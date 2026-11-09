#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

_CARD_ID_RE = re.compile(r"^\d+(\.\d+)*$")


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
    return min(val, 3600.0)


def _git_env() -> dict[str, str]:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        env.pop(key, None)
    return env


def _run(root: Path, argv: list[str], timeout: float | None = None) -> subprocess.CompletedProcess[str] | None:
    effective_timeout = _env_timeout("JT_GH_TIMEOUT", 5.0) if timeout is None else timeout
    try:
        return subprocess.run(
            argv,
            cwd=root,
            capture_output=True,
            text=True,
            env=_git_env(),
            timeout=effective_timeout,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def _branch_exists(root: Path, branch: str) -> bool:
    proc = _run(root, ["git", "rev-parse", "--verify", "--quiet", branch])
    return proc is not None and proc.returncode == 0


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
    head = f"task-{card_id}"
    view = _run(root, ["gh", "pr", "view", head, "--json", "state,headRefName"])
    if view is not None and view.returncode == 0:
        mark = _payload_mark(view.stdout, head)
        if mark in {"merged", "open"}:
            return mark
    listed = _run(
        root,
        ["gh", "pr", "list", "--head", head, "--state", "all", "--json", "state,headRefName"],
    )
    if listed is None or listed.returncode != 0:
        return "missing"
    return _payload_mark(listed.stdout, head)


def _refuse(reason: str, detail: str = "", nxt: str = "") -> int:
    print(f"refused: {reason}")
    print("merge: no")
    if nxt:
        print(f"next: {nxt}")
    if detail:
        print(f"detail: {detail}")
    return 1


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "landed":
        args = args[1:]
    parser = argparse.ArgumentParser(prog="landed.py")
    parser.add_argument("--root", default=".")
    parser.add_argument("--id", required=True)
    parsed = parser.parse_args(args)
    card_id = parsed.id
    if not _CARD_ID_RE.match(card_id):
        return _refuse("invalid-id", nxt="stop")
    root = Path(parsed.root).resolve()
    board_path = root / "jt-queue" / "board.md"
    if not board_path.is_file():
        return _refuse("board-missing", nxt="stop")
    queue = ""
    for line in board_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("queue:"):
            queue = line.split(":", 1)[1].strip()
            break
    if not queue:
        return _refuse("not-landed", detail="no-queue")
    head = f"task-{card_id}"
    if _branch_exists(root, head) and _branch_exists(root, queue):
        anc = _run(root, ["git", "merge-base", "--is-ancestor", head, queue])
        if anc is not None and anc.returncode == 0:
            print("landed: ancestor")
            print("merge: no")
            return 0
    mark = _github_mark(root, card_id)
    if mark == "merged":
        print("landed: squash")
        print("merge: no")
        return 0
    return _refuse("not-landed", detail="pr-open" if mark == "open" else "pr-missing")


if __name__ == "__main__":
    sys.exit(main())
