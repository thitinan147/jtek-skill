#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
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


def _home_lines(text: str) -> list[str]:
    lines: list[str] = []
    inside = False
    for line in text.splitlines():
        if line.startswith("## "):
            inside = line[3:].strip().casefold() == "repos"
        if not inside:
            lines.append(line)
    return lines


def _repos(text: str) -> list[dict[str, str]]:
    """`### <name>` blocks under `## repos` with their path: and queue: (same rules as gate.py)."""
    repos: list[dict[str, str]] = []
    inside = False
    for line in text.splitlines():
        if line.startswith("## "):
            inside = line[3:].strip().casefold() == "repos"
            continue
        if not inside:
            continue
        if line.startswith("### "):
            repos.append({"name": line[4:].strip(), "path": "", "queue": ""})
        elif repos and line.startswith("path:"):
            repos[-1]["path"] = line.split(":", 1)[1].strip()
        elif repos and line.startswith("queue:"):
            repos[-1]["queue"] = line.split(":", 1)[1].strip()
    return repos


def _label(text: str, name: str) -> str:
    for line in text.splitlines():
        if line.startswith(f"{name}:"):
            return line[len(name) + 1 :].strip()
    return ""


def _names(raw: str) -> list[str]:
    return list(dict.fromkeys(n for n in re.split(r"[\s,]+", raw) if n and n != "-"))


def _home_toplevel(root: Path) -> Path:
    proc = _run(root, ["git", "rev-parse", "--git-common-dir"])
    if proc is not None and proc.returncode == 0 and proc.stdout.strip():
        common = Path(proc.stdout.strip())
        common = common if common.is_absolute() else (root / common).resolve()
        if common.name == ".git":
            return common.parent.resolve()
    proc = _run(root, ["git", "rev-parse", "--show-toplevel"])
    if proc is not None and proc.returncode == 0:
        return Path(proc.stdout.strip()).resolve()
    return root.resolve()


def _landed_via(root: Path, card_id: str, queue: str) -> tuple[str, str]:
    head = f"task-{card_id}"
    if _branch_exists(root, head) and _branch_exists(root, queue):
        anc = _run(root, ["git", "merge-base", "--is-ancestor", head, queue])
        if anc is not None and anc.returncode == 0:
            return "ancestor", ""
    mark = _github_mark(root, card_id)
    if mark == "merged":
        return "squash", ""
    return "", "pr-open" if mark == "open" else "pr-missing"


def _gh_merged_at(root: Path, head: str) -> int | None:
    proc = _run(root, ["gh", "pr", "list", "--head", head, "--state", "merged", "--json", "mergedAt,headRefName"])
    if proc is None or proc.returncode != 0:
        return None
    try:
        rows = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:
        return None
    for row in rows if isinstance(rows, list) else [rows]:
        if isinstance(row, dict) and row.get("headRefName") == head and isinstance(row.get("mergedAt"), str):
            try:
                return int(datetime.fromisoformat(row["mergedAt"].replace("Z", "+00:00")).timestamp())
            except ValueError:
                return None
    return None


def _land_time(root: Path, card_id: str, queue: str, via: str) -> int | None:
    if via == "squash":
        return _gh_merged_at(root, f"task-{card_id}")
    tip_proc = _run(root, ["git", "rev-parse", f"task-{card_id}"])
    tip = tip_proc.stdout.strip() if tip_proc is not None else ""
    path = _run(root, ["git", "rev-list", "--first-parent", "--ancestry-path", "--reverse", f"{tip}..{queue}"])
    first = path.stdout.split()[0] if path is not None and path.returncode == 0 and path.stdout.split() else tip
    shown = _run(root, ["git", "show", "-s", "--format=%ct", first])
    if shown is None or shown.returncode != 0 or not shown.stdout.strip().isdigit():
        return None
    return int(shown.stdout.strip())


def _landed_across(root: Path, board: str, card: str, card_id: str, home_queue: str) -> tuple[bool, list[str], str] | None:
    repos = _repos(board)
    names = _names(_label(card, "repos"))
    home_name = next((r["name"] for r in repos if r["path"] == "."), "")
    if not repos or not names or names == [home_name]:
        return None
    by_name = {r["name"]: r for r in repos}
    wanted = [n for n in _names(_label(card, "land")) if n in names]
    rest = [r["name"] for r in repos if r["name"] in names and r["name"] not in wanted]
    order = list(dict.fromkeys(wanted + rest + [n for n in names if n not in wanted + rest]))
    home = _home_toplevel(root)
    states: dict[str, str] = {}
    times: dict[str, int | None] = {}
    for name in order:
        repo = by_name.get(name)
        if repo is None:
            states[name] = "unknown-repo"
            continue
        is_home = repo["path"] == "."
        where = root if is_home else (home / repo["path"]).resolve()
        queue = home_queue if is_home else repo["queue"]
        if not where.is_dir():
            states[name] = "repo-missing"
            continue
        via, detail = _landed_via(where, card_id, queue)
        states[name] = via or detail
        if via:
            times[name] = _land_time(where, card_id, queue, via)
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
    board = board_path.read_text(encoding="utf-8")
    queue = ""
    for line in _home_lines(board):
        if line.startswith("queue:"):
            queue = line.split(":", 1)[1].strip()
            break
    if not queue:
        return _refuse("not-landed", detail="no-queue")
    card_path = root / "jt-queue" / "tasks" / card_id / "task.md"
    card = card_path.read_text(encoding="utf-8") if card_path.is_file() else ""
    across = _landed_across(root, board, card, card_id, queue)
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
