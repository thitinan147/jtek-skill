#!/usr/bin/env python3

from __future__ import annotations

import argparse
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
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

NO_SUITE = "no-suite"
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
        "add-card",
        "do-card",
        "open-review",
        "wait",
        "stop",
    }
)
COMMAND_FOR = {
    "setup-board": "/jt-new-board",
    "brief": "/jt-ask-brief",
    "add-card": "/jt-new-card",
    "do-card": "/jt-do-work",
    "open-review": "/jt-open-work",
    "wait": "",
    "stop": "",
}
STATUS_TOKENS = ("review:", "send-back:", "ask:", "merge:", "drop:", "complete:")
SETUP_TIMEOUT = 900
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
_CLOSED = frozenset({"merge:", "drop:", "complete:"})
UNKNOWN_STATUS = "unknown:"
_STATUS_SET = frozenset(STATUS_TOKENS)
_COLON_TOKEN = re.compile(r"(?<!\S)([^\s:]+):")
_KIND_TAIL = re.compile(r"\([a-z]+\)\s*(.*)$")
_REF_ID = re.compile(r"(?<![\w.])(\d+(?:\.\d+)*)")
_SHA = re.compile(r"\b[0-9a-f]{7,40}\b", re.IGNORECASE)


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
    def __init__(self, reason: str, detail: str = "") -> None:
        self.reason = reason
        self.detail = detail
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


def parse_queue(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("queue:"):
            return line.split(":", 1)[1].strip()
    return ""


def parse_field(text: str, name: str) -> str:
    for line in text.splitlines():
        match = ROW_RE.match(line)
        if match and match.group(1) == name:
            return match.group(2).strip()
    return ""


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


def _is_parent(card: Card, cards: list[Card]) -> bool:
    prefix = card.id + "."
    return any(other.id.startswith(prefix) for other in cards)


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
        if _is_parent(card, cards) or _blocked(card, cards):
            continue
        chosen.append(card)
    return _ordered(chosen)


def _parent_ready(cards: list[Card]) -> Card | None:
    for card in _ordered(cards):
        if card.checked or card.section not in SECTION_RANK or not _is_parent(card, cards):
            continue
        if card.status is not None:
            continue
        children = [other for other in cards if other.id.startswith(card.id + ".")]
        if children and all(child.checked for child in children):
            return card
    return None


def _work(pool: list[Card], pred) -> Card | None:
    return next((card for card in pool if pred(card)), None)


def decide(
    board: Board | None,
    *,
    brief_exists: bool,
    dirty: bool,
    is_git: bool,
) -> Decision:
    if board is None:
        return Decision("setup-board", reason="no-board", command=COMMAND_FOR["setup-board"])
    missing: list[str] = []
    if not board.queue_branch:
        missing.append("queue")
    if board.test_cmd.strip() == "":
        missing.append("TEST_CMD")
    if board.stack_lock.strip() == "":
        missing.append("STACK_LOCK")
    if missing:
        return Decision("stop", reason="not-ready", fields=tuple(missing))
    if not is_git:
        return Decision("stop", reason="not-git")
    if dirty:
        return Decision("stop", reason="dirty")

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
    parent = _parent_ready(board.cards)
    if parent:
        return _take(board, parent, "subcards-complete")

    reviews = [
        card
        for card in _ordered(board.cards)
        if not card.checked and card.status == "review:" and card.section in SECTION_RANK
    ]
    if len(reviews) == 1:
        return Decision(
            "open-review",
            id=reviews[0].id,
            reason="review",
            command=COMMAND_FOR["open-review"],
            line=reviews[0].line,
        )
    if len(reviews) > 1:
        return Decision(
            "open-review",
            ids=tuple(card.id for card in reviews),
            reason="need-id",
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
        return Decision("add-card", reason="no-card", command=COMMAND_FOR["add-card"])
    unchecked = [
        card for card in board.cards if not card.checked and card.section in SECTION_RANK
    ]
    orphans = [
        card
        for card in unchecked
        if not card.has_card_file and not _is_parent(card, board.cards)
    ]
    if orphans:
        return Decision("stop", id=orphans[0].id, reason="no-card-file", line=orphans[0].line)
    if any(card.has_card_file and _blocked(card, board.cards) for card in unchecked):
        blocked = next(card for card in unchecked if _blocked(card, board.cards))
        return Decision("stop", id=blocked.id, reason="overlap", line=blocked.line)
    return Decision("stop", reason="queue-clear")


def _do(card: Card, reason: str) -> Decision:
    return Decision(
        "do-card",
        id=card.id,
        reason=reason,
        command=COMMAND_FOR["do-card"],
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
) -> str:
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
        raise GateError("card-line-missing")
    line = found[0].group(1)
    token, start, end = _status_span(line)
    if line.startswith("- [x]") or line.startswith("- [X]") or token in _CLOSED:
        raise GateError("card-closed")
    if token == UNKNOWN_STATUS:
        raise GateError("unknown-status")
    suffix = "review:" if not cleaned else f"review: {cleaned}"
    if token == "send-back:":
        new_line = f"{line[:start]}{suffix}{line[end:]}"
    elif token == "ask:":
        raise GateError("question-open")
    elif token == "review:":
        new_line = f"{line} {cleaned}" if cleaned and re.search(r"review:\s*$", line) else line
    elif token is None:
        new_line = f"{line} {suffix}"
    else:
        raise GateError("card-closed")
    if _has_boundary_token(new_line, "merge:"):
        raise GateError("merge-refused")
    start, end = found[0].start(1), found[0].end(1)
    return board_text[:start] + new_line + board_text[end:]


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


def _git_show(root: Path, spec: str) -> str | None:
    proc = _run_git(root, ["show", spec])
    if proc.returncode != 0:
        return None
    return proc.stdout


def _dirty(root: Path) -> bool:
    proc = _run_git(root, ["status", "--porcelain", "-z"])
    if proc.returncode != 0:
        return False
    parts = proc.stdout.split("\0")
    i = 0
    while i < len(parts):
        entry = parts[i]
        if not entry:
            i += 1
            continue
        status = entry[:2]
        path = entry[3:]
        if not path.startswith("card-loop/"):
            return True
        if ("R" in status or "C" in status) and i + 1 < len(parts):
            i += 1
            orig_path = parts[i]
            if not orig_path.startswith("card-loop/"):
                return True
        i += 1
    return False


def read_board_text(root: Path) -> str | None:
    path = root / "card-loop" / "board.md"
    work = path.read_text(encoding="utf-8") if path.is_file() else None
    if not _is_git(root):
        return work
    queue = parse_queue(work) if work else ""
    head = _current_branch(root)
    if queue and head != queue:
        shown = _git_show(root, f"{queue}:card-loop/board.md")
        if shown is not None:
            return shown
    if work is None:
        return _git_show(root, "HEAD:card-loop/board.md")
    return work


def _read_repo_file(root: Path, queue: str, rel: str) -> str | None:
    head = _current_branch(root) if _is_git(root) else ""
    if queue and head and head != queue:
        return _git_show(root, f"{queue}:{rel}")
    path = root / rel
    if path.is_file():
        return path.read_text(encoding="utf-8")
    if queue and _is_git(root):
        return _git_show(root, f"{queue}:{rel}")
    return None


def load_board(root: Path) -> tuple[Board | None, bool]:
    text = read_board_text(root)
    if text is None:
        return None, False
    board = parse_board(text)
    bodies = {
        card.id: _read_repo_file(root, board.queue_branch, f"card-loop/backlog/{card.id}.md")
        for card in board.cards
    }
    brief = _read_repo_file(root, board.queue_branch, "card-loop/brief.md")
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


def review_packet(root: Path, queue: str, card_id: str) -> dict[str, str | bool]:
    card = ""
    if queue:
        card = _git_show(root, f"{queue}:card-loop/backlog/{card_id}.md") or ""
    if not card:
        path = root / "card-loop" / "backlog" / f"{card_id}.md"
        card = path.read_text(encoding="utf-8") if path.is_file() else ""
    plan = _git_show(root, f"card-{card_id}:card-loop/plan/{card_id}.md") or ""
    header = _section_label(card, "pass:")
    diff_ok = False
    diff = ""
    if queue and _branch_exists(root, f"card-{card_id}"):
        proc = _run_git(root, ["diff", f"{queue}...card-{card_id}"])
        diff_ok = proc.returncode == 0
        diff = proc.stdout if diff_ok else ""
    compared = "pass diff" if header and diff_ok else "incomplete"
    return {
        "header": header,
        "decisions": _section_h2(plan, "decisions"),
        "review_diff": _section_h2(plan, "review-diff"),
        "evidence": _section_h2(plan, "evidence"),
        "diff": diff,
        "diff_ok": diff_ok,
        "compared": compared,
    }


def execute_test_cmd(root: Path, card_id: str, test_cmd: str, setup_cmd: str = "") -> int:
    command = test_cmd.strip()
    if command == "":
        raise GateError("test-cmd-empty")
    if not _branch_exists(root, f"card-{card_id}"):
        raise GateError("card-branch-missing")
    if command == NO_SUITE:
        return 0
    with _card_worktree(root, card_id, setup_cmd=setup_cmd) as work:
        return _run_shell(command, work)


def _env_with_bin(cwd: Path) -> dict[str, str]:
    env = _git_env()
    bin_dir = cwd / "node_modules" / ".bin"
    if bin_dir.is_dir():
        env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    return env


def _run_shell(command: str, cwd: Path, timeout: int | None = None) -> int:
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            env=_env_with_bin(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return proc.returncode
    except subprocess.TimeoutExpired:
        return 1


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


def format_packet(packet: dict[str, str | bool]) -> list[str]:
    diff = packet["diff"] if packet["diff_ok"] else "unreadable"
    return [
        f"compared: {packet['compared']}",
        "pass:",
        str(packet["header"] or "empty"),
        "decisions:",
        str(packet["decisions"] or "empty"),
        "review-diff:",
        str(packet.get("review_diff") or "empty"),
        "diff:",
        str(diff if str(diff).strip() else "empty"),
        "evidence:",
        str(packet["evidence"] or "empty"),
    ]


def cmd_next(root: Path) -> int:
    board, brief_exists = load_board(root)
    decision = decide(
        board,
        brief_exists=brief_exists,
        dirty=_dirty(root) if board is not None and _is_git(root) else False,
        is_git=True if board is None else _is_git(root),
    )
    extra = None
    if decision.action == "open-review" and decision.id and board is not None:
        extra = format_packet(review_packet(root, board.queue_branch, decision.id))
    emit(decision, extra)
    return 0


def _refuse(reason: str, step: str = "", detail: str = "") -> int:
    print(f"refused: {reason}")
    print("merge: no")
    if step:
        print(f"step: {step}")
    if detail:
        print(f"detail: {detail}")
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
    proc = _run_git(root, ["log", "--format=%s", f"{queue}..card-{card_id}"])
    if proc.returncode != 0:
        return None
    kinds: list[str] = []
    for line in proc.stdout.splitlines():
        match = KIND_RE.match(line.strip())
        if match:
            kinds.append(match.group(1))
    return kinds


def _code_diff_reviewable(root: Path, queue: str, card_id: str) -> bool:
    proc = _run_git(
        root,
        [
            "diff",
            "--name-only",
            f"{queue}...card-{card_id}",
            "--",
            ".",
            ":(exclude)card-loop",
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


def _run_while_up(work: Path, start: str, ports: list[int], wait_seconds: int, run) -> str | None:
    proc = subprocess.Popen(
        start,
        shell=True,
        cwd=work,
        start_new_session=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=_env_with_bin(work),
        text=True,
    )
    try:
        if not _wait_until_up(proc, ports, wait_seconds):
            return "start-down"
        return run()
    finally:
        _stop_process(proc)


def _click_surface(work: Path, card_text: str) -> str | None:
    start = _label(card_text, "start")
    port_text = _label(card_text, "port")
    click = _label(card_text, "click")
    wait_text = _label(card_text, "wait")
    wait_seconds = int(wait_text) if wait_text.isdigit() and int(wait_text) > 0 else 60
    ports = _parse_ports(port_text)
    if not start or ports is None:
        return "start-down"

    def run() -> str | None:
        if not click:
            return "click-mismatch"
        try:
            result = subprocess.run(
                click,
                shell=True,
                cwd=work,
                capture_output=True,
                text=True,
                env=_env_with_bin(work),
                timeout=300,
            )
        except subprocess.TimeoutExpired:
            return "click-mismatch"
        if result.returncode != 0:
            return "click-mismatch"
        return None

    return _run_while_up(work, start, ports, wait_seconds, run)


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
) -> int:
    argv = resolve_browser_argv(root, browser)
    if argv is None:
        print("screen-check: browser-missing")
        return 1
    if no_start or not start.strip():
        if _run_argv(argv, root) != 0:
            print("screen-check: browser-failed")
            return 1
        print("screen-check: ok")
        return 0
    parsed = _parse_ports(ports)
    if parsed is None:
        print("screen-check: start-down")
        return 1
    wait_seconds = int(wait) if wait.isdigit() and int(wait) > 0 else 60

    def run() -> str | None:
        if _run_argv(argv, root) != 0:
            return "browser-failed"
        return None

    reason = _run_while_up(root, start, parsed, wait_seconds, run)
    if reason:
        print(f"screen-check: {reason}")
        return 1
    print("screen-check: ok")
    return 0


def screen_check_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="jt-screen-check",
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
        board = root / "card-loop" / "board.md"
        text = board.read_text(encoding="utf-8") if board.is_file() else ""
        card = _read_card(root, args.id)
        if not browser:
            browser = parse_field(text, "BROWSER_TOOL")
        if not start:
            start = _label(card, "start")
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
    )


@contextmanager
def _card_worktree(root: Path, card_id: str, setup_cmd: str = ""):
    branch = f"card-{card_id}"
    if not _branch_exists(root, branch):
        raise GateError("card-branch-missing")
    if _current_branch(root) == branch:
        yield root
        return
    parent = Path(tempfile.mkdtemp(prefix="jt-next-step-"))
    worktree = parent / "card"
    try:
        added = _run_git(root, ["worktree", "add", "--detach", str(worktree), branch])
        if added.returncode != 0:
            raise GateError("worktree-failed", added.stderr.strip())
        if setup_cmd.strip():
            if _run_shell(setup_cmd.strip(), worktree, timeout=SETUP_TIMEOUT) != 0:
                raise GateError("setup-failed")
        yield worktree
    finally:
        _run_git(root, ["worktree", "remove", "--force", str(worktree)])
        shutil.rmtree(parent, ignore_errors=True)


def surface_refusal(
    root: Path, card_id: str, card_text: str, browser: str, setup_cmd: str = ""
) -> str | None:
    if not sees_screen(card_text):
        return None
    if browser.strip() == "":
        return "browser-empty"
    with _card_worktree(root, card_id, setup_cmd=setup_cmd) as work:
        return _click_surface(work, card_text)


def pair_name(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("pair:"):
            return line.split(":", 1)[1].strip()
    return ""


def _heading_has_pair(heading: str, pair: str) -> bool:
    if not pair or pair == "none":
        return False
    cut = _cut_known_status(heading)
    return re.search(rf"· {re.escape(pair)}(?=\s|\(|$)", cut) is not None


def card_names_pair(board_text: str, card_id: str, card_text: str = "") -> bool:
    pair = pair_name(board_text)
    line = ""
    found = re.findall(
        rf"^- \[[ xX]\] \*\*{re.escape(card_id)}\*\*.*$",
        board_text,
        re.M,
    )
    if len(found) == 1:
        line = found[0]
    title = next((row for row in card_text.splitlines() if row.startswith("# ")), "")
    return _heading_has_pair(line, pair) or _heading_has_pair(title, pair)


def locate_pair(primary: Path, name: str) -> Path | None:
    if not name or name == "none" or any(mark in name for mark in ("/", "\\", "\x00")):
        return None
    if name.strip() in {".", ".."}:
        return None
    parent = primary.resolve().parent
    other = (parent / name).resolve()
    if other.parent != parent or other == primary.resolve() or not other.is_dir():
        return None
    if not _is_git(other):
        return None
    return other


def repo_setup_cmd(root: Path) -> str:
    package = root / "package.json"
    if package.is_file():
        try:
            data = json.loads(package.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
        has_deps = bool(data.get("dependencies") or data.get("devDependencies"))
        if has_deps:
            if (root / "pnpm-lock.yaml").is_file():
                return "pnpm install --frozen-lockfile"
            if (root / "yarn.lock").is_file():
                return "yarn install --frozen-lockfile"
            if (root / "bun.lock").is_file() or (root / "bun.lockb").is_file():
                return "bun install --frozen-lockfile"
            if (root / "package-lock.json").is_file():
                return "npm ci"
            return "npm install"
    if (root / "uv.lock").is_file():
        return "uv sync --frozen"
    if (root / "poetry.lock").is_file():
        return "poetry install"
    if (root / "Cargo.toml").is_file():
        return "cargo build"
    if (root / "go.mod").is_file():
        return "go mod download"
    return ""


def repo_test_cmd(root: Path) -> str:
    package = root / "package.json"
    if package.is_file():
        try:
            data = json.loads(package.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return ""
        scripts = data.get("scripts")
        if isinstance(scripts, dict):
            script = scripts.get("test")
            if isinstance(script, str) and script.strip():
                return script.strip()
    if (root / "Cargo.toml").is_file():
        return "cargo test"
    if (root / "go.mod").is_file():
        return "go test ./..."
    pyproject = root / "pyproject.toml"
    if pyproject.is_file() and "pytest" in pyproject.read_text(encoding="utf-8"):
        return "pytest"
    return NO_SUITE


def pair_passed(primary: Path, name: str, card_id: str) -> bool:
    other = locate_pair(primary, name)
    if other is None:
        return False
    command = repo_test_cmd(other)
    if command == "":
        return False
    setup = repo_setup_cmd(other)
    try:
        return execute_test_cmd(other, card_id, command, setup_cmd=setup) == 0
    except GateError:
        return False


def _read_card(root: Path, card_id: str) -> str:
    path = root / "card-loop" / "backlog" / f"{card_id}.md"
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return ""


def _is_ancestor(root: Path, child: str, parent: str) -> bool:
    if not child or not parent:
        return False
    if not _branch_exists(root, child) or not _branch_exists(root, parent):
        return False
    proc = _run_git(root, ["merge-base", "--is-ancestor", child, parent])
    return proc.returncode == 0


def _gh(root: Path, args: list[str]) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            ["gh", *args],
            cwd=root,
            capture_output=True,
            text=True,
            env=_git_env(),
        )
    except FileNotFoundError:
        return None


def _payload_mark(raw: str, head: str) -> str:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return "missing"
    rows = data if isinstance(data, list) else [data]
    saw_open = False
    for row in rows:
        if not isinstance(row, dict) or row.get("headRefName") != head:
            continue
        if row.get("state") == "MERGED":
            return "merged"
        if row.get("state") == "OPEN":
            saw_open = True
    return "open" if saw_open else "missing"


def _github_mark(root: Path, card_id: str) -> str:
    head = f"card-{card_id}"
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
    if listed is None or listed.returncode != 0:
        return "missing"
    return _payload_mark(listed.stdout, head)


def landed_via(root: Path, card_id: str, queue: str) -> tuple[str, str]:
    if _is_ancestor(root, f"card-{card_id}", queue):
        return "ancestor", ""
    mark = _github_mark(root, card_id)
    if mark == "merged":
        return "squash", ""
    return "", "pr-open" if mark == "open" else "pr-missing"


def cmd_landed(root: Path, card_id: str) -> int:
    board_path = root / "card-loop" / "board.md"
    if not board_path.is_file():
        return _refuse("board-missing")
    queue = parse_queue(board_path.read_text(encoding="utf-8"))
    if not queue:
        return _refuse("not-landed", detail="no-queue")
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
            f"{queue}..card-{card_id}",
            "--",
            ".",
            ":(exclude)card-loop",
        ],
    )
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def _card_worktree_drift(root: Path, card_id: str) -> bool:
    if _current_branch(root) != f"card-{card_id}":
        return False
    proc = _run_git(
        root,
        ["status", "--porcelain", "--", ".", ":(exclude)card-loop"],
    )
    if proc.returncode != 0:
        return True
    return bool(proc.stdout.strip())


def diff_review_detail(root: Path, card_id: str) -> str:
    board_path = root / "card-loop" / "board.md"
    if not board_path.is_file():
        return "no-review"
    queue = parse_queue(board_path.read_text(encoding="utf-8"))
    branch = f"card-{card_id}"
    if not queue or not _branch_exists(root, branch):
        return "no-review"
    if not _code_diff_reviewable(root, queue, card_id):
        return "skip"
    if _card_worktree_drift(root, card_id):
        return "stale-review"
    sha = _code_tip_sha(root, queue, card_id)
    if not sha:
        return "no-review"
    plan = _git_show(root, f"{branch}:card-loop/plan/{card_id}.md") or ""
    section = _section_h2(plan, "review-diff")
    if not section.strip():
        return "no-review"
    if _SHA.search(section) is None:
        return "no-sha"
    if sha not in section and sha[:7] not in section:
        return "stale-review"
    return "ok"


def diff_check_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jt-diff-check")
    parser.add_argument("--root", default=".")
    parser.add_argument("--id", required=True)
    args = parser.parse_args(argv)
    status = diff_review_detail(Path(args.root).resolve(), args.id)
    print(f"diff-check: {status}")
    return 0 if status in {"ok", "skip"} else 1


def _diff_check_script() -> Path:
    return Path(__file__).resolve().parents[2] / "scripts" / "jt-diff-check"


def _review_recorded(root: Path, queue: str, card_id: str) -> str | None:
    if not queue:
        return "no-review"
    script = _diff_check_script()
    if not script.is_file():
        return "no-review"
    proc = subprocess.run(
        [sys.executable, str(script), "--root", str(root), "--id", card_id],
        cwd=root,
        capture_output=True,
        text=True,
        env=_git_env(),
    )
    detail = ""
    for line in proc.stdout.splitlines():
        if line.startswith("diff-check:"):
            detail = line.split(":", 1)[1].strip()
    if proc.returncode == 0 and detail == "ok":
        return None
    if detail in {"no-review", "no-sha", "stale-review"}:
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
    if not queue or not _branch_exists(root, f"card-{card_id}"):
        return None
    args = ["diff", "--name-only"]
    if added_only:
        args.append("--diff-filter=A")
    args.extend([f"{queue}...card-{card_id}", "--", ".", ":(exclude)card-loop"])
    proc = _run_git(root, args)
    if proc.returncode != 0:
        return None
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def _is_rule_path(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    folded = f"/{path.strip('/')}"
    if name in {"SKILL.md", "gate.py"}:
        return True
    if "/skills/" in folded or "/rules/" in folded:
        return True
    return _CHECKER_BASENAME.match(name) is not None


def _cited(path: str, section: str) -> bool:
    if path in section:
        return True
    name = path.rsplit("/", 1)[-1]
    if "/" in path and name in {"SKILL.md", "gate.py"}:
        return False
    return name in section


def one_off_checker(root: Path, queue: str, card_id: str, card_text: str) -> bool:
    added = _diff_names(root, queue, card_id, added_only=True)
    if not added:
        return False
    asked = _section_label(card_text, "do:")
    for path in added:
        name = path.rsplit("/", 1)[-1]
        if _CHECKER_BASENAME.match(name) is None:
            continue
        if name in asked or path in asked:
            continue
        return True
    return False


def repeat_patch_missing(root: Path, queue: str, card_id: str, cards: list[Card]) -> str:
    current = next((card for card in cards if card.id == card_id), None)
    if current is None:
        return ""
    siblings = _same_topic(current, cards)
    if not siblings:
        return ""
    plan = ""
    if _branch_exists(root, f"card-{card_id}"):
        plan = _git_show(root, f"card-{card_id}:card-loop/plan/{card_id}.md") or ""
    section = _section_h2(plan, "decisions")
    if "update-rule" not in section:
        return "no-row"
    names: list[str] = []
    for item in (current, *siblings):
        found = _diff_names(root, queue, item.id)
        if found:
            names.extend(found)
    if any(_is_rule_path(path) and _cited(path, section) for path in names):
        return ""
    return "prose-only"


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
    proc = subprocess.run(
        [
            "gh",
            "pr",
            "list",
            "--head",
            head,
            "--state",
            "open",
            "--json",
            "url,isDraft,headRefName,baseRefName",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        env=_git_env(),
    )
    if proc.returncode != 0:
        return ("ask", "pr-failed")
    try:
        data = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:
        return ("ask", "pr-failed")
    if not isinstance(data, list):
        return ("ask", "pr-failed")
    return classify_open_prs(data, head, base)


def cmd_reach_review(root: Path, card_id: str, write: bool, link: str) -> int:
    board_path = root / "card-loop" / "board.md"
    if not board_path.is_file():
        return _refuse("board-missing")
    text = board_path.read_text(encoding="utf-8")
    queue = parse_queue(text)
    test_cmd = parse_field(text, "TEST_CMD")
    setup_cmd = parse_field(text, "SETUP_CMD")
    if write and (not queue or _current_branch(root) != queue):
        return _refuse("not-on-queue-branch")
    if test_cmd.strip() == "":
        return _refuse("test-cmd-empty")
    review_state = "skip"
    card_text = _read_card(root, card_id)
    cards = _cards_from_text(root, text)
    current = next((card for card in cards if card.id == card_id), None)
    if current is not None and _related_stop(current, cards) is not None:
        return _refuse("related", "ask")
    if _branch_exists(root, f"card-{card_id}"):
        kinds = _commit_kinds(root, queue, card_id)
        if kinds is None:
            return _refuse("review-diff")
        if any(opens_repo_review(kind) for kind in kinds):
            if not _code_diff_reviewable(root, queue, card_id):
                return _refuse("review-diff")
            review_err = _review_recorded(root, queue, card_id)
            if review_err:
                return _refuse("review-diff", detail=review_err)
            review_state = "open"
        if one_off_checker(root, queue, card_id, card_text):
            return _refuse("one-off-checker")
        repeat = repeat_patch_missing(root, queue, card_id, cards)
        if repeat:
            return _refuse("repeat-patch", detail=repeat)
    try:
        need_screen = sees_screen(card_text)
        need_test = (test_cmd.strip() != NO_SUITE)
        if need_screen:
            browser = parse_field(text, "BROWSER_TOOL")
            if browser.strip() == "":
                return _refuse("browser-empty", "ask")
        if need_screen or need_test:
            with _card_worktree(root, card_id, setup_cmd=setup_cmd) as work:
                if need_screen:
                    reason = _click_surface(work, card_text)
                    if reason:
                        return _refuse(reason, "ask")
                if need_test:
                    code = _run_shell(test_cmd, work)
                    if code != 0:
                        return _refuse("test-failed")
                else:
                    code = 0
        else:
            code = 0
        if card_names_pair(text, card_id, card_text) and not pair_passed(
            root, pair_name(text), card_id
        ):
            return _refuse("pair-not-passed")
        if write:
            kind, value = lookup_draft_pr(root, f"card-{card_id}", queue)
            if kind == "ask":
                return _refuse(value, "ask")
            if kind == "ok":
                link = value
            updated = apply_waiting_review(text, card_id, code, link)
            board_path.write_text(updated, encoding="utf-8")
    except GateError as err:
        return _refuse(err.reason, detail=err.detail)
    print(f"repo-review: {review_state}")
    print("allowed")
    print("merge: no")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] in MERGE_ARGV:
        sys.stderr.write("this gate cannot merge\n")
        print("refused: merge")
        print("merge: no")
        return 2
    parser = argparse.ArgumentParser(prog="jt-next-step")
    sub = parser.add_subparsers(dest="cmd", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--root", default=".")

    sub.add_parser("next", parents=[common])
    reach = sub.add_parser("reach-review", parents=[common])
    reach.add_argument("--id", required=True)
    reach.add_argument("--write", action="store_true")
    reach.add_argument("--link", default="")
    landed = sub.add_parser("landed", parents=[common])
    landed.add_argument("--id", required=True)

    parsed = parser.parse_args(args)
    root = Path(parsed.root).resolve()
    if parsed.cmd == "next":
        return cmd_next(root)
    if parsed.cmd == "reach-review":
        return cmd_reach_review(root, parsed.id, parsed.write, parsed.link)
    if parsed.cmd == "landed":
        return cmd_landed(root, parsed.id)
    return _refuse("merge")


if __name__ == "__main__":
    sys.exit(main())
