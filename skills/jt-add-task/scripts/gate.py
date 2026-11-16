#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
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
    "setup-board": "/jt-setup",
    "brief": "/jt-add-task",
    "add-task": "/jt-add-task",
    "do-task": "/jt-work",
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
    "lint-failed": "retry",
    "lint-timeout": "retry",
    "typecheck-failed": "retry",
    "typecheck-timeout": "retry",
    "setup-failed": "retry",
    "review-diff": "retry",
    "ai-review": "retry",
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
    "secret-suspect": "ask",
    "secret-failed": "ask",
    "secret-timeout": "ask",
    "deprecated-name": "retry",
    "verify-failed": "retry",
    "verify-timeout": "retry",
    "pass-ac": "retry",
    "spec-unapproved": "stop",
}
HINT_FOR = {
    "test-failed": "Read log:, fix the cause on the task branch (type/<ticket-id>-<slug>), commit, then run reach-review again.",
    "test-timeout": "The test command ran past its limit. Make it faster, or raise JT_TEST_TIMEOUT (max 3600 seconds).",
    "lint-failed": "Read log:, fix the lint failure on the task branch (type/<ticket-id>-<slug>), commit, then run reach-review again.",
    "lint-timeout": "The lint command ran past its limit. Make it faster, or raise JT_TEST_TIMEOUT (max 3600 seconds).",
    "typecheck-failed": "Read log:, fix the typecheck failure on the task branch (type/<ticket-id>-<slug>), commit, then run reach-review again.",
    "typecheck-timeout": "The typecheck command ran past its limit. Make it faster, or raise JT_TEST_TIMEOUT (max 3600 seconds).",
    "setup-failed": "SETUP_CMD failed in the task worktree. Read log:, then fix the command or the dependencies.",
    "review-diff": "Fix what detail: names in plan.md ('## review-diff' citing the latest code commit, or a missing '## evidence' row), then run gate.py diff-check.",
    "ai-review": (
        "Record one fresh-context review in '## ai-review' "
        "(accepted: or rejected: with a reason, or "
        "'fallback: no reviewer skill installed'), fix accepted findings, "
        "then run reach-review again."
    ),
    "one-off-checker": "Delete the new check script, or name it in do:. Use the check commands already on the board.",
    "task-branch-missing": "Commit the work on one branch named type/<ticket-id>-<slug> (legacy task-<id>-<slug> still works), then run reach-review again.",
    "merge-refused": "This gate cannot merge. Stop and report to the human.",
    "related": "Link each same-layer task under refs: in task.md, or run gate.py ask.",
    "browser-empty": "<BROWSER_TOOL> is empty in jt-queue/board.md. A human sets it; run gate.py ask.",
    "browser-missing": "No playwright or cypress was found. Install the project's browser tool, or run gate.py ask.",
    "browser-failed": "The browser command failed. Read its output above, fix the screen or the check, then retry.",
    "start-down": "Check start:, port:, and wait: in task.md and read log:. The app must listen on every port in port:.",
    "click-mismatch": "The click: command failed or is empty. Read log:, then fix the screen or the command.",
    "worktree-failed": "Git could not create a worktree for the task branch (type/<ticket-id>-<slug>). Resolve it, or run gate.py ask.",
    "pr-missing": "Push the task branch (type/<ticket-id>-<slug>) and open one draft pull request (head type/<ticket-id>-<slug>, base <queue>); see Handoff in SKILL.md.",
    "pr-duplicate": "Close the extra open PRs whose head is the task branch (type/<ticket-id>-<slug>) so exactly one remains.",
    "pr-base": "Retarget the open PR to the queue branch.",
    "pr-not-draft": "Convert the PR back to a draft, then run reach-review --write again.",
    "pr-failed": "gh could not list PRs. Check gh auth and network, or run gate.py ask.",
    "gh-missing": "Install the GitHub CLI (gh), or run gate.py ask.",
    "question-open": "The ask: line in task.md is still open. Wait for the human to answer it.",
    "board-missing": "Create jt-queue/board.md with /jt-setup first.",
    "commands-unapproved": "Stop. A human must review the commands and run approve-commands. Never run it yourself.",
    "commands-changed": "Stop. Show the human what changed; only the human runs approve-commands.",
    "not-on-queue-branch": "Check out the queue: branch named in board.md before using --write.",
    "test-cmd-empty": "<TEST_CMD> is empty in board.md. Ask the human to set it (or no-suite).",
    "unknown-status": "Fix the status token on that board line to one of ask:, review:, send-back:, merge:, drop:.",
    "task-line-missing": "That id has no open line on the board. Add the line or check the id.",
    "task-closed": "That task is already closed on the board. Pick another id.",
    "merge": "This gate cannot merge. Only a human merges, then records it with /jt-review.",
    "git-status-failed": "git status failed. Fix the repository state, then run the command again.",
    "invalid-id": "Task ids look like 1 or 1.2 and nothing else.",
    "repo-missing": "A repo under '## repos' in board.md is not a git repository at its path:. Clone it there or fix path:, then run again.",
    "repo-undeclared": "The task branch (type/<ticket-id>-<slug>) has commits in a repo the task does not list under repos:. Remove them, or run gate.py ask to add that repo to the task.",
    "repo-invalid": "Fix '## repos' in board.md: one '### <name>' per repo, exactly one with 'path: .' and nothing else, every other path: relative and distinct.",
    "secret-suspect": "Remove the named file from the branch and do not print its contents. If it must stay, run gate.py ask.",
    "secret-failed": "The secret scan failed. Fix the finding and do not print the value. If it must stay, run gate.py ask.",
    "secret-timeout": "The secret scan ran past its limit. Make it faster, or raise JT_TEST_TIMEOUT (max 3600 seconds).",
    "deprecated-name": "Replace the retired name with the replacement named in detail:, then run reach-review again.",
    "verify-failed": "Read log:, fix the verify failure on the task branch (type/<ticket-id>-<slug>), commit, then run reach-review again.",
    "verify-timeout": "The verify command ran past its limit. Make it faster, or raise JT_TEST_TIMEOUT (max 3600 seconds).",
    "pass-ac": "Write each pass: line as '- <id>: <Then>' copied from that AC or EC in spec:.",
    "spec-unapproved": "A human approves the spec (✅ name · date) after questions that block dev or AC are closed. Do not approve it yourself.",
}
MAX_ROUNDS = 3
ROUND_REASONS = frozenset(
    {
        "test-failed",
        "test-timeout",
        "setup-failed",
        "lint-failed",
        "lint-timeout",
        "typecheck-failed",
        "typecheck-timeout",
        "verify-failed",
        "verify-timeout",
    }
)
# Printed on allowed, in this order, so a reader does not have to guess which checks ran.
# The first six are the fail-fast steps: stop at the first failure and name the next one.
GATE_REPORT = (
    "secret",
    "denylist",
    "typecheck",
    "lint",
    "tests",
    "verify",
    "screen",
    "review-diff",
    "test-weakening",
)
FAIL_FAST = ("secret", "denylist", "typecheck", "lint", "tests", "verify")
# Process size is separate from the quick/standard tier. reach-review records it
# and may raise it. fresh-context-review is the ## ai-review check. The other
# two LARGE_SIZE_HOOKS names are still only printed.
SIZES = ("small", "medium", "large")
SIZE_RANK = {name: index for index, name in enumerate(SIZES)}
DEFAULT_DIFF_LIMIT = 400
LARGE_SIZE_HOOKS = ("worktree-rounds", "fresh-context-review", "high-risk")
_SIZE_TOKEN = re.compile(r"(?<!\S)size:\s*(small|medium|large)\b", re.IGNORECASE)
_AUTH_TOKEN = re.compile(
    r"^(?:auth(?:entication|enticat\w*)?|logins?|logouts?|sessions?|passwords?|passwds?|"
    r"credentials?|oauth|oidc|jwt|rbac|permissions?|acls?|signins?|signouts?|signups?)$",
    re.IGNORECASE,
)
_DATA_PARTS = frozenset({"migrations", "migration", "alembic", "flyway", "liquibase", "migrate"})
_CHECK_FAIL = {
    "test": "test-failed",
    "lint": "lint-failed",
    "typecheck": "typecheck-failed",
    "verify": "verify-failed",
}
_CHECK_TIMEOUT = {
    "test": "test-timeout",
    "lint": "lint-timeout",
    "typecheck": "typecheck-timeout",
    "verify": "verify-timeout",
}
_STEP_FOR_CHECK = {
    "test": "tests",
    "lint": "lint",
    "typecheck": "typecheck",
    "verify": "verify",
}
_HASHED_WHEN_SET = ("TYPECHECK_CMD", "LINT_CMD", "AFFECTED_TEST_CMD", "SECURITY_CMD", "VERIFY_CMD")
_PRIVATE_KEY_LINE = re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")
_SKIP_MARKER = re.compile(
    r"(?:\.skip\b|\.only\b|\bxit\s*\(|\bxdescribe\s*\(|\bxcontext\s*\(|"
    r"@pytest\.mark\.skip\b|@skip\b|\bpytest\.mark\.xfail\b|\bxfail\b|unittest\.skip\b)"
)
_PRIVATE_KEY_STEMS = frozenset({"id_rsa", "id_dsa", "id_ecdsa", "id_ed25519"})
_VERDICT_LINE = re.compile(r"^[\s>*-]*verdict:[ \t]*(.*?)[ \t]*$", re.IGNORECASE | re.MULTILINE)
_CHECKED_LINE = re.compile(r"^[\s>*-]*checked:[ \t]*\S", re.IGNORECASE | re.MULTILINE)
_AI_REVIEW_LINE = re.compile(
    r"^[\s>*-]*(accepted|rejected|fallback):[ \t]*(.*?)[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)
AI_REVIEW_FALLBACK = "no reviewer skill installed"
AI_REVIEW_MISSING = (
    "plan.md needs '## ai-review' with accepted: or rejected: plus a reason, "
    "or 'fallback: no reviewer skill installed'"
)
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
REPO_VALUES = (
    "TEST_CMD",
    "SETUP_CMD",
    "TYPECHECK_CMD",
    "LINT_CMD",
    "STACK_LOCK",
    "AFFECTED_TEST_CMD",
    "SECURITY_CMD",
    "VERIFY_CMD",
    "DENYLIST",
)
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


def _status_in(text: str) -> tuple[str | None, re.Match[str] | None]:
    """First status token, skipping a size: override on the same line."""
    for found in _COLON_TOKEN.finditer(text):
        token = f"{found.group(1)}:"
        if token == "size:":
            continue
        return token, found
    return None, None


def status_on_line(text: str) -> str | None:
    token, _found = _status_in(text)
    if token is None:
        return None
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
    token, found = _status_in(suffix)
    if token is None or found is None:
        return None, suffix_at, suffix_at
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
_BRANCH_TYPES = frozenset(
    {
        "feat",
        "fix",
        "chore",
        "docs",
        "refactor",
        "test",
        "perf",
        "ci",
        "build",
        "style",
        "revert",
    }
)


def _normalize_ticket_id(value: str) -> str:
    value = value.strip()
    if " #" in value:
        value = value.split(" #", 1)[0].rstrip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1].strip()
    return value


def ticket_id_in_card(card_text: str) -> str:
    for line in card_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("ticket:"):
            return _normalize_ticket_id(stripped.split(":", 1)[1])
    return ""


def _legacy_task_head(name: str, card_id: str) -> bool:
    """True for deprecated task-<id> or task-<id>-<slug> (slug: lowercase words joined by '-')."""
    bare = f"task-{card_id}"
    if name == bare:
        return True
    return name.startswith(bare + "-") and bool(_TASK_SLUG_RE.fullmatch(name[len(bare) + 1 :]))


def _conventional_task_head(name: str, ticket_id: str) -> bool:
    """True for type/<ticket-id>-<slug> or bare type/<ticket-id>."""
    if "/" not in name or not ticket_id:
        return False
    type_part, rest = name.split("/", 1)
    if type_part not in _BRANCH_TYPES:
        return False
    if rest == ticket_id:
        return True
    prefix = ticket_id + "-"
    if not rest.startswith(prefix):
        return False
    slug = rest[len(prefix) :]
    return bool(slug) and bool(_TASK_SLUG_RE.fullmatch(slug))


def is_task_head(name: str, card_id: str, ticket_id: str = "") -> bool:
    """Conventional type/<ticket-id>-<slug>, or legacy task-<id>[-<slug>]."""
    if _legacy_task_head(name, card_id):
        return True
    return _conventional_task_head(name, ticket_id)


def _branch_type(kind: str) -> str:
    return kind if kind in _BRANCH_TYPES else "feat"


def _default_task_branch(root: Path, card_id: str) -> str:
    ticket = ticket_id_in_card(_read_card(root, card_id))
    if ticket:
        board = read_board_text(root) or ""
        kind = _branch_type(card_kind_in_board(board, card_id))
        return f"{kind}/{ticket}"
    return f"task-{card_id}"


def task_branch_names(root: Path, card_id: str) -> tuple[list[str], list[str]]:
    """(local, remote-only) branch names that belong to the task, sorted."""
    if not valid_card_id(card_id):
        return [], []
    ticket_id = ticket_id_in_card(_read_card(root, card_id))
    proc = _run_git(
        root,
        ["for-each-ref", "--format=%(refname)", "refs/heads", "refs/remotes"],
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
            if is_task_head(name, card_id, ticket_id):
                bucket.add(name)
    return sorted(local), sorted(remote - local)


def task_branch(root: Path, card_id: str) -> str:
    """The task's branch: one local match, else one remote, else the conventional default."""
    local, remote = task_branch_names(root, card_id)
    if len(local) == 1:
        return local[0]
    if not local and len(remote) == 1:
        return remote[0]
    return _default_task_branch(root, card_id)


def has_one_task_branch(root: Path, card_id: str) -> bool:
    local, _remote = task_branch_names(root, card_id)
    return len(local) == 1


def task_branch_deprecation_note(root: Path, card_id: str) -> str:
    branch = task_branch(root, card_id)
    if _legacy_task_head(branch, card_id):
        return (
            "branch-deprecated: legacy task-<id> branch; "
            "prefer type/<ticket-id>-short-slug (see SKILL.md)"
        )
    return ""


def task_branch_missing_detail(root: Path, card_id: str, repo: str = "") -> str:
    local, _remote = task_branch_names(root, card_id)
    where = f"repo {repo}: " if repo else ""
    ticket = ticket_id_in_card(_read_card(root, card_id))
    if len(local) > 1:
        return f"{where}more than one branch for this task ({', '.join(local)}); keep one"
    if ticket:
        return (
            f"{where}no type/<ticket-id>-<slug> branch for ticket {ticket!r} "
            f"(legacy task-{card_id} or task-{card_id}-<slug> still accepted)"
        )
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
    # Empty LINT_CMD and TYPECHECK_CMD stay out, so a v22 approval of TEST/SETUP still matches.
    # A non-empty value is part of the hash: setting or editing it is commands-changed.
    commands = {
        "TEST_CMD": parse_field(board_text, "TEST_CMD"),
        "SETUP_CMD": parse_field(board_text, "SETUP_CMD"),
    }
    for name in _HASHED_WHEN_SET:
        value = parse_field(board_text, name)
        if value.strip():
            commands[name] = value
    for repo in parse_repos(board_text):
        if repo.is_home:
            continue
        # path: and queue: decide where the commands run, so they are approved with them.
        commands[f"repo:{repo.name}:path"] = repo.path
        commands[f"repo:{repo.name}:queue"] = repo.queue
        commands[f"repo:{repo.name}:TEST_CMD"] = repo.values.get("TEST_CMD", "")
        commands[f"repo:{repo.name}:SETUP_CMD"] = repo.values.get("SETUP_CMD", "")
        for name in _HASHED_WHEN_SET:
            value = repo.values.get(name, "")
            if value.strip():
                commands[f"repo:{repo.name}:{name}"] = value
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
        if name.endswith(("SETUP_CMD", "LINT_CMD", "TYPECHECK_CMD", "SECURITY_CMD", "VERIFY_CMD")) and value:
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
                "TEST_CMD/SETUP_CMD/LINT_CMD/TYPECHECK_CMD/AFFECTED_TEST_CMD/SECURITY_CMD/VERIFY_CMD (and any '## repos' entry) in jt-queue/board.md have not been approved on this machine. "
                "A human must review them, then run: gate.py approve-commands --root . --id " + card_id
            )
        if known != _digest(board_cmds):
            return "commands-changed", (
                "TEST_CMD/SETUP_CMD/LINT_CMD/TYPECHECK_CMD/AFFECTED_TEST_CMD/SECURITY_CMD/VERIFY_CMD (or a '## repos' path:, queue:, or command) in jt-queue/board.md changed since a human approved them. "
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


def _run_check(
    root: Path, card_id: str, work: Path, slug: str, command: str, repo: str = ""
) -> int | None:
    """Run one approved command. Return a refusal exit code, or None when it exits 0."""
    limit = _env_timeout("JT_TEST_TIMEOUT", float(TEST_TIMEOUT))
    code, out, timed_out = _run_shell(command, work, timeout=limit)
    if not timed_out and code == 0:
        return None
    log_slug = f"{repo}-{slug}" if repo else slug
    detail, log_path = _record_command_log(root, card_id, log_slug, out)
    reason = _CHECK_TIMEOUT[slug] if timed_out else _CHECK_FAIL[slug]
    note = f"repo {repo}:\n{detail}" if repo else detail
    return _refuse_round(root, card_id, reason, note, log_path, step=_STEP_FOR_CHECK[slug])


def _gates_line(results: dict[str, str]) -> str:
    return "gates: " + " · ".join(f"{name} {results[name]}" for name in GATE_REPORT)


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
                    ticket_id = ticket_id_in_card(_read_card(root, cid))
                    if (
                        _payload_mark(
                            listed.stdout,
                            head,
                            fuzzy=task_branch_gone(root, cid),
                            ticket_id=ticket_id,
                        )
                        == "merged"
                    ):
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


def _skipped_after(step: str) -> str:
    try:
        index = FAIL_FAST.index(step)
    except ValueError:
        return "none"
    if index + 1 >= len(FAIL_FAST):
        return "none"
    return FAIL_FAST[index + 1]


def _refuse_round(
    root: Path, card_id: str, reason: str, detail: str = "", log: str = "", step: str = ""
) -> int:
    rounds = count_round(root, card_id)
    note = f"round {min(rounds, MAX_ROUNDS)} of {MAX_ROUNDS}"
    if rounds >= MAX_ROUNDS:
        return _refuse(
            reason,
            detail=f"{detail}\n{note}: stop retrying and run gate.py ask with what each round tried".lstrip(),
            log=log,
            next_step="ask",
            step=step,
        )
    return _refuse(reason, detail=f"{detail}\n{note}".lstrip(), log=log, step=step)


def _refuse(
    reason: str, detail: str = "", log: str = "", next_step: str = "", step: str = ""
) -> int:
    print(f"refused: {reason}")
    print("merge: no")
    nxt = next_step or NEXT_FOR.get(reason)
    if nxt:
        print(f"next: {nxt}")
    if step:
        print(f"step: {step}")
        print(f"skipped: {_skipped_after(step)}")
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


_SPEC_MARKER = "<!-- scrum-spec"
_PASS_AC_LINE = re.compile(r"^((?:AC|EC)\d+)\s*:\s*(.*)$")
_SPEC_APPROVED = re.compile(r"^✅\s+(.+?)\s+·\s+(\d{4}-\d{2}-\d{2})\b")
_SPEC_AI = re.compile(r"\bAI\b|\b(?i:claude|chatgpt|gpt|copilot|gemini|codex|assistant)\b")
_QUEUE_TASK_FILE = re.compile(r"^jt-queue/tasks/(\d+(?:\.\d+)*)/(task|plan)\.md$")
_COMMIT_QUEUE = frozenset({"jt-queue/board.md", "jt-queue/brief.md"})
_OPEN_ANSWER = frozenset({"", "-", "–"})


def blocks_dev_or_ac(blocks: str) -> bool:
    """Same rule as check.py: Blocks names dev or AC."""
    return bool({"ac", "dev"} & set(re.findall(r"[A-Za-z]+", blocks.lower())))


def queue_context_class(rel: str) -> str:
    """How a queue path is shared: 'commit', 'local', or 'outside'.

    Commit the files a teammate needs to resume: board.md, brief.md,
    tasks/<id>/task.md, and tasks/<id>/plan.md (its ## decisions).
    Everything else under jt-queue/ or .git/jt-queue/ stays local:
    lessons.md (notes for this agent, not the task), approved-commands.json
    (permission to run shell commands; a commit must not carry it),
    logs/ (command output can hold secrets), attempts.json (this machine's
    round counter), plus any .env or private key that landed in the folder.
    """
    norm = rel.replace("\\", "/").strip()
    while norm.startswith("./"):
        norm = norm[2:]
    if norm in _COMMIT_QUEUE or _QUEUE_TASK_FILE.match(norm):
        return "commit"
    if norm.startswith("jt-queue/") or norm.startswith(".git/jt-queue/") or "/jt-queue/" in f"/{norm}":
        return "local"
    return "outside"


def _md_cells(line: str) -> list[str]:
    body = line.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|"):
        body = body[:-1]
    return [part.strip().replace("\\|", "|") for part in re.split(r"(?<!\\)\|", body)]


def _md_separator(line: str) -> bool:
    return bool(re.fullmatch(r"\|[\s:|-]+\|?", line.strip())) and "-" in line


def _norm_cell(text: str) -> str:
    return " ".join(text.split())


def _spec_raw(card_text: str) -> str:
    raw = _label(card_text, "spec").split("#", 1)[0].strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "`\"'":
        raw = raw[1:-1].strip()
    if raw in {"", "-", "–", "—"}:
        return ""
    return raw


def _spec_inside(root: Path, raw: str) -> Path | None:
    candidate = Path(raw)
    try:
        full = (candidate if candidate.is_absolute() else root / candidate).resolve()
        full.relative_to(root.resolve())
    except (OSError, ValueError):
        return None
    return full


def _read_spec_facts(text: str) -> tuple[str, dict[str, str], list[tuple[str, str]]]:
    """Approval value, id → Then, and open questions that block dev or AC."""
    lines = text.splitlines()
    section, fence = "", False
    approve = ""
    thens: dict[str, str] = {}
    blocking: list[tuple[str, str]] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.lstrip().startswith("```"):
            fence = not fence
            i += 1
            continue
        if not fence and line.startswith("## "):
            section = line[3:].strip()
            i += 1
            continue
        if not fence and section == "Acceptance Criteria" and line.startswith("**approve:**"):
            approve = line.split("**approve:**", 1)[1].strip()
        if not fence and line.lstrip().startswith("|") and i + 1 < len(lines) and _md_separator(lines[i + 1]):
            header = _md_cells(line)
            i += 2
            rows: list[list[str]] = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                rows.append(_md_cells(lines[i]))
                i += 1
            if section == "Acceptance Criteria":
                then_at = header.index("Then") if "Then" in header else 3
                for row in rows:
                    if not row or not re.fullmatch(r"(?:AC|EC)\d+", row[0]):
                        continue
                    thens[row[0]] = row[then_at] if then_at < len(row) else ""
            elif section == "Questions" and "Answer" in header:
                answer_at = header.index("Answer")
                blocks_at = header.index("Blocks") if "Blocks" in header else None
                for row in rows:
                    if not row:
                        continue
                    answer = row[answer_at] if answer_at < len(row) else ""
                    blocks = row[blocks_at] if blocks_at is not None and blocks_at < len(row) else ""
                    if answer in _OPEN_ANSWER and blocks_dev_or_ac(blocks):
                        blocking.append((row[0], blocks.strip()))
            continue
        i += 1
    return approve, thens, blocking


def trace_spec_pass(root: Path, card_text: str) -> dict[str, object] | tuple[str, str] | None:
    """Trace pass: lines to a spec, or None when the task has no spec:.

    A dict means the spec is approved and every pass line quotes an AC or EC Then.
    A (reason, detail) pair is pass-ac or spec-unapproved.
    """
    raw = _spec_raw(card_text)
    if not raw:
        return None
    full = _spec_inside(root, raw)
    if full is None or not full.is_file():
        return ("spec-unapproved", "spec: must be a file inside this repository")
    try:
        text = full.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return ("spec-unapproved", "spec: must be a file inside this repository")
    spec_lines = text.splitlines()
    if not spec_lines or not spec_lines[0].startswith(_SPEC_MARKER):
        return ("spec-unapproved", "spec must start with <!-- scrum-spec -->")
    approve, thens, blocking = _read_spec_facts(text)
    who = _SPEC_APPROVED.match(approve)
    if not approve.startswith("✅"):
        return ("spec-unapproved", "spec is not approved")
    if who is None:
        return ("spec-unapproved", "approval must read ✅ <name> · YYYY-MM-DD")
    if _SPEC_AI.search(who.group(1)):
        return ("spec-unapproved", "approval must come from a person, not an AI")
    if blocking:
        detail = "; ".join(f"approval is blocked while {qid} blocks {blocks}" for qid, blocks in blocking)
        return ("spec-unapproved", detail)
    bullets = _header_bullets(card_text)
    if not bullets:
        return ("pass-ac", "spec: is set but pass: has no line to trace")
    ids: list[str] = []
    for bullet in bullets:
        match = _PASS_AC_LINE.match(bullet)
        if match is None:
            return ("pass-ac", f"pass: line {bullet!r} does not name an AC id")
        ac_id, rest = match.group(1), _norm_cell(match.group(2))
        if ac_id not in thens:
            return ("pass-ac", f"pass: {ac_id} is not an AC or EC in {raw}")
        expected = _norm_cell(thens[ac_id])
        if rest != expected:
            return ("pass-ac", f"pass: {ac_id} must quote its Then ({expected!r})")
        ids.append(ac_id)
    return {"approval": f"{who.group(1)} · {who.group(2)}", "ids": ids}


def _print_spec_trace(root: Path, card_text: str) -> None:
    traced = trace_spec_pass(root, card_text)
    if not isinstance(traced, dict):
        return
    print(f"spec-approval: {traced['approval']}")
    ids = traced["ids"]
    print("pass-ac: " + ", ".join(ids if isinstance(ids, list) else []))


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


def _path_tokens(path: str) -> list[str]:
    return [token for token in re.split(r"[^A-Za-z0-9]+", path) if token]


def touches_auth(paths: list[str]) -> bool:
    """A changed path names auth. `author` does not."""
    return any(_AUTH_TOKEN.match(token) for path in paths for token in _path_tokens(path))


def touches_data(paths: list[str]) -> bool:
    """A migration directory, a migration filename, `.sql`, or `schema.prisma`."""
    for path in paths:
        pure = PurePosixPath(path)
        if pure.suffix.lower() == ".sql" or pure.name.lower() == "schema.prisma":
            return True
        parts = [part.lower() for part in pure.parts]
        if any(part in _DATA_PARTS for part in parts):
            return True
        tokens = [token.lower() for token in _path_tokens(pure.name)]
        if any(token in {"migration", "migrations"} for token in tokens):
            return True
    return False


def task_recorded_size(card_text: str) -> str:
    raw = _label(card_text, "size").lower()
    return raw if raw in SIZE_RANK else ""


def board_recorded_size(board_text: str, card_id: str) -> str:
    """The human override on the board line, if it names small, medium, or large."""
    if not valid_card_id(card_id):
        return ""
    found = re.search(rf"^- \[[ xX]\] \*\*{re.escape(card_id)}\*\*.*$", board_text, re.M)
    if not found:
        return ""
    match = _SIZE_TOKEN.search(found.group(0))
    return match.group(1).lower() if match else ""


def size_floor(card_text: str, board_text: str, card_id: str) -> str:
    """Board `size:` overrides the task. Unset stays medium, which is today's full gate."""
    return board_recorded_size(board_text, card_id) or task_recorded_size(card_text) or "medium"


def diff_limit(board_text: str) -> int:
    raw = parse_field(board_text, "DIFF_LIMIT").strip()
    if raw.isdigit():
        return int(raw)
    return DEFAULT_DIFF_LIMIT


def diff_line_count(root: Path, queue: str, card_id: str) -> int | None:
    text = _range_diff(root, queue, card_id, ["--numstat"])
    if text is None:
        return None
    total = 0
    for line in text.splitlines():
        added, deleted, _path = (line.split("\t", 2) + ["", ""])[:3]
        if added.isdigit() and deleted.isdigit():
            total += int(added) + int(deleted)
    return total


def path_triggers(paths: list[str], line_count: int, limit: int) -> list[str]:
    found: list[str] = []
    if touches_auth(paths):
        found.append("auth")
    if touches_data(paths):
        found.append("migrations")
    if line_count > limit:
        found.append("diff")
    return found


def raised_size(floor: str, triggers: list[str]) -> tuple[str, list[str]]:
    """Raise one step per trigger, never above large, and never below the floor."""
    rank = SIZE_RANK[floor]
    if not triggers or rank >= SIZE_RANK["large"]:
        return floor, []
    return SIZES[min(SIZE_RANK["large"], rank + len(triggers))], list(triggers)


def _source_stems(path: str) -> list[str]:
    stem = PurePosixPath(path).stem
    keys = [stem]
    if stem.endswith(".test"):
        keys.append(stem[: -len(".test")])
    elif stem.endswith(".spec"):
        keys.append(stem[: -len(".spec")])
    return keys


def affected_test_paths(changed: list[str], existing: list[str]) -> list[str]:
    """Test files in the diff, plus tests whose name matches a changed source file."""
    existing_set = set(existing)
    by_stem: dict[str, list[str]] = {}
    for path in existing:
        if not _is_test_path(path):
            continue
        for key in _source_stems(path):
            by_stem.setdefault(key, []).append(path)
    chosen: list[str] = []
    seen: set[str] = set()

    def take(path: str) -> None:
        if path in existing_set and path not in seen:
            seen.add(path)
            chosen.append(path)

    for path in changed:
        if _is_test_path(path):
            take(path)
            continue
        for key in _source_stems(path):
            for stem in (key, f"test_{key}", f"{key}_test", f"{key}.test", f"{key}.spec"):
                for candidate in by_stem.get(stem, []):
                    take(candidate)
    return chosen


def _tree_files(root: Path, card_id: str) -> list[str] | None:
    branch = task_branch(root, card_id)
    if not _branch_exists(root, branch):
        return None
    proc = _run_git(root, ["ls-tree", "-r", "--name-only", branch])
    if proc.returncode != 0:
        return None
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def _fill_files(command: str, paths: list[str]) -> str:
    quoted = " ".join(shlex.quote(path) for path in paths)
    return " ".join(command.replace("{files}", quoted).split())


def _full_suite(test_cmd: str) -> tuple[str | None, str]:
    """The suite command, with a `{files}` placeholder removed. None when there is no suite."""
    command = " ".join(test_cmd.replace("{files}", "").split())
    if command in ("", NO_SUITE):
        return None, "none"
    return command, "none -> full suite"


def test_command_for(
    size: str, test_cmd: str, paths: list[str], affected_cmd: str = ""
) -> tuple[str | None, str]:
    """The test command to run, and the `affected:` value for a small task.

    Above small, this is `<TEST_CMD>` unchanged. Small runs an affected command only
    when the board says how: a non-empty `<AFFECTED_TEST_CMD>`, or `{files}` in
    `<TEST_CMD>`. Otherwise, and when no affected test can be named, it runs the full
    suite. It never appends paths onto a command that did not ask for them, and it
    never skips a real suite because no test file matched.
    """
    full = test_cmd.strip()
    if size != "small":
        if full in ("", NO_SUITE):
            return None, ""
        return full, ""
    scoped = affected_cmd.strip()
    if scoped and "{files}" not in scoped:
        # The command selects its own tests (vitest --changed, pytest --testmon).
        return scoped, "command"
    if scoped and paths:
        return _fill_files(scoped, paths), ", ".join(paths)
    if not scoped and "{files}" in full and paths and full not in ("", NO_SUITE):
        return _fill_files(full, paths), ", ".join(paths)
    return _full_suite(full)


def collect_size(
    board_text: str,
    card_text: str,
    card_id: str,
    repos: list[tuple[str, Path, str]],
) -> tuple[str, str, list[str], list[str]]:
    """Floor, effective size, triggers that raised it, and affected test paths.

    With more than one repo, affected paths are prefixed `<repo>:`.
    """
    paths: list[str] = []
    total = 0
    for _name, root, queue in repos:
        paths.extend(_diff_names(root, queue, card_id) or [])
        total += diff_line_count(root, queue, card_id) or 0
    floor = size_floor(card_text, board_text, card_id)
    size, triggers = raised_size(floor, path_triggers(paths, total, diff_limit(board_text)))
    affected: list[str] = []
    if size == "small":
        many = len(repos) > 1
        for name, root, queue in repos:
            changed = _diff_names(root, queue, card_id) or []
            existing = _tree_files(root, card_id) or []
            for path in affected_test_paths(changed, existing):
                affected.append(f"{name}:{path}" if many and name else path)
    return floor, size, triggers, affected


def affected_for(affected: list[str], name: str, many: bool) -> list[str]:
    if not many:
        return affected
    prefix = f"{name}:"
    return [path[len(prefix) :] for path in affected if path.startswith(prefix)]


def print_size(floor: str, size: str, triggers: list[str], affected_note: str) -> None:
    print(f"size: {size}")
    if triggers:
        print(f"size-from: {floor}")
        print("escalate: " + ", ".join(triggers))
    if size == "small":
        print("affected: " + (affected_note or "none"))
    if size == "large":
        # worktree-rounds is recorded only. fresh-context-review is ## ai-review.
        # high-risk names when /jt-work may use ponytail-review; this line does not run it.
        print("size-hooks: " + ", ".join(LARGE_SIZE_HOOKS))


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
    parent = Path(tempfile.mkdtemp(prefix="jt-work-"))
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


def _head_matches(
    name: object, head: str, fuzzy: bool = False, *, ticket_id: str = ""
) -> bool:
    """name is head; with fuzzy, a bare head also matches the same task's slug branch."""
    if not isinstance(name, str):
        return False
    if name == head:
        return True
    if not fuzzy:
        return False
    bare = _BARE_TASK_HEAD_RE.match(head)
    if bare and is_task_head(name, bare.group(1), ticket_id):
        return True
    return (
        bool(ticket_id)
        and head.count("/") == 1
        and name.startswith(head + "-")
        and _conventional_task_head(name, ticket_id)
    )


def task_branch_gone(root: Path, card_id: str) -> bool:
    """No local or remote-tracking branch for the task, so its slug is unknown here."""
    local, remote = task_branch_names(root, card_id)
    return not local and not remote


def _payload_mark(raw: str, head: str, fuzzy: bool = False, *, ticket_id: str = "") -> str:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return "missing"
    rows = data if isinstance(data, list) else [data]
    saw_open = False
    for row in rows:
        if not isinstance(row, dict) or not _head_matches(
            row.get("headRefName"), head, fuzzy, ticket_id=ticket_id
        ):
            continue
        if row.get("state") == "MERGED":
            return "merged"
        if row.get("state") == "OPEN":
            saw_open = True
    return "open" if saw_open else "missing"


def _github_mark(root: Path, card_id: str) -> str:
    head = task_branch(root, card_id)
    fuzzy = task_branch_gone(root, card_id)
    ticket_id = ticket_id_in_card(_read_card(root, card_id))
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
    return _payload_mark(recent.stdout, head, fuzzy=True, ticket_id=ticket_id)


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


def _gh_merged_at(root: Path, head: str, fuzzy: bool = False, *, ticket_id: str = "") -> int | None:
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
        if (
            isinstance(row, dict)
            and _head_matches(row.get("headRefName"), head, fuzzy, ticket_id=ticket_id)
            and isinstance(row.get("mergedAt"), str)
        ):
            try:
                return int(datetime.fromisoformat(row["mergedAt"].replace("Z", "+00:00")).timestamp())
            except ValueError:
                return None
    return None


def _land_time(root: Path, card_id: str, queue: str, via: str) -> int | None:
    """When task-<id> reached queue: the first queue commit that contains it, or the PR merge time."""
    if via == "squash":
        ticket_id = ticket_id_in_card(_read_card(root, card_id))
        return _gh_merged_at(
            root,
            task_branch(root, card_id),
            fuzzy=task_branch_gone(root, card_id),
            ticket_id=ticket_id,
        )
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


def ai_review_recorded(section: str) -> bool:
    """True when ## ai-review has a real finding or the no-skill fallback.

    A copied template line that still contains '<' or '|' does not count.
    accepted and rejected need a reason after an em dash or ' - '.
    """
    for kind, rest in _AI_REVIEW_LINE.findall(section):
        text = rest.strip()
        if not text or "<" in text or "|" in text:
            continue
        if kind.casefold() == "fallback":
            if text.casefold() == AI_REVIEW_FALLBACK:
                return True
            continue
        if "—" in text:
            reason = text.split("—", 1)[1]
        elif " - " in text:
            reason = text.split(" - ", 1)[1]
        else:
            continue
        if reason.strip():
            return True
    return False


def ai_review_state(root: Path, card_id: str, size: str, tier: str) -> str:
    """'skip', 'open', or 'missing'.

    Standard medium and large need the section. Small and Quick do not.
    """
    if tier != "standard" or size == "small":
        return "skip"
    plan = _read_queue_file(
        root, task_branch(root, card_id), _queue_rel("tasks", card_id, "plan.md")
    ) or ""
    if ai_review_recorded(_section_h2(plan, "ai-review")):
        return "open"
    return "missing"


def _refuse_ai_review(size: str) -> int:
    return _refuse("ai-review", detail=f"no-ai-review: size {size}; {AI_REVIEW_MISSING}")


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
    lint_cmd: str = ""
    typecheck_cmd: str = ""
    affected_cmd: str = ""
    security_cmd: str = ""
    verify_cmd: str = ""
    denylist: str = ""


def _repo_target(home: Path, board_text: str, repo: RepoSpec) -> Target:
    if repo.is_home:
        return Target(
            repo.name,
            home,
            parse_queue(board_text),
            parse_field(board_text, "TEST_CMD"),
            parse_field(board_text, "SETUP_CMD"),
            parse_field(board_text, "LINT_CMD"),
            parse_field(board_text, "TYPECHECK_CMD"),
            parse_field(board_text, "AFFECTED_TEST_CMD"),
            parse_field(board_text, "SECURITY_CMD"),
            parse_field(board_text, "VERIFY_CMD"),
            parse_field(board_text, "DENYLIST"),
        )
    return Target(
        repo.name,
        repo_root(home, repo),
        repo.queue,
        repo.values.get("TEST_CMD", ""),
        repo.values.get("SETUP_CMD", ""),
        repo.values.get("LINT_CMD", ""),
        repo.values.get("TYPECHECK_CMD", ""),
        repo.values.get("AFFECTED_TEST_CMD", ""),
        repo.values.get("SECURITY_CMD", ""),
        repo.values.get("VERIFY_CMD", ""),
        repo.values.get("DENYLIST", ""),
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


def _range_diff(root: Path, queue: str, card_id: str, extra: list[str]) -> str | None:
    if not queue or not _branch_exists(root, task_branch(root, card_id)):
        return None
    proc = _run_git(
        root,
        ["diff", *extra, f"{queue}...{task_branch(root, card_id)}", "--", ".", ":(exclude)jt-queue"],
    )
    if proc.returncode != 0:
        return None
    return proc.stdout


def _is_secret_env_name(name: str) -> bool:
    return name != ".env.example" and name.startswith(".env")


def _is_private_key_name(name: str) -> bool:
    if name.endswith(".pub"):
        return False
    if name.endswith(".pem"):
        return True
    return name.split(".", 1)[0] in _PRIVATE_KEY_STEMS


def _added_paths(diff_status: str) -> list[str]:
    paths: list[str] = []
    for line in diff_status.splitlines():
        parts = line.split("\t")
        if len(parts) < 2 or not parts[0]:
            continue
        path = parts[-1].strip()
        if path and path != "/dev/null":
            paths.append(path)
    return paths


def secret_suspects(root: Path, queue: str, card_id: str) -> list[str] | None:
    """Added secret files and private-key lines. Paths only: never file contents."""
    listed = _range_diff(root, queue, card_id, ["--name-status", "--diff-filter=ACR"])
    if listed is None:
        return None
    names = [
        path
        for path in _added_paths(listed)
        if _is_secret_env_name(path.rsplit("/", 1)[-1]) or _is_private_key_name(path.rsplit("/", 1)[-1])
    ]
    body = _range_diff(root, queue, card_id, ["--unified=0", "--no-color"])
    if body is None:
        return None
    named = set(names)
    hits: list[str] = []
    path = ""
    new_line = 0
    for line in body.splitlines():
        if line.startswith("+++ "):
            raw = line[4:]
            if raw.startswith("b/"):
                raw = raw[2:]
            path = "" if raw == "/dev/null" else raw
            continue
        if line.startswith("@@"):
            match = re.search(r"\+(\d+)", line)
            new_line = int(match.group(1)) if match else 0
            continue
        if line.startswith("+") and not line.startswith("+++"):
            if path and path not in named and new_line and _PRIVATE_KEY_LINE.search(line):
                hits.append(f"{path}:{new_line}")
            if new_line:
                new_line += 1
    return sorted(set(names) | set(hits))


def _command_installed(command: str, root: Path | None = None) -> bool:
    """True when SECURITY_CMD's program is on PATH or is an executable path."""
    command = command.strip()
    if not command:
        return False
    try:
        argv = shlex.split(command, posix=True)
    except ValueError:
        return False
    if not argv:
        return False
    binary = argv[0]
    if "/" in binary or binary.startswith("."):
        path = Path(binary)
        if root is not None and not path.is_absolute():
            path = root / path
        return path.is_file() and os.access(path, os.X_OK)
    if shutil.which(binary) is not None:
        return True
    if root is None:
        return False
    local = root / "node_modules" / ".bin" / binary
    return local.is_file() and os.access(local, os.X_OK)


def _run_security_cmd(root: Path, card_id: str, command: str, repo: str = "") -> int | None:
    """Run SECURITY_CMD. Drop its output so a secret value is never printed."""
    limit = _env_timeout("JT_TEST_TIMEOUT", float(TEST_TIMEOUT))
    code, output, timed_out = _run_shell(command, root, timeout=limit)
    del output
    if not timed_out and code == 0:
        return None
    reason = "secret-timeout" if timed_out else "secret-failed"
    note = "secret scan failed"
    if repo:
        note = f"repo {repo}: {note}"
    return _refuse(reason, detail=note, step="secret")


def _suspect_refusal(
    root: Path, queue: str, card_id: str, repo: str = "", against_queue: bool = False
) -> int | None:
    found = secret_suspects(root, queue, card_id)
    if found is None:
        tail = " against queue:" if against_queue else ""
        where = f"repo {repo}: " if repo else ""
        return _refuse(
            "review-diff",
            detail=f"{where}could not read the diff on the task branch (type/<ticket-id>-<slug>){tail}",
        )
    if found:
        names = [f"{repo}:{item}" if repo else item for item in found]
        return _refuse("secret-suspect", detail=", ".join(names), step="secret")
    return None


def _scan_secret(
    root: Path,
    queue: str,
    card_id: str,
    command: str,
    repo: str = "",
    against_queue: bool = False,
) -> int | None:
    """TruffleHog (or whatever SECURITY_CMD names) when that program is installed, else secret-suspect."""
    if _command_installed(command, root):
        return _run_security_cmd(root, card_id, command, repo)
    return _suspect_refusal(root, queue, card_id, repo, against_queue)


def parse_denylist_text(text: str) -> list[tuple[str, str]]:
    """`old -> replacement` pairs. `;` separates pairs on one line. `#` starts a comment."""
    pairs: list[tuple[str, str]] = []
    for raw in text.replace(";", "\n").splitlines():
        line = raw.split("#", 1)[0].strip()
        if "->" not in line:
            continue
        old, _, new = line.partition("->")
        old, new = old.strip().strip("`"), new.strip().strip("`")
        if old and new:
            pairs.append((old, new))
    return pairs


def _path_inside(root: Path, raw: str) -> Path | None:
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        resolved = candidate.resolve()
        resolved.relative_to(root.resolve())
    except (OSError, ValueError):
        return None
    return resolved


def _pairs_from_spec(root: Path, spec: str) -> tuple[list[tuple[str, str]], str]:
    spec = spec.strip()
    if not spec:
        return [], ""
    if "->" not in spec:
        path = _path_inside(root, spec)
        if path is None:
            return [], "denylist path is outside the repo"
        if not path.is_file():
            return [], f"denylist file not found: {spec}"
        try:
            body = path.read_text(encoding="utf-8")
        except OSError:
            return [], f"denylist file not readable: {spec}"
        return parse_denylist_text(body), ""
    return parse_denylist_text(spec), ""


def load_denylist(
    root: Path, board_text: str, repo_cell: str = "", repo_root: Path | None = None
) -> tuple[list[tuple[str, str]], str]:
    """Pairs from `<DENYLIST>` or `jt-queue/denylist.txt`. Empty list means the step is skipped.

    A non-empty second value is an error message (missing file, path outside the repo).
    """
    pairs: list[tuple[str, str]] = []
    cell = parse_field(board_text, "DENYLIST").strip()
    if cell:
        found, err = _pairs_from_spec(root, cell)
        if err:
            return [], err
        pairs.extend(found)
    else:
        default = root / QUEUE_DIR / "denylist.txt"
        if default.is_file():
            found, err = _pairs_from_spec(root, f"{QUEUE_DIR}/denylist.txt")
            if err:
                return [], err
            pairs.extend(found)
    repo_cell = repo_cell.strip()
    if repo_cell and repo_root is not None:
        found, err = _pairs_from_spec(repo_root, repo_cell)
        if err:
            return [], err
        pairs.extend(found)
    unique: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for pair in pairs:
        if pair not in seen:
            seen.add(pair)
            unique.append(pair)
    return unique, ""


def denylist_hits(
    root: Path, queue: str, card_id: str, pairs: list[tuple[str, str]]
) -> list[str] | None:
    """Added diff lines and new paths that contain a retired name. The line text is not returned."""
    if not pairs:
        return []
    body = _range_diff(root, queue, card_id, ["--unified=0", "--no-color"])
    if body is None:
        return None
    patterns = [
        (
            re.compile(rf"(?<![A-Za-z0-9_]){re.escape(old)}(?![A-Za-z0-9_])"),
            old,
            new,
        )
        for old, new in pairs
    ]
    hits: list[str] = []
    seen: set[str] = set()
    path = ""
    new_line = 0

    def add(where: str, old: str, new: str) -> None:
        item = f"{old} -> {new} ({where})"
        if item not in seen:
            seen.add(item)
            hits.append(item)

    for line in body.splitlines():
        if line.startswith("+++ "):
            raw = line[4:]
            if raw.startswith("b/"):
                raw = raw[2:]
            path = "" if raw == "/dev/null" else raw
            if path:
                for pattern, old, new in patterns:
                    if pattern.search(path):
                        add(path, old, new)
            continue
        if line.startswith("@@"):
            match = re.search(r"\+(\d+)", line)
            new_line = int(match.group(1)) if match else 0
            continue
        if line.startswith("+") and not line.startswith("+++"):
            added = line[1:]
            if path and new_line:
                for pattern, old, new in patterns:
                    if pattern.search(added):
                        add(f"{path}:{new_line}", old, new)
            if new_line:
                new_line += 1
            continue
        if line.startswith(" ") and new_line:
            new_line += 1
    return hits


def _diff_unreadable(repo: str = "", against_queue: bool = False) -> int:
    tail = " against queue:" if against_queue else ""
    where = f"repo {repo}: " if repo else ""
    return _refuse(
        "review-diff",
        detail=f"{where}could not read the diff on the task branch (type/<ticket-id>-<slug>){tail}",
    )


def _deny_step(
    root: Path,
    queue: str,
    card_id: str,
    pairs: list[tuple[str, str]],
    repo: str = "",
    against_queue: bool = False,
) -> int | None:
    if not pairs:
        return None
    hits = denylist_hits(root, queue, card_id, pairs)
    if hits is None:
        return _diff_unreadable(repo, against_queue)
    if hits:
        shown = [f"{repo}:{hit}" if repo else hit for hit in hits]
        return _refuse("deprecated-name", detail="; ".join(shown), step="denylist")
    return None


def _is_test_path(path: str) -> bool:
    pure = PurePosixPath(path)
    if any(part in {"test", "tests", "__tests__"} for part in pure.parts[:-1]):
        return True
    name = pure.name
    if name.startswith("test_") and name.endswith(".py"):
        return True
    if name.endswith("_test.py") or name.endswith("_test.go"):
        return True
    return ".test." in name or ".spec." in name


def test_weakening(root: Path, queue: str, card_id: str) -> list[str] | None:
    """Deleted test files and added skip/only markers. Locations only, not the line text."""
    deleted = _range_diff(root, queue, card_id, ["--name-only", "--diff-filter=D"])
    if deleted is None:
        return None
    found = [
        f"deleted:{path.strip()}"
        for path in deleted.splitlines()
        if path.strip() and _is_test_path(path.strip())
    ]
    body = _range_diff(root, queue, card_id, ["--unified=0", "--no-color"])
    if body is None:
        return None
    path = ""
    new_line = 0
    for line in body.splitlines():
        if line.startswith("+++ "):
            raw = line[4:]
            if raw.startswith("b/"):
                raw = raw[2:]
            path = "" if raw == "/dev/null" else raw
            continue
        if line.startswith("@@"):
            match = re.search(r"\+(\d+)", line)
            new_line = int(match.group(1)) if match else 0
            continue
        if line.startswith("+") and not line.startswith("+++"):
            if path and new_line and _SKIP_MARKER.search(line):
                found.append(f"marker:{path}:{new_line}")
            if new_line:
                new_line += 1
    return sorted(set(found))


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
        return _refuse(
            "repo-undeclared",
            detail="the task branch (type/<ticket-id>-<slug>) changes code in: " + ", ".join(extra),
        )
    for target in targets:
        if not has_one_task_branch(target.root, card_id):
            return _refuse("task-branch-missing", detail=task_branch_missing_detail(target.root, card_id, target.name))
        if not _code_diff_reviewable(target.root, target.queue, card_id):
            return _refuse("review-diff", detail=f"repo {target.name}: no diff outside jt-queue/ to review")
    if any(_command_installed(target.security_cmd, target.root) for target in targets):
        unapproved = _commands_refusal(root, text, card_id, card_text)
        if unapproved:
            return _refuse(unapproved[0], detail=unapproved[1])
    for target in targets:
        refused = _scan_secret(target.root, target.queue, card_id, target.security_cmd, target.name)
        if refused is not None:
            return refused
    saw_denylist = False
    for target in targets:
        repo_cell = "" if target.root.resolve() == root.resolve() else target.denylist
        pairs, deny_err = load_denylist(root, text, repo_cell, target.root)
        if deny_err:
            return _refuse("deprecated-name", detail=f"repo {target.name}: {deny_err}", step="denylist")
        if pairs:
            saw_denylist = True
        refused = _deny_step(target.root, target.queue, card_id, pairs, target.name)
        if refused is not None:
            return refused
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
    floor, work_size, triggers, affected = collect_size(
        text,
        card_text,
        card_id,
        [(target.name, target.root, target.queue) for target in targets],
    )
    many = len(targets) > 1
    test_runs: dict[str, str | None] = {}
    affected_notes: list[str] = []
    for target in targets:
        command, note = test_command_for(
            work_size,
            target.test_cmd,
            affected_for(affected, target.name, many),
            target.affected_cmd,
        )
        test_runs[target.name] = command
        if note:
            affected_notes.append(f"{target.name}: {note}" if many else note)
    ran_test = any(test_runs.values())
    ran_lint = any(t.lint_cmd.strip() for t in targets)
    ran_type = any(t.typecheck_cmd.strip() for t in targets)
    ran_verify = any(t.verify_cmd.strip() for t in targets)
    need_work = need_screen or ran_test or ran_lint or ran_type or ran_verify
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
            for slug in ("typecheck", "lint", "test", "verify"):
                for target in targets:
                    command = {
                        "typecheck": target.typecheck_cmd,
                        "lint": target.lint_cmd,
                        "test": test_runs[target.name] or "",
                        "verify": target.verify_cmd,
                    }[slug]
                    if not command.strip():
                        continue
                    refused = _run_check(
                        root, card_id, works[target.name], slug, command, target.name
                    )
                    if refused is not None:
                        return refused
            if need_screen:
                _click_across(works, card_text, card_id)
        ai_state = ai_review_state(root, card_id, work_size, "standard")
        if ai_state == "missing":
            return _refuse_ai_review(work_size)
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
    note = task_branch_deprecation_note(root, card_id)
    if note:
        print(note)
    print("merge: no")
    print("tier: standard")
    print_size(floor, work_size, triggers, ", ".join(affected_notes))
    print(f"ai-review: {ai_state}")
    print("repo-review: open")
    print("repos: " + ", ".join(names))
    weak_bits: list[str] = []
    for target in targets:
        weak_bits.extend(
            f"{target.name}:{item}"
            for item in (test_weakening(target.root, target.queue, card_id) or [])
        )
    weak = ",".join(weak_bits) if weak_bits else "none"
    print(
        _gates_line(
            {
                "secret": "ok",
                "denylist": "ok" if saw_denylist else "skip",
                "typecheck": "ok" if ran_type else "skip",
                "lint": "ok" if ran_lint else "skip",
                "tests": "ok" if ran_test else "skip",
                "verify": "ok" if ran_verify else "skip",
                "screen": "ok" if need_screen else "skip",
                "review-diff": "open",
                "test-weakening": weak,
            }
        )
    )
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
    if weak != "none":
        print("test-weakening: " + weak)
    _print_spec_trace(root, card_text)
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
    traced = trace_spec_pass(root, card_text)
    if isinstance(traced, tuple):
        return _refuse(traced[0], detail=traced[1])
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
            return _refuse(
            "repo-undeclared",
            detail="the task branch (type/<ticket-id>-<slug>) changes code in: " + ", ".join(extra),
        )
    if not has_one_task_branch(root, card_id):
        return _refuse("task-branch-missing", detail=task_branch_missing_detail(root, card_id))
    tier = card_tier(root, queue, card_id, card_text, text)
    if _commit_kinds(root, queue, card_id) is None:
        return _refuse(
            "review-diff",
            detail="could not read the commits on the task branch (type/<ticket-id>-<slug>) against queue:",
        )
    security_cmd = parse_field(text, "SECURITY_CMD")
    if _command_installed(security_cmd, root):
        unapproved = _commands_refusal(root, text, card_id, card_text)
        if unapproved:
            return _refuse(unapproved[0], detail=unapproved[1])
    refused = _scan_secret(root, queue, card_id, security_cmd, against_queue=True)
    if refused is not None:
        return refused
    deny_pairs, deny_err = load_denylist(root, text)
    if deny_err:
        return _refuse("deprecated-name", detail=deny_err, step="denylist")
    refused = _deny_step(root, queue, card_id, deny_pairs, against_queue=True)
    if refused is not None:
        return refused
    if tier == "standard":
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
    lint_cmd = parse_field(text, "LINT_CMD")
    type_cmd = parse_field(text, "TYPECHECK_CMD")
    verify_cmd = parse_field(text, "VERIFY_CMD")
    ai_state = "skip"
    extra_checks: list[tuple[str, str]] = []
    if tier == "standard":
        if type_cmd.strip():
            extra_checks.append(("typecheck", type_cmd.strip()))
        if lint_cmd.strip():
            extra_checks.append(("lint", lint_cmd.strip()))
    floor, work_size, triggers, affected = collect_size(text, card_text, card_id, [("", root, queue)])
    test_to_run, affected_note = test_command_for(
        work_size, test_cmd, affected, parse_field(text, "AFFECTED_TEST_CMD")
    )
    try:
        need_screen = sees_screen(card_text)
        if need_screen:
            browser = parse_field(text, "BROWSER_TOOL")
            if browser.strip() == "":
                return _refuse("browser-empty", detail="screen: yes needs <BROWSER_TOOL> in board.md")
        if need_screen or test_to_run or extra_checks or verify_cmd.strip():
            with _card_worktree(root, card_id, setup_cmd=setup_cmd) as work:
                for slug, command in extra_checks:
                    refused = _run_check(root, card_id, work, slug, command)
                    if refused is not None:
                        return refused
                if test_to_run:
                    refused = _run_check(root, card_id, work, "test", test_to_run)
                    if refused is not None:
                        return refused
                if verify_cmd.strip():
                    refused = _run_check(root, card_id, work, "verify", verify_cmd.strip())
                    if refused is not None:
                        return refused
                if need_screen:
                    _click_surface(work, card_text, card_id)
        ai_state = ai_review_state(root, card_id, work_size, tier)
        if ai_state == "missing":
            return _refuse_ai_review(work_size)
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
    note = task_branch_deprecation_note(root, card_id)
    if note:
        print(note)
    print("merge: no")
    print(f"tier: {tier}")
    print_size(floor, work_size, triggers, affected_note)
    print(f"ai-review: {ai_state}")
    print(f"repo-review: {review_state}")
    found = test_weakening(root, queue, card_id) or []
    weak = ",".join(found) if found else "none"
    print(
        _gates_line(
            {
                "secret": "ok",
                "denylist": "ok" if deny_pairs else "skip",
                "typecheck": "ok" if any(slug == "typecheck" for slug, _cmd in extra_checks) else "skip",
                "lint": "ok" if any(slug == "lint" for slug, _cmd in extra_checks) else "skip",
                "tests": "ok" if test_to_run else "skip",
                "verify": "ok" if verify_cmd.strip() else "skip",
                "screen": "ok" if need_screen else "skip",
                "review-diff": "open" if review_state == "open" else "skip",
                "test-weakening": weak,
            }
        )
    )
    outside = outside_card_files(root, queue, card_id, card_text, repos)
    if outside:
        print("outside-files: " + ", ".join(outside))
    style_diff = style_changes(root, queue, card_id, text)
    if style_diff:
        print("style-changes: " + ", ".join(style_diff))
    needs = parse_needs(card_text)
    if needs:
        print("needs: " + "; ".join(needs))
    if weak != "none":
        print("test-weakening: " + weak)
    _print_spec_trace(root, card_text)
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
