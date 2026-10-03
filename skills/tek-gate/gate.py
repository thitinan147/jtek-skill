#!/usr/bin/env python3
"""Read card-loop/board.md and take the next step the loop already allows.

The gate cannot merge. A failing <TEST_CMD> cannot write รอรีวิว.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

NO_SUITE = "ไม่มีชุดเทส"
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
    "setup-board": "/tek-setup-board",
    "brief": "/tek-brief",
    "add-card": "/tek-add-card",
    "do-card": "/tek-do-card",
    "open-review": "/tek-open-review",
    "wait": "",
    "stop": "",
}
SECTION_RANK = {"ทำก่อน": 0, "งานหลัก": 1, "เก็บเล็ก": 2}
STATUS_TOKENS = ("รอรีวิว:", "ส่งกลับ:", "ถาม:", "merge:", "ปิด:")
MERGE_ARGV = {
    "merge",
    "/merge",
    "mark-merge",
    "/mark-merge",
    "tek-mark-merge",
    "/tek-mark-merge",
}
ROW_RE = re.compile(r"^\|\s*`<([^>]+)>`\s*\|\s*(.*?)\s*\|\s*$")
CARD_RE = re.compile(r"^- \[([ xX])\] \*\*(.+?)\*\*\s*(.*)$")


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
        status = next((token for token in STATUS_TOKENS if token in rest), None)
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
            continue
        card.files = tuple(parse_files(body))
        card.question = question_text(body)
        card.question_empty = card.question == ""
    return board


def _is_parent(card: Card, cards: list[Card]) -> bool:
    prefix = card.id + "."
    return any(other.id.startswith(prefix) for other in cards)


def _overlaps(left: tuple[str, ...], right: tuple[str, ...]) -> bool:
    return bool(set(left) & set(right))


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
        return _do(send_back, "send-back")
    cleared = _work(
        pool,
        lambda card: card.status == "ถาม:" and card.question_empty and card.has_card_file,
    )
    if cleared:
        return _do(cleared, "question-cleared")
    ready = _work(pool, lambda card: card.status is None and card.has_card_file)
    if ready:
        return _do(ready, "ready")
    parent = _parent_ready(board.cards)
    if parent:
        return _do(parent, "subcards-complete")

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
    proc = _run_git(root, ["status", "--porcelain"])
    if proc.returncode != 0:
        return False
    for line in proc.stdout.splitlines():
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if not path.startswith("card-loop/"):
            return True
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
        "evidence": _section_h2(plan, "หลักฐานก่อนเปิดของให้ review"),
        "diff": diff,
        "diff_ok": diff_ok,
        "compared": compared,
    }


def execute_test_cmd(root: Path, card_id: str, test_cmd: str) -> int:
    """Run TEST_CMD on card-<id>. ไม่มีชุดเทส is not a command."""
    command = test_cmd.strip()
    if command == "":
        raise GateError("test-cmd-empty")
    branch = f"card-{card_id}"
    if not _branch_exists(root, branch):
        raise GateError("card-branch-missing")
    if command == NO_SUITE:
        return 0
    if _current_branch(root) == branch:
        return _run_shell(command, root)
    parent = Path(tempfile.mkdtemp(prefix="tek-gate-"))
    worktree = parent / "card"
    try:
        added = _run_git(root, ["worktree", "add", "--detach", str(worktree), branch])
        if added.returncode != 0:
            raise GateError("worktree-failed", added.stderr.strip())
        return _run_shell(command, worktree)
    finally:
        _run_git(root, ["worktree", "remove", "--force", str(worktree)])
        shutil.rmtree(parent, ignore_errors=True)


def _run_shell(command: str, cwd: Path) -> int:
    proc = subprocess.run(
        command,
        shell=True,
        cwd=cwd,
        env=_git_env(),
        capture_output=True,
        text=True,
    )
    return proc.returncode


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


def _refuse(reason: str) -> int:
    print(f"refused: {reason}")
    print("merge: no")
    return 1


def cmd_reach_review(root: Path, card_id: str, write: bool, link: str) -> int:
    board_path = root / "card-loop" / "board.md"
    if not board_path.is_file():
        return _refuse("board-missing")
    text = board_path.read_text(encoding="utf-8")
    queue = parse_queue(text)
    test_cmd = parse_field(text, "TEST_CMD")
    if write and (not queue or _current_branch(root) != queue):
        return _refuse("not-on-queue-branch")
    if test_cmd.strip() == "":
        return _refuse("test-cmd-empty")
    try:
        code = execute_test_cmd(root, card_id, test_cmd)
        if write:
            updated = apply_waiting_review(text, card_id, code, link)
            board_path.write_text(updated, encoding="utf-8")
        elif code != 0:
            return _refuse("test-failed")
    except GateError as err:
        return _refuse(err.reason)
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
    parser = argparse.ArgumentParser(prog="tek-gate")
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
