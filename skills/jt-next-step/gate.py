#!/usr/bin/env python3
"""Read card-loop/board.md and take the next step the loop already allows.

The gate cannot merge. A failing test command cannot write รอรีวิว.
A code commit whose diff cannot be reviewed cannot write รอรีวิว.
Screen work that cannot be clicked cannot write รอรีวิว.
A new checker script the card did not ask for cannot write รอรีวิว.
The same open topic cannot write รอรีวิว until a rule or check script
is updated and the plan records it. Unlinked cards of that topic cannot
write รอรีวิว. A card whose heading names the paired repo cannot write
รอรีวิว until both sides have passed. The board line ไม่มี keeps the
single-repo path.
"""

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

NO_SUITE = "ไม่มีชุดเทส"
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
SECTION_RANK = {"ทำก่อน": 0, "งานหลัก": 1, "เก็บเล็ก": 2}
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
STATUS_TOKENS = ("รอรีวิว:", "ส่งกลับ:", "ถาม:", "merge:", "ไม่เอา:", "ครบ:", "ปิด:")
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
_CLOSED = frozenset({"merge:", "ไม่เอา:", "ครบ:"})
_REF_ID = re.compile(r"(?<![\w.])(\d+(?:\.\d+)*)")


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
        if line.startswith("สาขาคิว:"):
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
            section = line[3:].strip()
            continue
        match = CARD_RE.match(line)
        if not match or section not in SECTION_RANK:
            continue
        rest = match.group(3)
        kind_match = re.search(r"\([a-z]+\)\s*(.*)$", rest)
        suffix = kind_match.group(1) if kind_match else rest
        status = next((token for token in STATUS_TOKENS if token in suffix), None)
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
        if line.startswith("ถาม:"):
            return line[len("ถาม:") :].strip()
    return ""


def parse_files(card_text: str) -> list[str]:
    collecting = False
    files: list[str] = []
    for line in card_text.splitlines():
        if line.startswith("ไฟล์ที่แตะได้:"):
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
        card.topic = _label(body, "ชั้น")
        card.refs = parse_refs(body)
    return board


def parse_refs(card_text: str) -> tuple[str, ...]:
    found: list[str] = []
    for line in _section_label(card_text, "อ้างอิง:").splitlines():
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
        if other.status in {"รอรีวิว:", "ส่งกลับ:"} and _overlaps(card.files, other.files):
            return True
    return False


def _ordered(cards: list[Card]) -> list[Card]:
    return sorted(cards, key=lambda card: (SECTION_RANK.get(card.section, 9), card.index))


def _pool(cards: list[Card]) -> list[Card]:
    higher_open = any(
        (not card.checked) and card.section in {"ทำก่อน", "งานหลัก"} for card in cards
    )
    chosen: list[Card] = []
    for card in cards:
        if card.checked or card.section not in SECTION_RANK:
            continue
        if card.section == "เก็บเล็ก" and higher_open:
            continue
        if _is_parent(card, cards) or _blocked(card, cards):
            continue
        chosen.append(card)
    return _ordered(chosen)


def _parent_ready(cards: list[Card]) -> Card | None:
    for card in _ordered(cards):
        if card.checked or card.section not in SECTION_RANK or not _is_parent(card, cards):
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
        missing.append("สาขาคิว")
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

    pool = _pool(board.cards)
    send_back = _work(pool, lambda card: card.status == "ส่งกลับ:" and card.has_card_file)
    if send_back:
        return _take(board, send_back, "send-back")
    cleared = _work(
        pool,
        lambda card: card.status == "ถาม:" and card.question_empty and card.has_card_file,
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
        if not card.checked and card.status == "รอรีวิว:" and card.section in SECTION_RANK
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
        if not card.checked and card.status == "ถาม:" and not card.question_empty
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
    if cleaned == "merge" or "merge:" in cleaned:
        raise GateError("merge-refused")
    pattern = re.compile(
        rf"^(- \[[ xX]\] \*\*{re.escape(card_id)}\*\*.*)$",
        re.M,
    )
    found = list(pattern.finditer(board_text))
    if len(found) != 1:
        raise GateError("card-line-missing")
    line = found[0].group(1)
    if (
        line.startswith("- [x]")
        or line.startswith("- [X]")
        or "ปิด:" in line
        or "ไม่เอา:" in line
        or "ครบ:" in line
        or re.search(r"(^|\s)merge:", line)
    ):
        raise GateError("card-closed")
    suffix = "รอรีวิว:" if not cleaned else f"รอรีวิว: {cleaned}"
    if "ส่งกลับ:" in line:
        new_line = line.replace("ส่งกลับ:", suffix, 1)
    elif "ถาม:" in line:
        raise GateError("question-open")
    elif "รอรีวิว:" in line:
        new_line = f"{line} {cleaned}" if cleaned and re.search(r"รอรีวิว:\s*$", line) else line
    else:
        new_line = f"{line} {suffix}"
    if re.search(r"(^|\s)merge:", new_line):
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
    header = _section_label(card, "ตรวจผ่านเมื่อ:")
    diff_ok = False
    diff = ""
    if queue and _branch_exists(root, f"card-{card_id}"):
        proc = _run_git(root, ["diff", f"{queue}...card-{card_id}"])
        diff_ok = proc.returncode == 0
        diff = proc.stdout if diff_ok else ""
    compared = "ตรวจผ่านเมื่อ diff" if header and diff_ok else "incomplete"
    return {
        "header": header,
        "decisions": _section_h2(plan, "การตัดสินใจ"),
        "review_diff": _section_h2(plan, "รีวิว diff"),
        "evidence": _section_h2(plan, "หลักฐานก่อนเปิดของให้ review"),
        "diff": diff,
        "diff_ok": diff_ok,
        "compared": compared,
    }


def execute_test_cmd(root: Path, card_id: str, test_cmd: str, setup_cmd: str = "") -> int:
    """Run TEST_CMD on card-<id>. ไม่มีชุดเทส is not a command."""
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
        print(f"ถาม: {decision.question}")
    if extra:
        print("\n".join(extra))


def format_packet(packet: dict[str, str | bool]) -> list[str]:
    diff = packet["diff"] if packet["diff_ok"] else "อ่านไม่ได้"
    return [
        f"compared: {packet['compared']}",
        "ตรวจผ่านเมื่อ:",
        str(packet["header"] or "ว่าง"),
        "การตัดสินใจ:",
        str(packet["decisions"] or "ว่าง"),
        "รีวิว diff:",
        str(packet.get("review_diff") or "ว่าง"),
        "diff:",
        str(diff if str(diff).strip() else "ว่าง"),
        "ผลเทส:",
        str(packet["evidence"] or "ว่าง"),
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
    return _label(card_text, "เห็นจอ") == "ใช่"


def _header_bullets(card_text: str) -> list[str]:
    bullets: list[str] = []
    for line in _section_label(card_text, "ตรวจผ่านเมื่อ:").splitlines():
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


def _click_surface(work: Path, card_text: str) -> str | None:
    start = _label(card_text, "เริ่ม")
    port_text = _label(card_text, "พอร์ต")
    click = _label(card_text, "คลิก")
    wait_text = _label(card_text, "รอ")
    wait_seconds = int(wait_text) if wait_text.isdigit() and int(wait_text) > 0 else 60

    if not start or not port_text:
        return "start-down"
    ports: list[int] = []
    for piece in re.split(r"[,\s]+", port_text.strip()):
        if not piece:
            continue
        if not piece.isdigit():
            return "start-down"
        p = int(piece)
        if p < 1 or p > 65535:
            return "start-down"
        ports.append(p)
    if not ports:
        return "start-down"

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
    finally:
        _stop_process(proc)


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
        if line.startswith("คู่:"):
            return line.split(":", 1)[1].strip()
    return ""


def _heading_has_pair(heading: str, pair: str) -> bool:
    if not pair or pair == "ไม่มี":
        return False
    cut = heading
    for token in STATUS_TOKENS:
        index = cut.find(token)
        if index != -1:
            cut = cut[:index]
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
    if not name or name == "ไม่มี" or any(mark in name for mark in ("/", "\\", "\x00")):
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


def _review_recorded(root: Path, queue: str, card_id: str) -> str | None:
    head_proc = _run_git(
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
    if head_proc.returncode != 0:
        return "no-review"
    head_sha = head_proc.stdout.strip()
    if not head_sha:
        return None
    plan = _git_show(root, f"card-{card_id}:card-loop/plan/{card_id}.md") or ""
    section = _section_h2(plan, "รีวิว diff")
    if not section.strip():
        return "no-review"
    if head_sha[:7] not in section:
        return "stale-review"
    return None


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
    """A new check/lint/verify script the card's ทำ section did not name."""
    added = _diff_names(root, queue, card_id, added_only=True)
    if not added:
        return False
    asked = _section_label(card_text, "ทำ:")
    for path in added:
        name = path.rsplit("/", 1)[-1]
        if _CHECKER_BASENAME.match(name) is None:
            continue
        if name in asked or path in asked:
            continue
        return True
    return False


def repeat_patch_missing(root: Path, queue: str, card_id: str, cards: list[Card]) -> bool:
    """Same open topic, and no recorded update to a rule or check script."""
    current = next((card for card in cards if card.id == card_id), None)
    if current is None:
        return False
    siblings = _same_topic(current, cards)
    if not siblings:
        return False
    plan = ""
    if _branch_exists(root, f"card-{card_id}"):
        plan = _git_show(root, f"card-{card_id}:card-loop/plan/{card_id}.md") or ""
    section = _section_h2(plan, "การตัดสินใจ")
    if "อัปเดตกติกา" not in section:
        return True
    names: list[str] = []
    for item in (current, *siblings):
        found = _diff_names(root, queue, item.id)
        if found:
            names.extend(found)
    return not any(_is_rule_path(path) and _cited(path, section) for path in names)


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
        return _refuse("related", "ถาม")
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
        if repeat_patch_missing(root, queue, card_id, cards):
            return _refuse("repeat-patch")
    try:
        need_screen = sees_screen(card_text)
        need_test = (test_cmd.strip() != NO_SUITE)
        if need_screen:
            browser = parse_field(text, "BROWSER_TOOL")
            if browser.strip() == "":
                return _refuse("browser-empty", "ถาม")
        if need_screen or need_test:
            with _card_worktree(root, card_id, setup_cmd=setup_cmd) as work:
                if need_screen:
                    reason = _click_surface(work, card_text)
                    if reason:
                        return _refuse(reason, "ถาม")
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
        sys.stderr.write("เกตนี้ merge ไม่ได้\n")
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

    parsed = parser.parse_args(args)
    root = Path(parsed.root).resolve()
    if parsed.cmd == "next":
        return cmd_next(root)
    if parsed.cmd == "reach-review":
        return cmd_reach_review(root, parsed.id, parsed.write, parsed.link)
    return _refuse("merge")


if __name__ == "__main__":
    sys.exit(main())
