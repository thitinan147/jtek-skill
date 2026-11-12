#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path, PurePosixPath

try:  # POSIX only; without it the round counter is unlocked
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]

NO_SUITE = "no-suite"
QUEUE_DIR = "jt-queue"
CODE_KINDS = frozenset(
    {
        "feat",
        "fix",
        "style",
        "refactor",
        "perf",
        "test",
        "build",
        "ci",
        "chore",
        "revert",
    }
)
SECTION_RANK = {"first": 0, "main": 1, "later": 2}
KIND_RE = re.compile(r"^([a-z]+)(?:\([^)]*\))?:")
ALLOWED_ACTIONS = frozenset(
    {
        "setup-board",
        "brief",
        "add-task",
        "do-task",
        "wait",
        "stop",
    }
)
COMMAND_FOR = {
    "setup-board": "/jt-work-queue",
    "brief": "/jt-work-queue",
    "add-task": "/jt-work-queue",
    "do-task": "/jt-work-queue",
    "wait": "",
    "stop": "",
}
STATUS_TOKENS = ("review:", "send-back:", "ask:", "merge:", "drop:")
SETUP_TIMEOUT = 900
TEST_TIMEOUT = 600


MAX_ENV_TIMEOUT = 3600.0


def _env_timeout(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        val = float(raw)
    except ValueError:
        return default
    if not val > 0:  # also rejects NaN
        return default
    return min(val, MAX_ENV_TIMEOUT)


NEXT_FOR = {
    "test-failed": "retry",
    "test-timeout": "retry",
    "setup-failed": "retry",
    "review-diff": "retry",
    "one-off-checker": "retry",
    "task-branch-missing": "retry",
    "merge-refused": "retry",
    "related": "ask",
    "browser-empty": "ask",
    "browser-missing": "ask",
    "browser-failed": "ask",
    "start-down": "ask",
    "click-mismatch": "ask",
    "worktree-failed": "ask",
    "pr-missing": "ask",
    "pr-duplicate": "ask",
    "pr-base": "ask",
    "pr-not-draft": "ask",
    "pr-failed": "ask",
    "gh-missing": "ask",
    "question-open": "ask",
    "board-missing": "stop",
    "commands-unapproved": "stop",
    "commands-changed": "stop",
    "not-on-queue-branch": "stop",
    "test-cmd-empty": "stop",
    "unknown-status": "stop",
    "task-line-missing": "stop",
    "task-closed": "stop",
    "merge": "stop",
    "git-status-failed": "stop",
    "invalid-id": "stop",
    "repo-missing": "stop",
    "repo-invalid": "stop",
    "repo-undeclared": "ask",
}
HINT_FOR = {
    "test-failed": "Read log:, fix the cause on task-<id>, commit, then run reach-review again.",
    "test-timeout": "The test command ran past its limit. Make it faster, or raise JT_TEST_TIMEOUT (max 3600 seconds).",
    "setup-failed": "SETUP_CMD failed in the task worktree. Read log:, then fix the command or the dependencies.",
    "review-diff": "Fix what detail: names in plan.md ('## review-diff' citing the latest code commit, or a missing '## evidence' row), then run gate.py diff-check.",
    "one-off-checker": "Delete the new check script, or name it in do:. Use the check commands already on the board.",
    "task-branch-missing": "Commit the work on one branch named task-<id>-<slug> (or task-<id>), then run reach-review again.",
    "merge-refused": "This gate cannot merge. Stop and report to the human.",
    "related": "Link each same-layer task under refs: in task.md, or run gate.py ask.",
    "browser-empty": "<BROWSER_TOOL> is empty in jt-queue/board.md. A human sets it; run gate.py ask.",
    "browser-missing": "No playwright or cypress was found. Install the project's browser tool, or run gate.py ask.",
    "browser-failed": "The browser command failed. Read its output above, fix the screen or the check, then retry.",
    "start-down": "Check start:, port:, and wait: in task.md and read log:. The app must listen on every port in port:.",
    "click-mismatch": "The click: command failed or is empty. Read log:, then fix the screen or the command.",
    "worktree-failed": "Git could not create a worktree for task-<id>. Resolve it, or run gate.py ask.",
    "pr-missing": "Push task-<id> and open one draft pull request (head task-<id>, base <queue>); see Handoff in SKILL.md.",
    "pr-duplicate": "Close the extra open PRs whose head is task-<id> so exactly one remains.",
    "pr-base": "Retarget the open PR to the queue branch.",
    "pr-not-draft": "Convert the PR back to a draft, then run reach-review --write again.",
    "pr-failed": "gh could not list PRs. Check gh auth and network, or run gate.py ask.",
    "gh-missing": "Install the GitHub CLI (gh), or run gate.py ask.",
    "question-open": "The ask: line in task.md is still open. Wait for the human to answer it.",
    "board-missing": "Create jt-queue/board.md with /jt-work-queue first.",
    "commands-unapproved": "Stop. A human must review the commands and run approve-commands. Never run it yourself.",
    "commands-changed": "Stop. Show the human what changed; only the human runs approve-commands.",
    "not-on-queue-branch": "Check out the queue: branch named in board.md before using --write.",
    "test-cmd-empty": "<TEST_CMD> is empty in board.md. Ask the human to set it (or no-suite).",
    "unknown-status": "Fix the status token on that board line to one of ask:, review:, send-back:, merge:, drop:.",
    "task-line-missing": "That id has no open line on the board. Add the line or check the id.",
    "task-closed": "That task is already closed on the board. Pick another id.",
    "merge": "This gate cannot merge. Only a human merges, then records it with /jt-review-work.",
    "git-status-failed": "git status failed. Fix the repository state, then run the command again.",
    "invalid-id": "Task ids look like 1 or 1.2 and nothing else.",
    "repo-missing": "A repo under '## repos' in board.md is not a git repository at its path:. Clone it there or fix path:, then run again.",
    "repo-undeclared": "task-<id> has commits in a repo the task does not list under repos:. Remove them, or run gate.py ask to add that repo to the task.",
    "repo-invalid": "Fix '## repos' in board.md: one '### <name>' per repo, exactly one with 'path: .' and nothing else, every other path: relative and distinct.",
}
MAX_ROUNDS = 3
ROUND_REASONS = frozenset({"test-failed", "test-timeout", "setup-failed"})
_VERDICT_LINE = re.compile(r"^[\s>*-]*verdict:[ \t]*(.*?)[ \t]*$", re.IGNORECASE | re.MULTILINE)
_CHECKED_LINE = re.compile(r"^[\s>*-]*checked:[ \t]*\S", re.IGNORECASE | re.MULTILINE)
REVIEW_DETAIL = {
    "no-review": "plan.md has no non-empty '## review-diff' section",
    "no-sha": "'## review-diff' does not cite any commit SHA",
    "stale-review": "'## review-diff' does not cite the latest code commit, or the worktree has uncommitted changes",
    "no-verdict": "'## review-diff' needs one line 'verdict: pass' or 'verdict: fix-needed'",
    "review-fix-needed": "'## review-diff' says verdict: fix-needed; fix the diff, commit, and review it again",
    "no-checked": "'## review-diff' needs at least one 'checked: <what you checked>' line",
    "no-repo-sha": "'## review-diff' needs one '<repo>: <sha>' line for each repo under repos:, citing that repo's latest code commit",
    "evidence-missing": "every pass: line in task.md must be quoted in the first cell of a filled row (pass line | command | result) in '## evidence' of plan.md",
}
MERGE_ARGV = {
    "merge",
    "/merge",
    "mark-merge",
    "/mark-merge",
    "jt-merge",
    "/jt-merge",
}
ROW_RE = re.compile(r"^\|\s*`<([^>]+)>`\s*\|\s*(.*?)\s*\|\s*$")
CARD_RE = re.compile(r"^- \[([ xX])\] \*\*(.+?)\*\*\s*(.*)$")
_CHECKER_BASENAME = re.compile(
    r"^(?:check|lint|verify)(?:[-_.].+)?\.(?:py|sh)$",
    re.IGNORECASE,
)
_CLOSED = frozenset({"merge:", "drop:"})
UNKNOWN_STATUS = "unknown:"
_STATUS_SET = frozenset(STATUS_TOKENS)
_COLON_TOKEN = re.compile(r"(?<!\S)([^\s:]+):")
_KIND_TAIL = re.compile(r"\([a-z]+\)\s*(.*)$")
_KIND_PAREN = re.compile(r"\(([a-z]+)\)\s*(.*)$")
_REF_ID = re.compile(r"(?<![\w.])(\d+(?:\.\d+)*)")
_CARD_ID_RE = re.compile(r"^\d+(\.\d+)*$")
REPOS_SECTION = "repos"
REPO_NAME_RE = re.compile(r"^[a-z][a-z0-9-]{0,31}$")
REPO_VALUES = ("TEST_CMD", "SETUP_CMD", "TYPECHECK_CMD", "LINT_CMD", "STACK_LOCK")
_SHA = re.compile(r"\b[0-9a-f]{7,40}\b", re.IGNORECASE)
_DOC_EXTS = (".md", ".rst", ".adoc")
_DOC_PREFIXES = (
    "README",
    "LICENSE",
    "CHANGELOG",
    "NOTICE",
    "AUTHORS",
    "CONTRIBUTING",
)


def is_doc_file(path: str) -> bool:
    name = path.strip().rsplit("/", 1)[-1]
    if not name:
        return False
    if name.lower().endswith(_DOC_EXTS):
        return True
    if "." not in name and name.upper().startswith(_DOC_PREFIXES):
        return True
    return False


def valid_card_id(card_id: str) -> bool:
    return bool(_CARD_ID_RE.match(card_id))


def status_on_line(text: str) -> str | None:
    match = _COLON_TOKEN.search(text)
    if not match:
        return None
    token = f"{match.group(1)}:"
    if token in _STATUS_SET:
        return token
    return UNKNOWN_STATUS


def _after_kind(rest: str) -> tuple[str, int]:
    kind_match = _KIND_TAIL.search(rest)
    if kind_match:
        return kind_match.group(1), kind_match.start(1)
    return rest, 0


def _status_span(line: str) -> tuple[str | None, int, int]:
    match = CARD_RE.match(line)
    if not match:
        return None, 0, 0
    suffix, suffix_at_rest = _after_kind(match.group(3))
    suffix_at = match.start(3) + suffix_at_rest
    found = _COLON_TOKEN.search(suffix)
    if not found:
        return None, suffix_at, suffix_at
    token = f"{found.group(1)}:"
    start = suffix_at + found.start()
    end = start + len(token)
    if token not in _STATUS_SET:
        return UNKNOWN_STATUS, start, end
    return token, start, end


def _has_boundary_token(text: str, token: str) -> bool:
    return re.search(rf"(?<!\S){re.escape(token)}", text) is not None


def _cut_known_status(text: str) -> str:
    for found in _COLON_TOKEN.finditer(text):
        token = f"{found.group(1)}:"
        if token in _STATUS_SET:
            return text[: found.start()]
    return text


class GateError(Exception):
    def __init__(self, reason: str, detail: str = "", log: str = "") -> None:
        self.reason = reason
        self.detail = detail
        self.log = log
        super().__init__(reason if not detail else f"{reason}: {detail}")


@dataclass
class Card:
    id: str
    section: str
    checked: bool
    status: str | None
    line: str
    index: int
    files: tuple[str, ...] = ()
    question: str = ""
    question_empty: bool = True
    has_card_file: bool = False
    topic: str = ""
    refs: tuple[str, ...] = ()


@dataclass
class Board:
    queue_branch: str
    test_cmd: str
    stack_lock: str
    cards: list[Card]
    text: str
    repos: list["RepoSpec"] = field(default_factory=list)


@dataclass
class Decision:
    action: str
    id: str = ""
    ids: tuple[str, ...] = ()
    reason: str = ""
    command: str = ""
    line: str = ""
    question: str = ""
    fields: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.action not in ALLOWED_ACTIONS:
            raise GateError("merge-refused")


def _home_lines(text: str) -> list[str]:
    """Board lines outside `## repos`: the home repo's own fields."""
    lines: list[str] = []
    inside = False
    for line in text.splitlines():
        if line.startswith("## "):
            inside = line[3:].strip().casefold() == REPOS_SECTION
        if not inside:
            lines.append(line)
    return lines


def parse_queue(text: str) -> str:
    for line in _home_lines(text):
        if line.startswith("queue:"):
            return line.split(":", 1)[1].strip()
    return ""


def parse_field(text: str, name: str) -> str:
    for line in _home_lines(text):
        match = ROW_RE.match(line)
        if match and match.group(1) == name:
            return match.group(2).strip()
    return ""


@dataclass
class RepoSpec:
    name: str
    path: str = ""
    queue: str = ""
    values: dict[str, str] = field(default_factory=dict)
    stray: tuple[str, ...] = ()

    @property
    def is_home(self) -> bool:
        return self.path == "."


def parse_repos(text: str) -> list[RepoSpec]:
    """Read `## repos`: one `### <name>` block per repo with path:, queue:, and a value table."""
    repos: list[RepoSpec] = []
    inside = False
    current: RepoSpec | None = None
    for line in text.splitlines():
        if line.startswith("## "):
            inside = line[3:].strip().casefold() == REPOS_SECTION
            current = None
            continue
        if not inside:
            continue
        if line.startswith("### "):
            current = RepoSpec(name=line[4:].strip())
            repos.append(current)
            continue
        if current is None:
            continue
        if line.startswith("path:"):
            current.path = line.split(":", 1)[1].strip()
            continue
        if line.startswith("queue:"):
            current.queue = line.split(":", 1)[1].strip()
            continue
        match = ROW_RE.match(line)
        if match:
            name, value = match.group(1), match.group(2).strip()
            if name in REPO_VALUES:
                current.values[name] = value
            elif value:
                current.stray = (*current.stray, name)
    return repos


def repos_shape_problems(repos: list[RepoSpec]) -> list[str]:
    """Problems in `## repos` that need no filesystem: names, the home row, absolute paths."""
    if not repos:
        return []
    problems: list[str] = []
    names = [repo.name for repo in repos]
    for name in dict.fromkeys(names):
        if not REPO_NAME_RE.match(name) or f"{name}:" in _STATUS_SET or name == "unknown":
            problems.append(f"{name or '(empty)'}.name")
        elif names.count(name) > 1:
            problems.append(f"{name}.duplicate")
    homes = [repo for repo in repos if repo.is_home]
    if len(homes) != 1:
        problems.append("home")
    if len(repos) < 2:
        problems.append("repos")
    for repo in repos:
        if repo.is_home:
            if repo.queue or any(v.strip() for v in repo.values.values()) or repo.stray:
                problems.append(f"{repo.name}.home-values")
            continue
        if not repo.path or PurePosixPath(repo.path).is_absolute() or repo.path.startswith("~"):
            problems.append(f"{repo.name}.path")
        for stray in repo.stray:
            problems.append(f"{repo.name}.{stray}")
    return problems


def repos_missing_fields(repos: list[RepoSpec]) -> list[str]:
    missing: list[str] = []
    for repo in repos:
        if repo.is_home:
            continue
        if not repo.queue:
            missing.append(f"{repo.name}.queue")
        for name in ("TEST_CMD", "STACK_LOCK"):
            if not repo.values.get(name, "").strip():
                missing.append(f"{repo.name}.{name}")
    return missing


def parse_board(text: str) -> Board:
    section = ""
    cards: list[Card] = []
    for index, line in enumerate(text.splitlines()):
        if line.startswith("## "):
            section = line[3:].strip().casefold()
            continue
        match = CARD_RE.match(line)
        if not match or section not in SECTION_RANK:
            continue
        suffix, _suffix_at = _after_kind(match.group(3))
        status = status_on_line(suffix)
        cards.append(
            Card(
                id=match.group(2).strip(),
                section=section,
                checked=match.group(1).lower() == "x",
                status=status,
                line=line,
                index=index,
            )
        )
    return Board(
        queue_branch=parse_queue(text),
        test_cmd=parse_field(text, "TEST_CMD"),
        stack_lock=parse_field(text, "STACK_LOCK"),
        cards=cards,
        text=text,
        repos=parse_repos(text),
    )


def question_text(card_text: str) -> str:
    for line in card_text.splitlines():
        if line.startswith("ask:"):
            return line[len("ask:") :].strip()
    return ""


def parse_files(card_text: str) -> list[str]:
    collecting = False
    files: list[str] = []
    for line in card_text.splitlines():
        if line.startswith("files:"):
            collecting = True
            continue
        if not collecting:
            continue
        if line.startswith("- "):
            name = line[2:].strip()
            if name and name != "-":
                files.append(name)
            continue
        if line.strip().endswith(":") and not line.startswith(" "):
            break
    return files


def hydrate(board: Board, bodies: dict[str, str | None]) -> Board:
    for card in board.cards:
        body = bodies.get(card.id)
        card.has_card_file = body is not None
        if body is None:
            card.files = ()
            card.question = ""
            card.question_empty = True
            card.topic = ""
            card.refs = ()
            continue
        card.files = tuple(parse_files(body))
        card.question = question_text(body)
        card.question_empty = card.question == ""
        card.topic = _label(body, "layer")
        card.refs = parse_refs(body)
    return board


def parse_refs(card_text: str) -> tuple[str, ...]:
    found: list[str] = []
    for line in _section_label(card_text, "refs:").splitlines():
        found.extend(_REF_ID.findall(line))
    return tuple(dict.fromkeys(found))


def _same_topic(card: Card, cards: list[Card]) -> list[Card]:
    if not card.topic:
        return []
    return [
        other
        for other in cards
        if other.id != card.id
        and not other.checked
        and other.section in SECTION_RANK
        and other.status not in _CLOSED
        and other.topic == card.topic
    ]


def _linked(card: Card, other: Card) -> bool:
    return other.id in card.refs or card.id in other.refs


def _related_stop(card: Card, cards: list[Card]) -> Decision | None:
    others = _same_topic(card, cards)
    if not others or all(_linked(card, other) for other in others):
        return None
    group = sorted([card, *others], key=lambda item: item.index)
    return Decision(
        "stop",
        id=card.id,
        ids=tuple(item.id for item in group),
        reason="related",
        line=card.line,
    )


def _path_overlaps(p1: str, p2: str) -> bool:
    p1 = p1.strip().rstrip("/")
    p2 = p2.strip().rstrip("/")
    if not p1 or not p2:
        return False
    if p1 == p2:
        return True
    return p2.startswith(p1 + "/") or p1.startswith(p2 + "/")


def _overlaps(left: tuple[str, ...], right: tuple[str, ...]) -> bool:
    for l in left:
        for r in right:
            if _path_overlaps(l, r):
                return True
    return False


def _blocked(card: Card, cards: list[Card]) -> bool:
    for other in cards:
        if other.id == card.id:
            continue
        if other.status in {"review:", "send-back:"} and _overlaps(card.files, other.files):
            return True
    return False


def _ordered(cards: list[Card]) -> list[Card]:
    return sorted(cards, key=lambda card: (SECTION_RANK.get(card.section, 9), card.index))


def _pool(cards: list[Card]) -> list[Card]:
    higher_open = any(
        (not card.checked) and card.section in {"first", "main"} for card in cards
    )
    chosen: list[Card] = []
    for card in cards:
        if card.checked or card.section not in SECTION_RANK:
            continue
        if card.section == "later" and higher_open:
            continue
        if _blocked(card, cards):
            continue
        chosen.append(card)
    return _ordered(chosen)


def _work(pool: list[Card], pred) -> Card | None:
    return next((card for card in pool if pred(card)), None)


def decide(
    board: Board | None,
    *,
    brief_exists: bool,
    dirty: bool | str,
    is_git: bool,
    repo_problem: tuple[str, tuple[str, ...]] | None = None,
) -> Decision:
    if board is None:
        return Decision("setup-board", reason="no-board", command=COMMAND_FOR["setup-board"])
    shape = repos_shape_problems(board.repos)
    if shape:
        return Decision("stop", reason="repo-invalid", fields=tuple(shape))
    missing: list[str] = []
    if not board.queue_branch:
        missing.append("queue")
    if board.test_cmd.strip() == "":
        missing.append("TEST_CMD")
    if board.stack_lock.strip() == "":
        missing.append("STACK_LOCK")
    missing.extend(repos_missing_fields(board.repos))
    if missing:
        return Decision("stop", reason="not-ready", fields=tuple(missing))
    if not is_git:
        return Decision("stop", reason="not-git")
    if repo_problem:
        return Decision("stop", reason=repo_problem[0], fields=repo_problem[1])
    if dirty == "unknown":
        return Decision("stop", reason="git-status-failed")
    if dirty is True or dirty == "dirty":
        return Decision("stop", reason="dirty")

    invalid = next(
        (
            card
            for card in _ordered(board.cards)
            if not card.checked
            and card.section in SECTION_RANK
            and not valid_card_id(card.id)
        ),
        None,
    )
    if invalid:
        return Decision("stop", id=invalid.id, reason="invalid-id", line=invalid.line)

    unknown = next(
        (
            card
            for card in _ordered(board.cards)
            if not card.checked
            and card.section in SECTION_RANK
            and card.status == UNKNOWN_STATUS
        ),
        None,
    )
    if unknown:
        return Decision("stop", id=unknown.id, reason="unknown-status", line=unknown.line)

    pool = _pool(board.cards)
    send_back = _work(pool, lambda card: card.status == "send-back:" and card.has_card_file)
    if send_back:
        return _take(board, send_back, "send-back")
    cleared = _work(
        pool,
        lambda card: card.status == "ask:" and card.question_empty and card.has_card_file,
    )
    if cleared:
        return _take(board, cleared, "question-cleared")
    ready = _work(pool, lambda card: card.status is None and card.has_card_file)
    if ready:
        return _take(board, ready, "ready")

    reviews = [
        card
        for card in _ordered(board.cards)
        if not card.checked and card.status == "review:" and card.section in SECTION_RANK
    ]
    if reviews:
        return Decision(
            "wait",
            id=reviews[0].id if len(reviews) == 1 else "",
            ids=tuple(card.id for card in reviews),
            reason="review",
            line=reviews[0].line,
        )

    waiting = [
        card
        for card in _ordered(board.cards)
        if not card.checked and card.status == "ask:" and not card.question_empty
    ]
    if waiting:
        return Decision(
            "wait",
            id=waiting[0].id,
            reason="question-open",
            line=waiting[0].line,
            question=waiting[0].question,
        )
    if not board.cards:
        if not brief_exists:
            return Decision("brief", reason="no-brief", command=COMMAND_FOR["brief"])
        return Decision("add-task", reason="no-task", command=COMMAND_FOR["add-task"])
    unchecked = [
        card for card in board.cards if not card.checked and card.section in SECTION_RANK
    ]
    orphans = [card for card in unchecked if not card.has_card_file]
    if orphans:
        return Decision("stop", id=orphans[0].id, reason="no-task-file", line=orphans[0].line)
    if any(card.has_card_file and _blocked(card, board.cards) for card in unchecked):
        blocked = next(card for card in unchecked if _blocked(card, board.cards))
        return Decision("stop", id=blocked.id, reason="overlap", line=blocked.line)
    return Decision("stop", reason="queue-clear")


def _do(card: Card, reason: str) -> Decision:
    return Decision(
        "do-task",
        id=card.id,
        reason=reason,
        command=COMMAND_FOR["do-task"],
        line=card.line,
    )


def _take(board: Board, card: Card, reason: str) -> Decision:
    stopped = _related_stop(card, board.cards)
    if stopped is not None:
        return stopped
    return _do(card, reason)


def apply_waiting_review(
    board_text: str,
    card_id: str,
    test_exit: int,
    link: str = "",
    *,
    question_empty: bool = False,
) -> str:
    if not valid_card_id(card_id):
        raise GateError("invalid-id")
    if test_exit != 0:
        raise GateError("test-failed")
    cleaned = link.strip()
    if cleaned == "merge" or _has_boundary_token(cleaned, "merge:"):
        raise GateError("merge-refused")
    pattern = re.compile(
        rf"^(- \[[ xX]\] \*\*{re.escape(card_id)}\*\*.*)$",
        re.M,
    )
    found = list(pattern.finditer(board_text))
    if len(found) != 1:
        raise GateError("task-line-missing")
    line = found[0].group(1)
    token, start, end = _status_span(line)
    if line.startswith("- [x]") or line.startswith("- [X]") or token in _CLOSED:
        raise GateError("task-closed")
    if token == UNKNOWN_STATUS:
        raise GateError("unknown-status")
    suffix = "review:" if not cleaned else f"review: {cleaned}"
    if token == "send-back:":
        new_line = f"{line[:start]}{suffix}{line[end:]}"
    elif token == "ask:":
        if not question_empty:
            raise GateError("question-open")
        new_line = f"{line[:start].rstrip()} {suffix}"
    elif token == "review:":
        new_line = f"{line} {cleaned}" if cleaned and re.search(r"review:\s*$", line) else line
    elif token is None:
        new_line = f"{line} {suffix}"
    else:
        raise GateError("task-closed")
    if _has_boundary_token(new_line, "merge:"):
        raise GateError("merge-refused")
    start, end = found[0].start(1), found[0].end(1)
    return board_text[:start] + new_line + board_text[end:]


def apply_card_ask(card_text: str, question: str, refused: str = "") -> str:
    q = " ".join(question.strip().splitlines()).strip()
    ref = refused.strip()
    lines: list[str] = []
    replaced_ask = False
    for line in card_text.splitlines():
        if line.startswith("refused:"):
            continue
        if line.startswith("ask:"):
            if not replaced_ask:
                lines.append(f"ask: {q}")
                if ref:
                    lines.append(f"refused: {ref}")
                replaced_ask = True
            continue
        lines.append(line)
    if not replaced_ask:
        if lines and lines[-1].strip() != "":
            lines.append("")
        lines.append(f"ask: {q}")
        if ref:
            lines.append(f"refused: {ref}")
    return "\n".join(lines) + "\n"


def apply_board_ask(board_text: str, card_id: str) -> str:
    if not valid_card_id(card_id):
        raise GateError("invalid-id")
    pattern = re.compile(
        rf"^(- \[[ xX]\] \*\*{re.escape(card_id)}\*\*.*)$",
        re.M,
    )
    found = list(pattern.finditer(board_text))
    if len(found) != 1:
        raise GateError("task-line-missing")
    line = found[0].group(1)
    token, start, _end = _status_span(line)
    if line.startswith("- [x]") or line.startswith("- [X]") or token in _CLOSED:
        raise GateError("task-closed")
    if token == UNKNOWN_STATUS:
        raise GateError("unknown-status")
    if token == "ask:":
        new_line = line
    elif token in {"review:", "send-back:"}:
        new_line = f"{line[:start].rstrip()} ask:"
    elif token is None:
        new_line = f"{line} ask:"
    else:
        raise GateError("task-closed")
    if _has_boundary_token(new_line, "merge:"):
        raise GateError("merge-refused")
    s, e = found[0].start(1), found[0].end(1)
    return board_text[:s] + new_line + board_text[e:]


def cmd_ask(root: Path, card_id: str, question: str, refused: str = "") -> int:
    if not valid_card_id(card_id):
        return _refuse("invalid-id")
    text = read_board_text(root)
    if text is None:
        return _refuse("board-missing")
    board_path = root / QUEUE_DIR / "board.md"
    queue = parse_queue(text)
    if not queue or _current_branch(root) != queue:
        return _refuse("not-on-queue-branch")
    card_path = _task_file(root, card_id)
    if card_path is None or not card_path.is_file():
        return _refuse("task-line-missing")
    try:
        updated_board = apply_board_ask(text, card_id)
    except GateError as err:
        return _refuse(err.reason, detail=err.detail)
    updated_card = apply_card_ask(card_path.read_text(encoding="utf-8"), question, refused)
    card_path.write_text(updated_card, encoding="utf-8")
    board_path.write_text(updated_board, encoding="utf-8")
    reset_rounds(root, card_id)
    print(f"asked: {card_id}")
    print("merge: no")
    return 0


def _git_env() -> dict[str, str]:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        env.pop(key, None)
    return env


def _run_git(root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        env=_git_env(),
    )


def _is_git(root: Path) -> bool:
    return _run_git(root, ["rev-parse", "--is-inside-work-tree"]).returncode == 0


def _current_branch(root: Path) -> str:
    proc = _run_git(root, ["rev-parse", "--abbrev-ref", "HEAD"])
    if proc.returncode != 0:
        return ""
    name = proc.stdout.strip()
    return "" if name == "HEAD" else name


def _branch_exists(root: Path, branch: str) -> bool:
    return _run_git(root, ["rev-parse", "--verify", "--quiet", branch]).returncode == 0


_TASK_SLUG_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def is_task_head(name: str, card_id: str) -> bool:
    """True for task-<id> or task-<id>-<slug> (slug: lowercase words joined by '-')."""
    bare = f"task-{card_id}"
    if name == bare:
        return True
    return name.startswith(bare + "-") and bool(_TASK_SLUG_RE.fullmatch(name[len(bare) + 1 :]))


def task_branch_names(root: Path, card_id: str) -> tuple[list[str], list[str]]:
    """(local, remote-only) branch names that belong to the task, sorted."""
    if not valid_card_id(card_id):
        return [], []
    bare = f"task-{card_id}"
    proc = _run_git(
        root,
        [
            "for-each-ref",
            "--format=%(refname)",
            f"refs/heads/{bare}",
            f"refs/heads/{bare}-*",
            f"refs/remotes/*/{bare}",
            f"refs/remotes/*/{bare}-*",
        ],
    )
    local: set[str] = set()
    remote: set[str] = set()
    if proc.returncode == 0:
        for ref in proc.stdout.split():
            if ref.startswith("refs/heads/"):
                name, bucket = ref[len("refs/heads/") :], local
            elif ref.startswith("refs/remotes/") and ref.count("/") >= 3:
                name, bucket = ref.split("/", 3)[3], remote
            else:
                continue
            if is_task_head(name, card_id):
                bucket.add(name)
    return sorted(local), sorted(remote - local)


def task_branch(root: Path, card_id: str) -> str:
    """The task's branch: the one local task-<id>[-<slug>], else the one on a remote, else task-<id>."""
    local, remote = task_branch_names(root, card_id)
    if len(local) == 1:
        return local[0]
    if not local and len(remote) == 1:
        return remote[0]
    return f"task-{card_id}"


def has_one_task_branch(root: Path, card_id: str) -> bool:
    local, _remote = task_branch_names(root, card_id)
    return len(local) == 1


def task_branch_missing_detail(root: Path, card_id: str, repo: str = "") -> str:
    local, _remote = task_branch_names(root, card_id)
    where = f"repo {repo}: " if repo else ""
    if len(local) > 1:
        return f"{where}more than one branch for this task ({', '.join(local)}); keep one"
    return f"{where}no task-{card_id} or task-{card_id}-<slug> branch"


def _git_show(root: Path, spec: str) -> str | None:
    proc = _run_git(root, ["show", spec])
    if proc.returncode != 0:
        return None
    return proc.stdout


def _queue_rel(*parts: str) -> str:
    return PurePosixPath(QUEUE_DIR, *parts).as_posix()


def _task_file(root: Path, card_id: str) -> Path | None:
    """The task contract, only if it stays inside jt-queue/tasks/<id>/."""
    if not valid_card_id(card_id):
        return None
    tasks = (root / QUEUE_DIR / "tasks").resolve()
    path = (tasks / card_id / "task.md").resolve()
    if not path.is_relative_to(tasks):
        return None
    return path


def _is_tracked(root: Path, rel: str) -> bool:
    if not _is_git(root):
        return False
    proc = _run_git(root, ["ls-files", "--error-unmatch", "--", rel])
    return proc.returncode == 0


def _read_disk(root: Path, rel: str) -> str | None:
    path = root / rel
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return None


def _read_queue_file(root: Path, branch: str, rel: str) -> str | None:
    """Ignored queue files stay on disk. Tracked files are read from `branch`."""
    disk = _read_disk(root, rel)
    if disk is not None and not _is_tracked(root, rel):
        return disk
    if not _is_git(root):
        return disk
    head = _current_branch(root)
    if branch and head == branch:
        if disk is not None:
            return disk
        return _git_show(root, f"HEAD:{rel}")
    if branch:
        shown = _git_show(root, f"{branch}:{rel}")
        if shown is not None:
            return shown
    return disk


def _dirty(root: Path) -> str:
    proc = _run_git(root, ["status", "--porcelain", "-z"])
    if proc.returncode != 0:
        return "unknown"
    parts = proc.stdout.split("\0")
    i = 0
    while i < len(parts):
        entry = parts[i]
        if not entry:
            i += 1
            continue
        status = entry[:2]
        path = entry[3:]
        if not path.startswith(QUEUE_DIR + "/"):
            return "dirty"
        if ("R" in status or "C" in status) and i + 1 < len(parts):
            i += 1
            orig_path = parts[i]
            if not orig_path.startswith(QUEUE_DIR + "/"):
                return "dirty"
        i += 1
    return "clean"


def read_board_text(root: Path) -> str | None:
    rel = _queue_rel("board.md")
    disk = _read_disk(root, rel)
    if not _is_git(root):
        return disk
    if disk is not None and not _is_tracked(root, rel):
        return disk
    queue = parse_queue(disk) if disk else ""
    head = _current_branch(root)
    if queue and head != queue:
        shown = _git_show(root, f"{queue}:{rel}")
        if shown is not None:
            return shown
    if disk is None:
        return _git_show(root, f"HEAD:{rel}")
    return disk


def _read_repo_file(root: Path, queue: str, rel: str) -> str | None:
    return _read_queue_file(root, queue, rel)


def load_board(root: Path) -> tuple[Board | None, bool]:
    text = read_board_text(root)
    if text is None:
        return None, False
    board = parse_board(text)
    bodies = {
        card.id: (
            _read_repo_file(root, board.queue_branch, _queue_rel("tasks", card.id, "task.md"))
            if valid_card_id(card.id)
            else None
        )
        for card in board.cards
    }
    brief = _read_repo_file(root, board.queue_branch, _queue_rel("brief.md"))
    return hydrate(board, bodies), brief is not None


def _section_label(text: str, name: str) -> str:
    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.strip() == name:
            start = index + 1
            break
    if start is None:
        return ""
    body: list[str] = []
    for line in lines[start:]:
        stripped = line.strip()
        if stripped.endswith(":") and not stripped.startswith("-") and not line.startswith(" "):
            break
        body.append(line)
    return "\n".join(body).strip()


def _section_h2(text: str, title: str) -> str:
    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.strip() == f"## {title}":
            start = index + 1
            break
    if start is None:
        return ""
    body: list[str] = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        body.append(line)
    return "\n".join(body).strip()


def _git_common_dir(root: Path) -> Path:
    proc = _run_git(root, ["rev-parse", "--git-common-dir"])
    if proc.returncode == 0 and proc.stdout.strip():
        raw = Path(proc.stdout.strip())
        return raw if raw.is_absolute() else (root / raw).resolve()
    return (root / ".git").resolve()


def _home_toplevel(root: Path) -> Path:
    """The home repo's main worktree, so `## repos` paths mean the same from a linked worktree."""
    common = _git_common_dir(root)
    if common.name == ".git":
        return common.parent.resolve()
    proc = _run_git(root, ["rev-parse", "--show-toplevel"])
    return Path(proc.stdout.strip()).resolve() if proc.returncode == 0 else root.resolve()


def repo_root(root: Path, repo: RepoSpec) -> Path:
    return (_home_toplevel(root) / repo.path).resolve()


def check_repos(root: Path, repos: list[RepoSpec]) -> tuple[str, tuple[str, ...]] | None:
    """Every non-home repo must be its own git work tree at path:, distinct from home and each other."""
    if not repos:
        return None
    home = _home_toplevel(root)
    seen: dict[Path, str] = {home: next((r.name for r in repos if r.is_home), "home")}
    missing: list[str] = []
    invalid: list[str] = []
    for repo in repos:
        if repo.is_home:
            continue
        target = repo_root(root, repo)
        proc = _run_git(target, ["rev-parse", "--show-toplevel"]) if target.is_dir() else None
        if proc is None or proc.returncode != 0:
            missing.append(repo.name)
            continue
        top = Path(proc.stdout.strip()).resolve()
        if top != target or top in seen:
            invalid.append(f"{repo.name}.path")
            continue
        seen[top] = repo.name
    if missing:
        return "repo-missing", tuple(missing)
    if invalid:
        return "repo-invalid", tuple(invalid)
    return None


def _digest(parts: dict[str, str]) -> str:
    blob = json.dumps({k: v.strip() for k, v in parts.items()}, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _board_commands(board_text: str) -> dict[str, str]:
    # Without `## repos` this must stay exactly the v22 dict, so existing approvals still match.
    commands = {
        "TEST_CMD": parse_field(board_text, "TEST_CMD"),
        "SETUP_CMD": parse_field(board_text, "SETUP_CMD"),
    }
    for repo in parse_repos(board_text):
        if repo.is_home:
            continue
        # path: and queue: decide where the commands run, so they are approved with them.
        commands[f"repo:{repo.name}:path"] = repo.path
        commands[f"repo:{repo.name}:queue"] = repo.queue
        commands[f"repo:{repo.name}:TEST_CMD"] = repo.values.get("TEST_CMD", "")
        commands[f"repo:{repo.name}:SETUP_CMD"] = repo.values.get("SETUP_CMD", "")
    return commands


def start_entries(card_text: str) -> list[tuple[str, str]]:
    """`start:` as a list, one `- <repo>: <command>` per repo, for a task across repos."""
    entries: list[tuple[str, str]] = []
    for line in _section_label(card_text, "start:").splitlines():
        item = line.strip()
        if not item.startswith("- "):
            continue
        head, sep, command = item[2:].partition(":")
        if sep and REPO_NAME_RE.match(head.strip()) and command.strip():
            entries.append((head.strip(), command.strip()))
    return entries


def _card_commands(card_text: str) -> dict[str, str]:
    commands = {name: _label(card_text, name) for name in ("start", "port", "wait", "click")}
    entries = start_entries(card_text)
    if entries:  # absent on a v22 card, so its approval digest does not change
        commands["start-repos"] = "\n".join(f"{name}: {command}" for name, command in entries)
        commands["repos"] = _label(card_text, "repos")
    return commands


def _board_runs_commands(commands: dict[str, str]) -> bool:
    if any(name.startswith("repo:") for name in commands):
        return True  # path: decides where every command and start line runs
    for name, value in commands.items():
        value = value.strip()
        if name.endswith("SETUP_CMD") and value:
            return True
        if name.endswith("TEST_CMD") and value not in ("", NO_SUITE):
            return True
    return False


def _card_runs_commands(card_text: str, commands: dict[str, str]) -> bool:
    return bool(
        commands["start"].strip() or commands["click"].strip() or commands.get("start-repos", "").strip()
    )


def _approval_path(root: Path) -> Path:
    # Inside .git: it is never part of a branch, commit, or pull request, so changes
    # to board.md or a card cannot carry an approval with them.
    return _git_common_dir(root) / "jt-queue" / "approved-commands.json"


def _load_approvals(root: Path) -> dict:
    try:
        data = json.loads(_approval_path(root).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _commands_refusal(
    root: Path, board_text: str, card_id: str, card_text: str, check_board: bool = True
) -> tuple[str, str] | None:
    """Refuse to run shell commands that a human has not approved on this machine."""
    approvals = _load_approvals(root)
    board_cmds = _board_commands(board_text)
    if check_board and _board_runs_commands(board_cmds):
        known = approvals.get("board")
        if not known:
            return "commands-unapproved", (
                "TEST_CMD/SETUP_CMD (and any '## repos' entry) in jt-queue/board.md have not been approved on this machine. "
                "A human must review them, then run: gate.py approve-commands --root . --id " + card_id
            )
        if known != _digest(board_cmds):
            return "commands-changed", (
                "TEST_CMD/SETUP_CMD (or a '## repos' path:, queue:, or command) in jt-queue/board.md changed since a human approved them. "
                "Review the change, then run: gate.py approve-commands --root . --id " + card_id
            )
    card_cmds = _card_commands(card_text)
    if _card_runs_commands(card_text, card_cmds):
        known = (approvals.get("cards") or {}).get(card_id)
        if not known:
            return "commands-unapproved", (
                f"start/click in jt-queue/tasks/{card_id}/task.md have not been approved. "
                "A human must review them, then run: gate.py approve-commands --root . --id " + card_id
            )
        if known != _digest(card_cmds):
            return "commands-changed", (
                f"start/click in jt-queue/tasks/{card_id}/task.md changed since a human approved them. "
                "Review the change, then run: gate.py approve-commands --root . --id " + card_id
            )
    return None


def cmd_approve_commands(root: Path, card_id: str) -> int:
    """HUMAN-ONLY: record the commands in the board (and one card) as reviewed."""
    if card_id and not valid_card_id(card_id):
        return _refuse("invalid-id")
    board_text = read_board_text(root)
    if board_text is None:
        return _refuse("board-missing")
    approvals = _load_approvals(root)
    board_cmds = _board_commands(board_text)
    approvals["board"] = _digest(board_cmds)
    print("approved board commands:")
    for name, value in board_cmds.items():
        print(f"  {name} = {value.strip() or '(empty)'}")
    if card_id:
        card_text = _read_card(root, card_id)
        card_cmds = _card_commands(card_text)
        approvals.setdefault("cards", {})[card_id] = _digest(card_cmds)
        print(f"approved card {card_id} commands:")
        for name, value in card_cmds.items():
            print(f"  {name} = {value.strip() or '(empty)'}")
    path = _approval_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(approvals, indent=2, sort_keys=True), encoding="utf-8")
    print("merge: no")
    return 0


def _record_command_log(
    root: Path, card_id: str, command_name: str, output: str
) -> tuple[str, str]:
    log_dir = _git_common_dir(root) / "jt-queue" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{card_id}-{command_name}.log"
    log_path.write_text(output, encoding="utf-8")
    tail_lines = [line for line in output.splitlines() if line.strip()][-20:]
    detail = "\n".join(tail_lines) if tail_lines else f"{command_name}-failed"
    return detail, str(log_path)


def _env_with_bin(cwd: Path) -> dict[str, str]:
    env = _git_env()
    bin_dir = cwd / "node_modules" / ".bin"
    if bin_dir.is_dir():
        env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    return env


def _run_shell(
    command: str, cwd: Path, timeout: float | None = None
) -> tuple[int, str, bool]:
    proc = subprocess.Popen(
        command,
        # Intentional: command comes from the human-confirmed board/card (see SECURITY.md).
        shell=True,  # nosec B602
        cwd=cwd,
        env=_env_with_bin(cwd),
        start_new_session=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    timed_out = False
    try:
        out, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            out, _ = proc.communicate(timeout=0.2)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            out, _ = proc.communicate()
        if not out:
            partial = exc.output
            if isinstance(partial, bytes):
                partial = partial.decode("utf-8", errors="replace")
            out = partial or ""
    return (proc.returncode if not timed_out else -1, out or "", timed_out)


def emit(decision: Decision, extra: list[str] | None = None) -> None:
    print(f"action: {decision.action}")
    print(f"command: {decision.command}")
    print(f"id: {decision.id}")
    if decision.ids:
        print("ids: " + ", ".join(decision.ids))
    print(f"reason: {decision.reason}")
    print("merge: no")
    if decision.fields:
        print("fields: " + " ".join(decision.fields))
    if decision.line:
        print(f"line: {decision.line}")
    if decision.question:
        print(f"ask: {decision.question}")
    if extra:
        print("\n".join(extra))


def cmd_next(root: Path) -> int:
    board, brief_exists = load_board(root)
    has_git = _is_git(root) or (root / ".git").exists()
    decision = decide(
        board,
        brief_exists=brief_exists,
        dirty=_dirty(root) if board is not None and has_git else "clean",
        is_git=True if board is None else has_git,
        repo_problem=check_repos(root, board.repos) if board is not None and has_git else None,
    )
    extra: list[str] = []
    if board is not None and has_git and board.queue_branch:
        landed_ids: list[str] = []
        pending_gh: list[str] = []
        for card in _ordered(board.cards):
            if (
                not card.checked
                and card.section in SECTION_RANK
                and card.status == "review:"
                and valid_card_id(card.id)
            ):
                across = landed_across(root, board.text, _read_card(root, card.id), card.id, quick=True)
                if across is not None:
                    if across[0]:
                        landed_ids.append(card.id)
                    continue
                if _is_ancestor(root, task_branch(root, card.id), board.queue_branch):
                    landed_ids.append(card.id)
                else:
                    pending_gh.append(card.id)
        if pending_gh and _has_remote(root) and shutil.which("gh") is not None:
            listed = _gh(
                root,
                [
                    "pr", "list", "--state", "merged", "--limit", "200",
                    "--json", "state,headRefName",
                ],
                timeout=_env_timeout("JT_GH_TIMEOUT", 2.0),
            )
            if listed is not None and listed.returncode == 0:
                for cid in pending_gh:
                    head = task_branch(root, cid)
                    if _payload_mark(listed.stdout, head, fuzzy=task_branch_gone(root, cid)) == "merged":
                        landed_ids.append(cid)
        if landed_ids:
            extra.append("landed-waiting: " + ", ".join(landed_ids))
    if board is not None and has_git:
        prune_rounds(root, {card.id for card in board.cards if not card.checked})
    emit(decision, extra or None)
    return 0


def _attempts_path(root: Path) -> Path:
    return _git_common_dir(root) / "jt-queue" / "attempts.json"


def _load_attempts(root: Path) -> dict:
    try:
        data = json.loads(_attempts_path(root).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_attempts(root: Path, data: dict) -> None:
    path = _attempts_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


@contextmanager
def _attempts_lock(root: Path):
    lock = _attempts_path(root).with_suffix(".lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    with open(lock, "a+", encoding="utf-8") as handle:
        if fcntl is not None:
            fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(handle, fcntl.LOCK_UN)


def reset_rounds(root: Path, card_id: str) -> None:
    with _attempts_lock(root):
        data = _load_attempts(root)
        if data.pop(card_id, None) is not None:
            _save_attempts(root, data)


def prune_rounds(root: Path, open_ids: set[str]) -> None:
    """Forget counts of tasks that are closed or gone from the board (merge:, drop:)."""
    with _attempts_lock(root):
        data = _load_attempts(root)
        kept = {key: value for key, value in data.items() if key in open_ids}
        if kept != data:
            _save_attempts(root, kept)


def count_round(root: Path, card_id: str) -> int:
    """Every failed reach-review run is a round, so retrying an unchanged commit still counts."""
    with _attempts_lock(root):
        data = _load_attempts(root)
        entry = data.get(card_id)
        count = int(entry.get("count", 0)) + 1 if isinstance(entry, dict) else 1
        data[card_id] = {"count": count}
        _save_attempts(root, data)
    return count


def _refuse_round(root: Path, card_id: str, reason: str, detail: str = "", log: str = "") -> int:
    rounds = count_round(root, card_id)
    note = f"round {min(rounds, MAX_ROUNDS)} of {MAX_ROUNDS}"
    if rounds >= MAX_ROUNDS:
        return _refuse(
            reason,
            detail=f"{detail}\n{note}: stop retrying and run gate.py ask with what each round tried".lstrip(),
            log=log,
            next_step="ask",
        )
    return _refuse(reason, detail=f"{detail}\n{note}".lstrip(), log=log)


def _refuse(
    reason: str, detail: str = "", log: str = "", next_step: str = ""
) -> int:
    print(f"refused: {reason}")
    print("merge: no")
    nxt = next_step or NEXT_FOR.get(reason)
    if nxt:
        print(f"next: {nxt}")
    if detail:
        print(f"detail: {detail}")
    if log:
        print(f"log: {log}")
    hint = HINT_FOR.get(reason)
    if hint:
        print(f"hint: {hint}")
    return 1


def opens_repo_review(kind: str) -> bool:
    return kind in CODE_KINDS


def _label(text: str, name: str) -> str:
    prefix = f"{name}:"
    for line in text.splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    return ""


def sees_screen(card_text: str) -> bool:
    return _label(card_text, "screen") == "yes"


def _header_bullets(card_text: str) -> list[str]:
    bullets: list[str] = []
    for line in _section_label(card_text, "pass:").splitlines():
        if not line.startswith("- "):
            continue
        item = line[2:].strip()
        if item and item != "-":
            bullets.append(item)
    return bullets


def _commit_kinds(root: Path, queue: str, card_id: str) -> list[str] | None:
    if not queue:
        return None
    proc = _run_git(root, ["log", "--format=%s", f"{queue}..{task_branch(root, card_id)}"])
    if proc.returncode != 0:
        return None
    kinds: list[str] = []
    for line in proc.stdout.splitlines():
        match = KIND_RE.match(line.strip())
        if match:
            kinds.append(match.group(1))
    return kinds


def _commit_kinds_outside_queue(
    root: Path, queue: str, card_id: str
) -> list[str] | None:
    if not queue:
        return None
    proc = _run_git(
        root,
        [
            "log",
            "--no-merges",
            "--format=%s",
            f"{queue}..{task_branch(root, card_id)}",
            "--",
            ".",
            ":(exclude)jt-queue",
        ],
    )
    if proc.returncode != 0:
        return None
    kinds: list[str] = []
    for line in proc.stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        match = KIND_RE.match(stripped)
        kinds.append(match.group(1) if match else "")
    return kinds


def card_kind_in_board(board_text: str, card_id: str) -> str:
    if not valid_card_id(card_id):
        return ""
    pattern = re.compile(
        rf"^- \[[ xX]\] \*\*{re.escape(card_id)}\*\*\s*(.*)$",
        re.M,
    )
    found = list(pattern.finditer(board_text))
    if len(found) != 1:
        return ""
    rest = _cut_known_status(found[0].group(1))
    match = _KIND_PAREN.search(rest)
    return match.group(1) if match else ""


def card_kind_at_merge_base(root: Path, queue: str, card_id: str) -> str:
    if not queue or not valid_card_id(card_id) or not _branch_exists(root, task_branch(root, card_id)):
        return ""
    proc = _run_git(root, ["merge-base", queue, task_branch(root, card_id)])
    if proc.returncode != 0 or not proc.stdout.strip():
        return ""
    rel = _queue_rel("board.md")
    disk = _read_disk(root, rel)
    if disk is not None and not _is_tracked(root, rel):
        return card_kind_in_board(disk, card_id)
    base = proc.stdout.strip()
    base_board = _git_show(root, f"{base}:{rel}")
    if base_board is None:
        return ""
    return card_kind_in_board(base_board, card_id)


def card_tier(
    root: Path, queue: str, card_id: str, card_text: str, board_text: str = ""
) -> str:
    base_kind = card_kind_at_merge_base(root, queue, card_id)
    if base_kind not in {"docs", "style"}:
        return "standard"
    if board_text and card_kind_in_board(board_text, card_id) != base_kind:
        return "standard"
    if sees_screen(card_text):
        return "standard"
    outside_kinds = _commit_kinds_outside_queue(root, queue, card_id)
    if outside_kinds is None or any(k != base_kind for k in outside_kinds):
        return "standard"
    all_kinds = _commit_kinds(root, queue, card_id)
    if all_kinds is None or any(k not in {base_kind, "docs"} for k in all_kinds):
        return "standard"
    if base_kind == "docs":
        changed = _diff_names(root, queue, card_id)
        if changed is None or any(not is_doc_file(path) for path in changed):
            return "standard"
    return "quick"


def _code_diff_reviewable(root: Path, queue: str, card_id: str) -> bool:
    proc = _run_git(
        root,
        [
            "diff",
            "--name-only",
            f"{queue}...{task_branch(root, card_id)}",
            "--",
            ".",
            ":(exclude)jt-queue",
        ],
    )
    if proc.returncode != 0:
        return False
    return any(line.strip() for line in proc.stdout.splitlines())


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def _stop_process(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait(timeout=2)


def _wait_until_up(proc: subprocess.Popen[str], ports: list[int], wait_seconds: int = 60) -> bool:
    deadline = time.monotonic() + wait_seconds
    while time.monotonic() < deadline:
        if all(_port_open(port) for port in ports):
            return True
        if proc.poll() is not None:
            return False
        time.sleep(0.05)
    return all(_port_open(port) for port in ports)


def _parse_ports(port_text: str) -> list[int] | None:
    ports: list[int] = []
    for piece in re.split(r"[,\s]+", port_text.strip()):
        if not piece:
            continue
        if not piece.isdigit():
            return None
        port = int(piece)
        if port < 1 or port > 65535:
            return None
        ports.append(port)
    return ports or None


def _command_evidence(
    root: Path, card_id: str, command_name: str, output: str, fallback: str
) -> tuple[str, str]:
    """Return (detail, log path); outside a git repo there is no log, only the tail."""
    if _is_git(root):
        return _record_command_log(root, card_id or "adhoc", command_name, output)
    tail = [line for line in output.splitlines() if line.strip()][-20:]
    return ("\n".join(tail) if tail else fallback), ""


def _run_while_up(
    work: Path, start: str, ports: list[int], wait_seconds: int, run, card_id: str = ""
) -> str | None:
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="replace") as sink:
        proc = subprocess.Popen(
            start,
            # Intentional: command comes from the human-confirmed board/card (see SECURITY.md).
            shell=True,  # nosec B602
            cwd=work,
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=sink,
            stderr=subprocess.STDOUT,
            env=_env_with_bin(work),
        )
        try:
            if not _wait_until_up(proc, ports, wait_seconds):
                code = proc.poll()
                state = (
                    f"start exited with code {code}"
                    if code is not None
                    else f"start is still running but port(s) {', '.join(map(str, ports))} did not open within {wait_seconds}s"
                )
                sink.flush()
                sink.seek(0)
                detail, log_path = _command_evidence(work, card_id, "start", sink.read(), "start-down")
                raise GateError("start-down", detail=f"{state}\n{detail}", log=log_path)
            return run()
        finally:
            _stop_process(proc)


def _click_surface(work: Path, card_text: str, card_id: str = "") -> str | None:
    start = _label(card_text, "start")
    port_text = _label(card_text, "port")
    click = _label(card_text, "click")
    wait_text = _label(card_text, "wait")
    wait_seconds = int(wait_text) if wait_text.isdigit() and int(wait_text) > 0 else 60
    ports = _parse_ports(port_text)
    if not start or ports is None:
        raise GateError("start-down", detail="start: is empty or port: is missing or invalid in task.md")

    return _run_while_up(work, start, ports, wait_seconds, lambda: _run_click(work, click, card_id), card_id)


def _run_click(work: Path, click: str, card_id: str) -> str | None:
    if not click:
        raise GateError("click-mismatch", detail="click: is empty in task.md")
    try:
        result = subprocess.run(
            click,
            # Intentional: command comes from the human-confirmed board/card (see SECURITY.md).
            shell=True,  # nosec B602
            cwd=work,
            capture_output=True,
            text=True,
            env=_env_with_bin(work),
            timeout=300,
        )
    except subprocess.TimeoutExpired as exc:
        partial = exc.output.decode("utf-8", "replace") if isinstance(exc.output, bytes) else (exc.output or "")
        detail, log_path = _command_evidence(work, card_id, "click", partial, "click-timeout")
        raise GateError("click-mismatch", detail=f"click timed out after 300s\n{detail}", log=log_path)
    if result.returncode != 0:
        detail, log_path = _command_evidence(
            work, card_id, "click", (result.stdout or "") + (result.stderr or ""), "no output"
        )
        raise GateError(
            "click-mismatch",
            detail=f"click exited with code {result.returncode}\n{detail}",
            log=log_path,
        )
    return None


def _run_all_while_up(
    starts: list[tuple[str, Path, str]], ports: list[int], wait_seconds: int, run, card_id: str = ""
) -> str | None:
    """Start every (repo, cwd, command) in order, wait for all ports, run, then stop them all."""
    with ExitStack() as stack:
        procs: list[tuple[str, Path, subprocess.Popen[str], object]] = []
        for name, cwd, command in starts:
            sink = stack.enter_context(
                tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="replace")
            )
            proc = subprocess.Popen(
                command,
                # Intentional: command comes from the human-approved card (see SECURITY.md).
                shell=True,  # nosec B602
                cwd=cwd,
                start_new_session=True,
                stdin=subprocess.DEVNULL,
                stdout=sink,
                stderr=subprocess.STDOUT,
                env=_env_with_bin(cwd),
            )
            stack.callback(_stop_process, proc)
            procs.append((name, cwd, proc, sink))
        deadline = time.monotonic() + wait_seconds
        down: tuple[str, Path, subprocess.Popen[str], object] | None = None
        while not all(_port_open(port) for port in ports):
            down = next((entry for entry in procs if entry[2].poll() is not None), None)
            if down is not None or time.monotonic() >= deadline:
                break
            time.sleep(0.05)
        else:
            return run()
        name, cwd, proc, sink = down or procs[-1]
        code = proc.poll()
        state = (
            f"repo {name}: start exited with code {code}"
            if code is not None
            else f"port(s) {', '.join(map(str, ports))} did not open within {wait_seconds}s"
        )
        sink.flush()  # type: ignore[attr-defined]
        sink.seek(0)  # type: ignore[attr-defined]
        detail, log_path = _command_evidence(cwd, card_id, f"{name}-start", sink.read(), "start-down")  # type: ignore[attr-defined]
        raise GateError("start-down", detail=f"{state}\n{detail}", log=log_path)


def _click_target(click: str, names: list[str]) -> tuple[str, str]:
    """`click: fe: npx playwright test` runs in fe; without a repo prefix it runs in the first repo."""
    head, sep, rest = click.partition(":")
    if sep and head.strip() in names and rest.strip():
        return head.strip(), rest.strip()
    return (names[0] if names else ""), click


def _starts_across(card_text: str, roots: dict[str, Path]) -> list[tuple[str, Path, str]]:
    entries = start_entries(card_text)
    if not entries:
        raise GateError("start-down", detail="start: needs one '- <repo>: <command>' line per repo for a task across repos")
    unknown = [name for name, _cmd in entries if name not in roots]
    if unknown:
        raise GateError("repo-invalid", detail="start: names a repo not under repos: " + ", ".join(unknown))
    return [(name, roots[name], command) for name, command in entries]


def _click_across(works: dict[str, Path], card_text: str, card_id: str) -> str | None:
    starts = _starts_across(card_text, works)
    ports = _parse_ports(_label(card_text, "port"))
    if ports is None:
        raise GateError("start-down", detail="port: is missing or invalid in task.md")
    wait_text = _label(card_text, "wait")
    wait_seconds = int(wait_text) if wait_text.isdigit() and int(wait_text) > 0 else 60
    target, click = _click_target(_label(card_text, "click"), list(works))
    work = works[target]
    return _run_all_while_up(starts, ports, wait_seconds, lambda: _run_click(work, click, card_id), card_id)


_BROWSER_ORDER = ("playwright", "cypress")
_BROWSER_TAIL = {"playwright": ("test",), "cypress": ("run",)}


def _declared_browsers(root: Path) -> set[str]:
    package = root / "package.json"
    if not package.is_file():
        return set()
    try:
        data = json.loads(package.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return set()
    deps: set[str] = set()
    for key in ("dependencies", "devDependencies", "optionalDependencies"):
        block = data.get(key)
        if isinstance(block, dict):
            deps.update(str(name) for name in block)
    found: set[str] = set()
    if "playwright" in deps or "@playwright/test" in deps:
        found.add("playwright")
    if "cypress" in deps:
        found.add("cypress")
    scripts = data.get("scripts")
    if isinstance(scripts, dict):
        blob = "\n".join(value for value in scripts.values() if isinstance(value, str))
        if "playwright" in blob:
            found.add("playwright")
        if "cypress" in blob:
            found.add("cypress")
    return found


def resolve_browser_argv(root: Path, tool: str = "") -> list[str] | None:
    name = tool.strip().lower()
    if name in _BROWSER_TAIL:
        order = (name,)
    elif name == "":
        order = _BROWSER_ORDER
    else:
        return None
    env = _env_with_bin(root)
    declared = _declared_browsers(root)
    for candidate in order:
        local = root / "node_modules" / ".bin" / candidate
        tail = list(_BROWSER_TAIL[candidate])
        if local.is_file() and os.access(local, os.X_OK):
            return [str(local), *tail]
        if shutil.which(candidate, path=env.get("PATH")):
            return [candidate, *tail]
        if candidate in declared:
            return ["npx", "--no-install", candidate, *tail]
    return None


def _run_argv(argv: list[str], cwd: Path, timeout: int = 300) -> int:
    try:
        proc = subprocess.run(
            argv,
            cwd=cwd,
            env=_env_with_bin(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return 1
    if proc.returncode != 0:
        if proc.stdout:
            sys.stderr.write(proc.stdout)
            if not proc.stdout.endswith("\n"):
                sys.stderr.write("\n")
        if proc.stderr:
            sys.stderr.write(proc.stderr)
            if not proc.stderr.endswith("\n"):
                sys.stderr.write("\n")
    return proc.returncode


def run_screen_check(
    root: Path,
    *,
    start: str = "",
    ports: str = "",
    wait: str = "",
    browser: str = "",
    no_start: bool = False,
    card_id: str = "",
    starts: list[tuple[str, Path, str]] | None = None,
) -> int:
    def fail(reason: str, detail: str = "", log: str = "") -> int:
        print(f"screen-check: {reason}")
        if detail:
            print(f"detail: {detail}")
        if log:
            print(f"log: {log}")
        hint = HINT_FOR.get(reason)
        if hint:
            print(f"hint: {hint}")
        return 1

    argv = resolve_browser_argv(root, browser)
    if argv is None:
        return fail("browser-missing")
    if no_start or not (start.strip() or starts):
        if _run_argv(argv, root) != 0:
            return fail("browser-failed")
        print("screen-check: ok")
        return 0
    parsed = _parse_ports(ports)
    if parsed is None:
        return fail("start-down", "port: is missing or invalid")
    wait_seconds = int(wait) if wait.isdigit() and int(wait) > 0 else 60

    def run() -> str | None:
        if _run_argv(argv, root) != 0:
            return "browser-failed"
        return None

    try:
        if starts:
            reason = _run_all_while_up(starts, parsed, wait_seconds, run, card_id)
        else:
            reason = _run_while_up(root, start, parsed, wait_seconds, run, card_id)
    except GateError as err:
        return fail(err.reason, err.detail, err.log)
    if reason:
        return fail(reason)
    print("screen-check: ok")
    return 0


def screen_check_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="gate.py screen-check",
        description=(
            "JTek screen check. Start the app when start is set, "
            "then run the playwright or cypress command that already exists. Exit non-zero on failure"
        ),
    )
    parser.add_argument("--root", default=".")
    parser.add_argument("--id", default="")
    parser.add_argument("--start", default="")
    parser.add_argument("--port", default="")
    parser.add_argument("--wait", default="")
    parser.add_argument("--browser", default="")
    parser.add_argument("--no-start", action="store_true")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    start = args.start
    ports = args.port
    wait = args.wait
    browser = args.browser
    if args.id:
        if not valid_card_id(args.id):
            return _refuse("invalid-id")
        text = read_board_text(root) or ""
        card = _read_card(root, args.id)
        card_start = _label(card, "start")
        if start and start.strip() != card_start.strip():
            return _refuse("commands-changed", detail="--start does not match card start")
        multi = bool(start_entries(card))
        if multi:
            repos = parse_repos(text)
            shape = repos_shape_problems(repos)
            if shape:
                return _refuse("repo-invalid", detail=", ".join(shape))
            problem = check_repos(root, repos)
            if problem:
                return _refuse(problem[0], detail=", ".join(problem[1]))
        unapproved = _commands_refusal(root, text, args.id, card, check_board=multi)
        if unapproved:
            return _refuse(unapproved[0], detail=unapproved[1])
        if not browser:
            browser = parse_field(text, "BROWSER_TOOL")
        if start_entries(card):
            # A task across repos starts each repo from its own checkout at path:.
            try:
                targets = card_targets(root, text, card) or []
                starts = _starts_across(card, {t.name: t.root for t in targets})
            except GateError as err:
                return _refuse(err.reason, detail=err.detail)
            return run_screen_check(
                root,
                ports=ports or _label(card, "port"),
                wait=wait or _label(card, "wait"),
                browser=browser,
                no_start=args.no_start,
                card_id=args.id,
                starts=starts,
            )
        if not start:
            start = card_start
        if not ports:
            ports = _label(card, "port")
        if not wait:
            wait = _label(card, "wait")
    return run_screen_check(
        root,
        start=start,
        ports=ports,
        wait=wait,
        browser=browser,
        no_start=args.no_start,
        card_id=args.id,
    )


@contextmanager
def _card_worktree(root: Path, card_id: str, setup_cmd: str = ""):
    branch = task_branch(root, card_id)
    if not has_one_task_branch(root, card_id):
        raise GateError("task-branch-missing", detail=task_branch_missing_detail(root, card_id))
    if _current_branch(root) == branch:
        yield root
        return
    parent = Path(tempfile.mkdtemp(prefix="jt-work-queue-"))
    worktree = parent / "card"
    try:
        added = _run_git(root, ["worktree", "add", "--detach", str(worktree), branch])
        if added.returncode != 0:
            raise GateError("worktree-failed", added.stderr.strip())
        if setup_cmd.strip():
            code, out, _timed_out = _run_shell(setup_cmd.strip(), worktree, timeout=SETUP_TIMEOUT)
            if code != 0:
                detail, log_path = _record_command_log(root, card_id, "setup", out)
                raise GateError("setup-failed", detail=detail, log=log_path)
        yield worktree
    finally:
        _run_git(root, ["worktree", "remove", "--force", str(worktree)])
        shutil.rmtree(parent, ignore_errors=True)


def detect_setup_cmd(root: Path) -> tuple[str, str]:
    """Return (command, source file) for the dependency install step, or ("", "")."""
    package = root / "package.json"
    if package.is_file():
        try:
            data = json.loads(package.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
        has_deps = bool(data.get("dependencies") or data.get("devDependencies"))
        if has_deps:
            if (root / "pnpm-lock.yaml").is_file():
                return "pnpm install --frozen-lockfile", "pnpm-lock.yaml"
            if (root / "yarn.lock").is_file():
                return "yarn install --frozen-lockfile", "yarn.lock"
            if (root / "bun.lock").is_file():
                return "bun install --frozen-lockfile", "bun.lock"
            if (root / "bun.lockb").is_file():
                return "bun install --frozen-lockfile", "bun.lockb"
            if (root / "package-lock.json").is_file():
                return "npm ci", "package-lock.json"
            return "npm install", "package.json"
    if (root / "uv.lock").is_file():
        return "uv sync --frozen", "uv.lock"
    if (root / "poetry.lock").is_file():
        return "poetry install", "poetry.lock"
    if (root / "Cargo.toml").is_file():
        return "cargo build", "Cargo.toml"
    if (root / "go.mod").is_file():
        return "go mod download", "go.mod"
    return "", ""


def detect_test_cmd(root: Path) -> tuple[str, str]:
    """Return (command, source file) for the test step; no-suite when none is found."""
    package = root / "package.json"
    if package.is_file():
        try:
            data = json.loads(package.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return "", "package.json (invalid JSON)"
        scripts = data.get("scripts")
        if isinstance(scripts, dict):
            script = scripts.get("test")
            if isinstance(script, str) and script.strip():
                return script.strip(), "package.json scripts.test"
    if (root / "Cargo.toml").is_file():
        return "cargo test", "Cargo.toml"
    if (root / "go.mod").is_file():
        return "go test ./...", "go.mod"
    pyproject = root / "pyproject.toml"
    if pyproject.is_file() and "pytest" in pyproject.read_text(encoding="utf-8"):
        return "pytest", "pyproject.toml"
    return NO_SUITE, "no test runner found"


def repo_setup_cmd(root: Path) -> str:
    return detect_setup_cmd(root)[0]


def repo_test_cmd(root: Path) -> str:
    return detect_test_cmd(root)[0]


def cmd_detect(root: Path) -> int:
    """Read-only: print the commands this repo suggests, each with its source."""
    for name, (value, source) in (
        ("TEST_CMD", detect_test_cmd(root)),
        ("SETUP_CMD", detect_setup_cmd(root)),
    ):
        print(f"{name} = {value or '(empty)'}  [source: {source or 'none found'}]")
    print("merge: no")
    return 0


def _read_card(root: Path, card_id: str) -> str:
    path = _task_file(root, card_id)
    if path is None or not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def _is_ancestor(root: Path, child: str, parent: str) -> bool:
    if not child or not parent:
        return False
    if not _branch_exists(root, child) or not _branch_exists(root, parent):
        return False
    proc = _run_git(root, ["merge-base", "--is-ancestor", child, parent])
    return proc.returncode == 0


def _gh(
    root: Path, args: list[str], timeout: float | None = None
) -> subprocess.CompletedProcess[str] | None:
    limit = (
        timeout
        if timeout is not None
        else _env_timeout("JT_GH_TIMEOUT", 5.0)
    )
    try:
        return subprocess.run(
            ["gh", *args],
            cwd=root,
            capture_output=True,
            text=True,
            env=_git_env(),
            timeout=limit,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


_BARE_TASK_HEAD_RE = re.compile(r"^task-(\d+(?:\.\d+)*)$")


def _head_matches(name: object, head: str, fuzzy: bool = False) -> bool:
    """name is head; with fuzzy (no branch for the task in this clone), a bare task-<id> also matches task-<id>-<slug>."""
    if not isinstance(name, str):
        return False
    if name == head:
        return True
    bare = _BARE_TASK_HEAD_RE.match(head) if fuzzy else None
    return bool(bare) and is_task_head(name, bare.group(1))


def task_branch_gone(root: Path, card_id: str) -> bool:
    """No local or remote-tracking branch for the task, so its slug is unknown here."""
    local, remote = task_branch_names(root, card_id)
    return not local and not remote


def _payload_mark(raw: str, head: str, fuzzy: bool = False) -> str:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return "missing"
    rows = data if isinstance(data, list) else [data]
    saw_open = False
    for row in rows:
        if not isinstance(row, dict) or not _head_matches(row.get("headRefName"), head, fuzzy):
            continue
        if row.get("state") == "MERGED":
            return "merged"
        if row.get("state") == "OPEN":
            saw_open = True
    return "open" if saw_open else "missing"


def _github_mark(root: Path, card_id: str) -> str:
    head = task_branch(root, card_id)
    fuzzy = task_branch_gone(root, card_id)
    view = _gh(root, ["pr", "view", head, "--json", "state,headRefName"])
    if view is not None and view.returncode == 0:
        mark = _payload_mark(view.stdout, head)
        if mark in {"merged", "open"}:
            return mark
    listed = _gh(
        root,
        [
            "pr",
            "list",
            "--head",
            head,
            "--state",
            "all",
            "--json",
            "state,headRefName",
        ],
    )
    if listed is not None and listed.returncode == 0:
        mark = _payload_mark(listed.stdout, head)
        if mark != "missing" or not fuzzy:
            return mark
    elif not fuzzy:
        return "missing"
    # The branch is gone from this clone, so its slug is unknown: look for task-<id>-<slug> among recent PRs.
    recent = _gh(root, ["pr", "list", "--state", "all", "--limit", "200", "--json", "state,headRefName"])
    if recent is None or recent.returncode != 0:
        return "missing"
    return _payload_mark(recent.stdout, head, fuzzy=True)


def landed_via(
    root: Path, card_id: str, queue: str, require_remote_for_gh: bool = False
) -> tuple[str, str]:
    if _is_ancestor(root, task_branch(root, card_id), queue):
        return "ancestor", ""
    if require_remote_for_gh and not _has_remote(root):
        return "", "pr-missing"
    mark = _github_mark(root, card_id)
    if mark == "merged":
        return "squash", ""
    return "", "pr-open" if mark == "open" else "pr-missing"


def _gh_merged_at(root: Path, head: str, fuzzy: bool = False) -> int | None:
    if fuzzy:
        args = ["pr", "list", "--state", "merged", "--limit", "200", "--json", "mergedAt,headRefName"]
    else:
        args = ["pr", "list", "--head", head, "--state", "merged", "--json", "mergedAt,headRefName"]
    proc = _gh(root, args)
    if proc is None or proc.returncode != 0:
        return None
    try:
        rows = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:
        return None
    for row in rows if isinstance(rows, list) else [rows]:
        if isinstance(row, dict) and _head_matches(row.get("headRefName"), head, fuzzy) and isinstance(row.get("mergedAt"), str):
            try:
                return int(datetime.fromisoformat(row["mergedAt"].replace("Z", "+00:00")).timestamp())
            except ValueError:
                return None
    return None


def _land_time(root: Path, card_id: str, queue: str, via: str) -> int | None:
    """When task-<id> reached queue: the first queue commit that contains it, or the PR merge time."""
    if via == "squash":
        return _gh_merged_at(root, task_branch(root, card_id), fuzzy=task_branch_gone(root, card_id))
    tip = _run_git(root, ["rev-parse", task_branch(root, card_id)]).stdout.strip()
    path = _run_git(root, ["rev-list", "--first-parent", "--ancestry-path", "--reverse", f"{tip}..{queue}"])
    first = path.stdout.split()[0] if path.returncode == 0 and path.stdout.split() else tip
    shown = _run_git(root, ["show", "-s", "--format=%ct", first])
    return int(shown.stdout.strip()) if shown.returncode == 0 and shown.stdout.strip().isdigit() else None


def land_order(card_text: str, repos: list[RepoSpec], names: list[str]) -> list[str]:
    """land: on the task, then the '## repos' order for repos it does not name."""
    wanted = [n for n in re.split(r"[\s,]+", _label(card_text, "land")) if n in names]
    rest = [repo.name for repo in repos if repo.name in names and repo.name not in wanted]
    return list(dict.fromkeys(wanted + rest + [n for n in names if n not in wanted + rest]))


def landed_across(
    root: Path, board_text: str, card_text: str, card_id: str, quick: bool = False
) -> tuple[bool, list[str], str] | None:
    """Landed state of a task in every repo it lists, or None for a home-only task."""
    repos = parse_repos(board_text)
    names = list(dict.fromkeys(card_repo_names(card_text)))
    home_name = next((repo.name for repo in repos if repo.is_home), "")
    if not repos or not names or names == [home_name]:
        return None
    by_name = {repo.name: repo for repo in repos}
    order = land_order(card_text, repos, names)
    states: dict[str, str] = {}
    times: dict[str, int | None] = {}
    for name in order:
        repo = by_name.get(name)
        if repo is None:
            states[name] = "unknown-repo"
            continue
        target = _repo_target(root, board_text, repo)
        if not target.root.is_dir():
            states[name] = "repo-missing"
            continue
        via, detail = landed_via(target.root, card_id, target.queue, require_remote_for_gh=quick)
        states[name] = via or detail
        if via and not quick:
            times[name] = _land_time(target.root, card_id, target.queue, via)
    lines = [f"landed-{name}: {states[name]}" for name in order]
    lines.append("land-order: " + ", ".join(order))
    waiting = [name for name in order if states[name] not in ("ancestor", "squash")]
    if waiting:
        return False, lines, "; ".join(f"{name}: {states[name]}" for name in waiting)
    for i, first in enumerate(order):
        for later in order[i + 1 :]:
            a, b = times.get(first), times.get(later)
            if a is not None and b is not None and b < a:
                lines.append(f"order-warning: {later} landed before {first}")
    return True, lines, ""


def cmd_landed(root: Path, card_id: str) -> int:
    if not valid_card_id(card_id):
        return _refuse("invalid-id")
    board_text = read_board_text(root)
    if board_text is None:
        return _refuse("board-missing")
    queue = parse_queue(board_text)
    if not queue:
        return _refuse("not-landed", detail="no-queue")
    across = landed_across(root, board_text, _read_card(root, card_id), card_id)
    if across is not None:
        ok, lines, detail = across
        if not ok:
            _refuse("not-landed", detail=detail)
            print("\n".join(lines))
            return 1
        print("\n".join(lines))
        print("landed: all")
        print("merge: no")
        return 0
    via, detail = landed_via(root, card_id, queue)
    if not via:
        return _refuse("not-landed", detail=detail)
    print(f"landed: {via}")
    print("merge: no")
    return 0


def _code_tip_sha(root: Path, queue: str, card_id: str) -> str | None:
    proc = _run_git(
        root,
        [
            "log",
            "-1",
            "--no-merges",
            "--format=%H",
            f"{queue}..{task_branch(root, card_id)}",
            "--",
            ".",
            ":(exclude)jt-queue",
        ],
    )
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def _card_worktree_drift(root: Path, card_id: str) -> bool:
    if _current_branch(root) != task_branch(root, card_id):
        return False
    proc = _run_git(
        root,
        ["status", "--porcelain", "--", ".", ":(exclude)jt-queue"],
    )
    if proc.returncode != 0:
        return True
    return bool(proc.stdout.strip())


def review_verdicts(section: str) -> list[str]:
    """Verdict values in a review-diff; a line holding '|' is the unfilled template and is ignored."""
    return [
        value.rstrip(".").strip().casefold()
        for value in _VERDICT_LINE.findall(section)
        if "|" not in value
    ]


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("`", "")).strip().casefold()


def _evidence_rows(plan: str) -> list[list[str]]:
    """Rows of the '## evidence' table that have three filled cells."""
    rows: list[list[str]] = []
    for line in _section_h2(plan, "evidence").splitlines():
        text = line.strip()
        if not text.startswith("|"):
            continue
        text = text[1:]
        if text.endswith("|") and not text.endswith("\\|"):
            text = text[:-1]
        cells = [cell.strip().replace("\\|", "|") for cell in re.split(r"(?<!\\)\|", text)]
        if len(cells) >= 3 and all(cells[:3]):
            rows.append(cells)
    return rows


def evidence_gaps(root: Path, card_id: str, plan: str) -> list[str]:
    """pass: lines of the task that no '## evidence' row quotes in its first cell."""
    firsts = [_norm(row[0]) for row in _evidence_rows(plan)]
    return [
        bullet
        for bullet in _header_bullets(_read_card(root, card_id))
        if not any(_norm(bullet) in first for first in firsts)
    ]


def card_repo_names(card_text: str) -> list[str]:
    raw = _label(card_text, "repos")
    return [name for name in re.split(r"[\s,]+", raw) if name and name != "-"]


@dataclass
class Target:
    name: str
    root: Path
    queue: str
    test_cmd: str
    setup_cmd: str


def _repo_target(home: Path, board_text: str, repo: RepoSpec) -> Target:
    if repo.is_home:
        return Target(
            repo.name,
            home,
            parse_queue(board_text),
            parse_field(board_text, "TEST_CMD"),
            parse_field(board_text, "SETUP_CMD"),
        )
    return Target(
        repo.name,
        repo_root(home, repo),
        repo.queue,
        repo.values.get("TEST_CMD", ""),
        repo.values.get("SETUP_CMD", ""),
    )


def card_targets(home: Path, board_text: str, card_text: str) -> list[Target] | None:
    """The repos a task works in, or None when it is a home-only (v22) task."""
    repos = parse_repos(board_text)
    names = card_repo_names(card_text)
    if not repos:
        if names:
            raise GateError("repo-invalid", "task.md names repos: but board.md has no '## repos'")
        return None
    home_name = next((repo.name for repo in repos if repo.is_home), "")
    if not names or names == [home_name]:
        return None
    by_name = {repo.name: repo for repo in repos}
    unknown = [name for name in names if name not in by_name]
    if unknown:
        raise GateError("repo-invalid", "repos: names a repo not in board.md: " + ", ".join(unknown))
    return [_repo_target(home, board_text, by_name[name]) for name in dict.fromkeys(names)]


def files_in_repo(card_text: str, repo: str, home_name: str) -> list[str]:
    """files: entries for one repo; `be:src/x` belongs to be, an unprefixed path to home."""
    picked: list[str] = []
    for entry in parse_files(card_text):
        head, sep, rest = entry.partition(":")
        if sep and REPO_NAME_RE.match(head) and not rest.startswith("//"):
            if head == repo:
                picked.append(rest.strip())
        elif repo == home_name:
            picked.append(entry)
    return picked


def undeclared_repos(home: Path, board_text: str, card_id: str, declared: list[str]) -> list[str]:
    """Repos outside repos: whose task-<id> branch changes code."""
    found: list[str] = []
    for repo in parse_repos(board_text):
        if repo.name in declared:
            continue
        target = _repo_target(home, board_text, repo)
        if target.root.is_dir() and _diff_names(target.root, target.queue, card_id):
            found.append(repo.name)
    return found


def _repo_sha_cited(section: str, name: str, sha: str) -> bool:
    pattern = re.compile(rf"^[\s>*-]*`?{re.escape(name)}`?:[ \t]*`?([0-9a-f]{{7,40}})", re.I | re.M)
    return any(sha.startswith(found.lower()) for found in pattern.findall(section))


def multi_review_detail(home: Path, card_id: str, targets: list[Target]) -> tuple[str, str]:
    """(status, repo) for a task across repos; repo names the one that failed, if any."""
    for target in targets:
        if not target.queue or not _branch_exists(target.root, task_branch(target.root, card_id)):
            return "no-review", target.name
        if _card_worktree_drift(target.root, card_id):
            return "stale-review", target.name
    plan = _read_queue_file(home, task_branch(home, card_id), _queue_rel("tasks", card_id, "plan.md")) or ""
    section = _section_h2(plan, "review-diff")
    if not section.strip():
        return "no-review", ""
    for target in targets:
        sha = _code_tip_sha(target.root, target.queue, card_id)
        if not sha:
            return "no-review", target.name
        if not _repo_sha_cited(section, target.name, sha):
            return "no-repo-sha", target.name
    verdicts = review_verdicts(section)
    if not verdicts or any(v not in {"pass", "fix-needed"} for v in verdicts):
        return "no-verdict", ""
    if "fix-needed" in verdicts:
        return "review-fix-needed", ""
    if _CHECKED_LINE.search(section) is None:
        return "no-checked", ""
    if evidence_gaps(home, card_id, plan):
        return "evidence-missing", ""
    return "ok", ""


def diff_review_detail(root: Path, card_id: str) -> str:
    if not valid_card_id(card_id):
        return "no-review"
    board_text = read_board_text(root)
    if board_text is None:
        return "no-review"
    try:
        targets = card_targets(root, board_text, _read_card(root, card_id))
    except GateError:
        return "no-review"
    if targets is not None:
        return multi_review_detail(root, card_id, targets)[0]
    queue = parse_queue(board_text)
    branch = task_branch(root, card_id)
    if not queue or not _branch_exists(root, branch):
        return "no-review"
    if not _code_diff_reviewable(root, queue, card_id):
        return "skip"
    if _card_worktree_drift(root, card_id):
        return "stale-review"
    sha = _code_tip_sha(root, queue, card_id)
    if not sha:
        return "no-review"
    plan = _read_queue_file(root, branch, _queue_rel("tasks", card_id, "plan.md")) or ""
    section = _section_h2(plan, "review-diff")
    if not section.strip():
        return "no-review"
    if _SHA.search(section) is None:
        return "no-sha"
    if sha not in section and sha[:7] not in section:
        return "stale-review"
    verdicts = review_verdicts(section)
    if not verdicts or any(v not in {"pass", "fix-needed"} for v in verdicts):
        return "no-verdict"
    if "fix-needed" in verdicts:
        return "review-fix-needed"
    if _CHECKED_LINE.search(section) is None:
        return "no-checked"
    if evidence_gaps(root, card_id, plan):
        return "evidence-missing"
    return "ok"


def diff_check_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gate.py diff-check")
    parser.add_argument("--root", default=".")
    parser.add_argument("--id", required=True)
    args = parser.parse_args(argv)
    if not valid_card_id(args.id):
        return _refuse("invalid-id")
    status = diff_review_detail(Path(args.root).resolve(), args.id)
    print(f"diff-check: {status}")
    return 0 if status in {"ok", "skip"} else 1


def _review_recorded(root: Path, queue: str, card_id: str) -> str | None:
    if not queue:
        return "no-review"
    detail = diff_review_detail(root, card_id)
    if detail == "ok":
        return None
    if detail in {"no-review", "no-sha", "stale-review", *REVIEW_DETAIL}:
        return detail
    return "no-review"


def _cards_from_text(root: Path, board_text: str) -> list[Card]:
    board = parse_board(board_text)
    bodies = {
        card.id: _read_card(root, card.id) or None
        for card in board.cards
    }
    return hydrate(board, bodies).cards


def _diff_names(root: Path, queue: str, card_id: str, added_only: bool = False) -> list[str] | None:
    if not queue or not _branch_exists(root, task_branch(root, card_id)):
        return None
    args = ["diff", "--name-only"]
    if added_only:
        args.append("--diff-filter=A")
    args.extend([f"{queue}...{task_branch(root, card_id)}", "--", ".", ":(exclude)jt-queue"])
    proc = _run_git(root, args)
    if proc.returncode != 0:
        return None
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def outside_card_files(
    root: Path, queue: str, card_id: str, card_text: str, repos: list[RepoSpec] | None = None
) -> list[str]:
    home_name = next((repo.name for repo in repos or [] if repo.is_home), "")
    listed = files_in_repo(card_text, home_name, home_name) if home_name else parse_files(card_text)
    declared = [f.strip().rstrip("/") for f in listed if f.strip()]
    if not declared:
        return []
    changed = _diff_names(root, queue, card_id)
    if not changed:
        return []
    outside: list[str] = []
    for path in changed:
        norm = path.strip().rstrip("/")
        if not any(norm == d or norm.startswith(d + "/") for d in declared):
            outside.append(path)
    return outside


def style_changes(
    root: Path, queue: str, card_id: str, board_text: str = ""
) -> list[str]:
    if not queue or not _branch_exists(root, task_branch(root, card_id)):
        return []
    kind = card_kind_at_merge_base(root, queue, card_id) or card_kind_in_board(
        board_text, card_id
    )
    if kind != "style":
        return []
    proc = _run_git(
        root,
        [
            "diff",
            "-w",
            "--ignore-blank-lines",
            "--numstat",
            f"{queue}...{task_branch(root, card_id)}",
            "--",
            ".",
            ":(exclude)jt-queue",
        ],
    )
    if proc.returncode != 0:
        return []
    changed: list[str] = []
    for line in proc.stdout.splitlines():
        parts = line.split("\t", 2)
        if len(parts) == 3 and (parts[0] != "0" or parts[1] != "0"):
            changed.append(parts[2].strip())
    return changed


def parse_needs(card_text: str) -> list[str]:
    needs: list[str] = []
    for line in _section_label(card_text, "needs:").splitlines():
        item = line.strip()[1:].strip() if line.strip().startswith("-") else ""
        if item:
            needs.append(item)
    return needs


def one_off_files(root: Path, queue: str, card_id: str, card_text: str) -> list[str]:
    added = _diff_names(root, queue, card_id, added_only=True)
    if not added:
        return []
    asked = _section_label(card_text, "do:")
    found: list[str] = []
    for path in added:
        name = path.rsplit("/", 1)[-1]
        if _CHECKER_BASENAME.match(name) is None:
            continue
        if name in asked or path in asked:
            continue
        found.append(path)
    return found


def one_off_checker(root: Path, queue: str, card_id: str, card_text: str) -> bool:
    return bool(one_off_files(root, queue, card_id, card_text))


def _has_remote(root: Path) -> bool:
    proc = _run_git(root, ["remote"])
    return proc.returncode == 0 and bool(proc.stdout.strip())


def classify_open_prs(prs: list[dict], head: str, base: str) -> tuple[str, str]:
    matches = [
        pr
        for pr in prs
        if isinstance(pr, dict) and pr.get("headRefName") == head
    ]
    if not matches:
        return ("ask", "pr-missing")
    if len(matches) > 1:
        return ("ask", "pr-duplicate")
    pr = matches[0]
    if pr.get("baseRefName") != base:
        return ("ask", "pr-base")
    if pr.get("isDraft") is not True:
        return ("ask", "pr-not-draft")
    url = pr.get("url")
    if not isinstance(url, str) or not url.strip():
        return ("ask", "pr-missing")
    return ("ok", url.strip())


def lookup_draft_pr(root: Path, head: str, base: str) -> tuple[str, str]:
    if not _has_remote(root):
        return ("local", "local")
    if shutil.which("gh") is None:
        return ("ask", "gh-missing")
    proc = _gh(
        root,
        [
            "pr",
            "list",
            "--head",
            head,
            "--state",
            "open",
            "--json",
            "url,isDraft,headRefName,baseRefName",
        ],
    )
    if proc is None or proc.returncode != 0:
        return ("ask", "pr-failed")
    try:
        data = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:
        return ("ask", "pr-failed")
    if not isinstance(data, list):
        return ("ask", "pr-failed")
    return classify_open_prs(data, head, base)


def _reach_review_multi(
    root: Path,
    card_id: str,
    write: bool,
    link: str,
    text: str,
    card_text: str,
    targets: list[Target],
    question_empty: bool,
) -> int:
    """reach-review for a task across repos: every listed repo must pass, others stay untouched."""
    names = [target.name for target in targets]
    extra = undeclared_repos(root, text, card_id, names)
    if extra:
        return _refuse("repo-undeclared", detail="task-<id> changes code in: " + ", ".join(extra))
    for target in targets:
        if not has_one_task_branch(target.root, card_id):
            return _refuse("task-branch-missing", detail=task_branch_missing_detail(target.root, card_id, target.name))
        if not _code_diff_reviewable(target.root, target.queue, card_id):
            return _refuse("review-diff", detail=f"repo {target.name}: no diff outside jt-queue/ to review")
    status, failed = multi_review_detail(root, card_id, targets)
    if status != "ok":
        where = f"repo {failed}: " if failed else ""
        note = f"{where}{status}: {REVIEW_DETAIL.get(status, 'review-diff is not recorded')}"
        if status == "evidence-missing":
            plan = _read_queue_file(root, task_branch(root, card_id), _queue_rel("tasks", card_id, "plan.md")) or ""
            note += ": " + "; ".join(evidence_gaps(root, card_id, plan))
        return _refuse("review-diff", detail=note)
    for target in targets:
        one_off = one_off_files(target.root, target.queue, card_id, card_text)
        if one_off:
            return _refuse(
                "one-off-checker", detail=f"repo {target.name}: new check script: " + ", ".join(one_off)
            )
    unapproved = _commands_refusal(root, text, card_id, card_text)
    if unapproved:
        return _refuse(unapproved[0], detail=unapproved[1])
    for target in targets:
        if target.test_cmd.strip() == "":
            return _refuse("test-cmd-empty", detail=f"repo {target.name}")
    need_screen = sees_screen(card_text)
    if need_screen and parse_field(text, "BROWSER_TOOL").strip() == "":
        return _refuse("browser-empty", detail="screen: yes needs <BROWSER_TOOL> in board.md")
    need_work = need_screen or any(t.test_cmd.strip() != NO_SUITE for t in targets)
    current = ""
    try:
        with ExitStack() as stack:
            works: dict[str, Path] = {}
            for target in targets if need_work else []:
                current = target.name
                works[target.name] = stack.enter_context(
                    _card_worktree(target.root, card_id, setup_cmd=target.setup_cmd)
                )
            current = ""
            if need_screen:
                _click_across(works, card_text, card_id)
            for target in targets:
                if target.test_cmd.strip() == NO_SUITE:
                    continue
                limit = _env_timeout("JT_TEST_TIMEOUT", float(TEST_TIMEOUT))
                code, out, timed_out = _run_shell(target.test_cmd, works[target.name], timeout=limit)
                if timed_out or code != 0:
                    detail, log_path = _record_command_log(root, card_id, f"{target.name}-test", out)
                    reason = "test-timeout" if timed_out else "test-failed"
                    return _refuse_round(root, card_id, reason, f"repo {target.name}:\n{detail}", log_path)
        if write:
            links: list[str] = []
            for target in targets:
                current = target.name
                kind, value = lookup_draft_pr(target.root, task_branch(target.root, card_id), target.queue)
                if kind == "ask":
                    return _refuse(value, detail=f"repo {target.name}")
                links.append(f"{target.name}:{value if kind == 'ok' else (link.strip() or 'local')}")
            current = ""
            updated = apply_waiting_review(
                text, card_id, 0, " ".join(links), question_empty=question_empty
            )
            (root / QUEUE_DIR / "board.md").write_text(updated, encoding="utf-8")
    except GateError as err:
        detail = f"repo {current}: {err.detail}" if current else err.detail
        if err.reason in ROUND_REASONS:
            return _refuse_round(root, card_id, err.reason, detail, err.log)
        return _refuse(err.reason, detail=detail, log=err.log)
    reset_rounds(root, card_id)
    print("allowed")
    print("merge: no")
    print("tier: standard")
    print("repo-review: open")
    print("repos: " + ", ".join(names))
    home_name = next((repo.name for repo in parse_repos(text) if repo.is_home), "")
    outside: list[str] = []
    for target in targets:
        declared = [f.rstrip("/") for f in files_in_repo(card_text, target.name, home_name) if f.strip()]
        if not declared:
            continue
        for path in _diff_names(target.root, target.queue, card_id) or []:
            norm = path.strip().rstrip("/")
            if not any(norm == d or norm.startswith(d + "/") for d in declared):
                outside.append(f"{target.name}:{path}")
    if outside:
        print("outside-files: " + ", ".join(outside))
    needs = parse_needs(card_text)
    if needs:
        print("needs: " + "; ".join(needs))
    return 0


def cmd_reach_review(root: Path, card_id: str, write: bool, link: str) -> int:
    if not valid_card_id(card_id):
        return _refuse("invalid-id")
    text = read_board_text(root)
    if text is None:
        return _refuse("board-missing")
    board_path = root / QUEUE_DIR / "board.md"
    queue = parse_queue(text)
    test_cmd = parse_field(text, "TEST_CMD")
    setup_cmd = parse_field(text, "SETUP_CMD")
    if write and (not queue or _current_branch(root) != queue):
        return _refuse("not-on-queue-branch")
    if test_cmd.strip() == "":
        return _refuse("test-cmd-empty")
    review_state = "skip"
    card_text = _read_card(root, card_id)
    question_empty = question_text(card_text) == ""
    if not question_empty:
        return _refuse("question-open")
    cards = _cards_from_text(root, text)
    current = next((card for card in cards if card.id == card_id), None)
    stopped = _related_stop(current, cards) if current is not None else None
    if stopped is not None:
        return _refuse(
            "related",
            detail="same-layer tasks without refs: links: " + ", ".join(stopped.ids),
        )
    repos = parse_repos(text)
    if repos:
        shape = repos_shape_problems(repos)
        if shape:
            return _refuse("repo-invalid", detail=", ".join(shape))
        problem = check_repos(root, repos)
        if problem:
            return _refuse(problem[0], detail=", ".join(problem[1]))
    try:
        targets = card_targets(root, text, card_text)
    except GateError as err:
        return _refuse(err.reason, detail=err.detail)
    if targets is not None:
        return _reach_review_multi(
            root, card_id, write, link, text, card_text, targets, question_empty
        )
    if repos:
        home_name = next(repo.name for repo in repos if repo.is_home)
        extra = undeclared_repos(root, text, card_id, [home_name])
        if extra:
            return _refuse("repo-undeclared", detail="task-<id> changes code in: " + ", ".join(extra))
    if not has_one_task_branch(root, card_id):
        return _refuse("task-branch-missing", detail=task_branch_missing_detail(root, card_id))
    tier = card_tier(root, queue, card_id, card_text, text)
    kinds = _commit_kinds(root, queue, card_id)
    if kinds is None:
        return _refuse("review-diff", detail="could not read the commits on task-<id> against queue:")
    if tier == "standard" and (
        _code_diff_reviewable(root, queue, card_id)
        or any(opens_repo_review(kind) for kind in kinds)
    ):
        if not _code_diff_reviewable(root, queue, card_id):
            return _refuse("review-diff", detail="no diff outside jt-queue/ to review")
        review_err = _review_recorded(root, queue, card_id)
        if review_err:
            note = f"{review_err}: {REVIEW_DETAIL.get(review_err, 'review-diff is not recorded')}"
            if review_err == "no-verdict":
                plan = _read_queue_file(root, task_branch(root, card_id), _queue_rel("tasks", card_id, "plan.md")) or ""
                seen = _VERDICT_LINE.findall(_section_h2(plan, "review-diff"))
                note += " (found: " + (", ".join(repr(v) for v in seen) or "no verdict line") + ")"
            if review_err == "evidence-missing":
                plan = _read_queue_file(root, task_branch(root, card_id), _queue_rel("tasks", card_id, "plan.md")) or ""
                note += ": " + "; ".join(evidence_gaps(root, card_id, plan))
            return _refuse("review-diff", detail=note)
        review_state = "open"
    one_off = one_off_files(root, queue, card_id, card_text)
    if one_off:
        return _refuse("one-off-checker", detail="new check script: " + ", ".join(one_off))
    unapproved = _commands_refusal(root, text, card_id, card_text)
    if unapproved:
        return _refuse(unapproved[0], detail=unapproved[1])
    try:
        need_screen = sees_screen(card_text)
        need_test = (test_cmd.strip() != NO_SUITE)
        if need_screen:
            browser = parse_field(text, "BROWSER_TOOL")
            if browser.strip() == "":
                return _refuse("browser-empty", detail="screen: yes needs <BROWSER_TOOL> in board.md")
        if need_screen or need_test:
            with _card_worktree(root, card_id, setup_cmd=setup_cmd) as work:
                if need_screen:
                    _click_surface(work, card_text, card_id)
                if need_test:
                    limit = _env_timeout("JT_TEST_TIMEOUT", float(TEST_TIMEOUT))
                    code, out, timed_out = _run_shell(test_cmd, work, timeout=limit)
                    if timed_out:
                        detail, log_path = _record_command_log(root, card_id, "test", out)
                        return _refuse_round(root, card_id, "test-timeout", detail, log_path)
                    if code != 0:
                        detail, log_path = _record_command_log(root, card_id, "test", out)
                        return _refuse_round(root, card_id, "test-failed", detail, log_path)
                else:
                    code = 0
        else:
            code = 0
        if write:
            kind, value = lookup_draft_pr(root, task_branch(root, card_id), queue)
            if kind == "ask":
                return _refuse(value)
            if kind == "ok":
                link = value
            updated = apply_waiting_review(
                text, card_id, code, link, question_empty=question_empty
            )
            board_path.write_text(updated, encoding="utf-8")
    except GateError as err:
        if err.reason in ROUND_REASONS:
            return _refuse_round(root, card_id, err.reason, err.detail, err.log)
        return _refuse(err.reason, detail=err.detail, log=err.log)
    reset_rounds(root, card_id)
    print("allowed")
    print("merge: no")
    print(f"tier: {tier}")
    print(f"repo-review: {review_state}")
    outside = outside_card_files(root, queue, card_id, card_text, repos)
    if outside:
        print("outside-files: " + ", ".join(outside))
    style_diff = style_changes(root, queue, card_id, text)
    if style_diff:
        print("style-changes: " + ", ".join(style_diff))
    needs = parse_needs(card_text)
    if needs:
        print("needs: " + "; ".join(needs))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] in MERGE_ARGV:
        sys.stderr.write("this gate cannot merge\n")
        print("refused: merge")
        print("merge: no")
        print(f"next: {NEXT_FOR['merge']}")
        return 2
    if args and args[0] == "diff-check":
        return diff_check_main(args[1:])
    if args and args[0] == "screen-check":
        return screen_check_main(args[1:])
    parser = argparse.ArgumentParser(prog="gate.py")
    sub = parser.add_subparsers(dest="cmd", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--root", default=".")

    sub.add_parser("next", parents=[common])
    ask_parser = sub.add_parser("ask", parents=[common])
    ask_parser.add_argument("--id", required=True)
    ask_parser.add_argument("--question", required=True)
    ask_parser.add_argument("--refused", default="")
    reach = sub.add_parser("reach-review", parents=[common])
    reach.add_argument("--id", required=True)
    reach.add_argument("--write", action="store_true")
    reach.add_argument("--link", default="")
    diff = sub.add_parser("diff-check", parents=[common])
    diff.add_argument("--id", required=True)
    screen = sub.add_parser("screen-check", parents=[common])
    screen.add_argument("--id", default="")
    screen.add_argument("--start", default="")
    screen.add_argument("--port", default="")
    screen.add_argument("--wait", default="")
    screen.add_argument("--browser", default="")
    screen.add_argument("--no-start", action="store_true")
    approve = sub.add_parser("approve-commands", parents=[common])
    approve.add_argument("--id", default="")
    sub.add_parser("detect", parents=[common])
    landed = sub.add_parser("landed", parents=[common])
    landed.add_argument("--id", required=True)

    parsed = parser.parse_args(args)
    root = Path(parsed.root).resolve()
    if parsed.cmd == "next":
        return cmd_next(root)
    if parsed.cmd == "ask":
        return cmd_ask(root, parsed.id, parsed.question, parsed.refused)
    if parsed.cmd == "reach-review":
        return cmd_reach_review(root, parsed.id, parsed.write, parsed.link)
    if parsed.cmd == "approve-commands":
        return cmd_approve_commands(root, parsed.id)
    if parsed.cmd == "detect":
        return cmd_detect(root)
    if parsed.cmd == "landed":
        return cmd_landed(root, parsed.id)
    return _refuse("merge")


if __name__ == "__main__":
    sys.exit(main())
