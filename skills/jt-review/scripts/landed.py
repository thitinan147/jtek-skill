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


_TASK_SLUG_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_BARE_TASK_HEAD_RE = re.compile(r"^task-(\d+(?:\.\d+)*)$")
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
_KIND_PAREN = re.compile(r"\(([a-z]+)\)")
_COLON_TOKEN = re.compile(r"(?<!\S)([^\s:]+):")
_STATUS_SET = frozenset(
    {"ask:", "review:", "send-back:", "merge:", "drop:", "unknown:"}
)


def _normalize_ticket_id(value: str) -> str:
    value = value.strip()
    if " #" in value:
        value = value.split(" #", 1)[0].rstrip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1].strip()
    return value


def _ticket_id(root: Path, card_id: str) -> str:
    path = root / "jt-queue" / "tasks" / card_id / "task.md"
    if not path.is_file():
        return ""
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("ticket:"):
            return _normalize_ticket_id(stripped.split(":", 1)[1])
    return ""


def _read_board(root: Path) -> str:
    path = root / "jt-queue" / "board.md"
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def _cut_known_status(text: str) -> str:
    for found in _COLON_TOKEN.finditer(text):
        token = f"{found.group(1)}:"
        if token in _STATUS_SET:
            return text[: found.start()]
    return text


def _card_kind_in_board(board_text: str, card_id: str) -> str:
    if not re.match(r"^\d+(\.\d+)*$", card_id):
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


def _branch_type(kind: str) -> str:
    return kind if kind in _BRANCH_TYPES else "feat"


def _legacy_task_head(name: str, card_id: str) -> bool:
    bare = f"task-{card_id}"
    if name == bare:
        return True
    return name.startswith(bare + "-") and bool(_TASK_SLUG_RE.fullmatch(name[len(bare) + 1 :]))


def _conventional_task_head(name: str, ticket_id: str) -> bool:
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


def _is_task_head(name: str, card_id: str, ticket_id: str = "") -> bool:
    """Conventional type/<ticket-id>-<slug>, or legacy task-<id>[-<slug>] (same rule as gate.py)."""
    if _legacy_task_head(name, card_id):
        return True
    return _conventional_task_head(name, ticket_id)


def _default_task_branch(root: Path, card_id: str, ticket_id: str) -> str:
    if ticket_id:
        kind = _branch_type(_card_kind_in_board(_read_board(root), card_id))
        return f"{kind}/{ticket_id}"
    return f"task-{card_id}"


def _task_branch(root: Path, card_id: str) -> tuple[str, bool]:
    """(branch, gone): one local match, else one remote, else the conventional default."""
    ticket_id = _ticket_id(root, card_id)
    proc = _run(
        root,
        ["git", "for-each-ref", "--format=%(refname)", "refs/heads", "refs/remotes"],
    )
    local: set[str] = set()
    remote: set[str] = set()
    if proc is not None and proc.returncode == 0:
        for ref in proc.stdout.split():
            if ref.startswith("refs/heads/"):
                name, bucket = ref[len("refs/heads/") :], local
            elif ref.startswith("refs/remotes/") and ref.count("/") >= 3:
                name, bucket = ref.split("/", 3)[3], remote
            else:
                continue
            if _is_task_head(name, card_id, ticket_id):
                bucket.add(name)
    remote -= local
    gone = not local and not remote
    if len(local) == 1:
        return next(iter(local)), gone
    if not local and len(remote) == 1:
        return next(iter(remote)), gone
    return _default_task_branch(root, card_id, ticket_id), gone


def _head_matches(name: object, head: str, fuzzy: bool = False, *, ticket_id: str = "") -> bool:
    if not isinstance(name, str):
        return False
    if name == head:
        return True
    if not fuzzy:
        return False
    bare = _BARE_TASK_HEAD_RE.match(head)
    if bare and _is_task_head(name, bare.group(1), ticket_id):
        return True
    return (
        bool(ticket_id)
        and head.count("/") == 1
        and name.startswith(head + "-")
        and _conventional_task_head(name, ticket_id)
    )


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
    head, fuzzy = _task_branch(root, card_id)
    ticket_id = _ticket_id(root, card_id)
    view = _run(root, ["gh", "pr", "view", head, "--json", "state,headRefName"])
    if view is not None and view.returncode == 0:
        mark = _payload_mark(view.stdout, head)
        if mark in {"merged", "open"}:
            return mark
    listed = _run(
        root,
        ["gh", "pr", "list", "--head", head, "--state", "all", "--json", "state,headRefName"],
    )
    if listed is not None and listed.returncode == 0:
        mark = _payload_mark(listed.stdout, head)
        if mark != "missing" or not fuzzy:
            return mark
    elif not fuzzy:
        return "missing"
    recent = _run(root, ["gh", "pr", "list", "--state", "all", "--limit", "200", "--json", "state,headRefName"])
    if recent is None or recent.returncode != 0:
        return "missing"
    return _payload_mark(recent.stdout, head, fuzzy=True, ticket_id=ticket_id)


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
    head = _task_branch(root, card_id)[0]
    if _branch_exists(root, head) and _branch_exists(root, queue):
        anc = _run(root, ["git", "merge-base", "--is-ancestor", head, queue])
        if anc is not None and anc.returncode == 0:
            return "ancestor", ""
    mark = _github_mark(root, card_id)
    if mark == "merged":
        return "squash", ""
    return "", "pr-open" if mark == "open" else "pr-missing"


def _gh_merged_at(root: Path, head: str, fuzzy: bool = False, *, ticket_id: str = "") -> int | None:
    if fuzzy:
        argv = ["gh", "pr", "list", "--state", "merged", "--limit", "200", "--json", "mergedAt,headRefName"]
    else:
        argv = ["gh", "pr", "list", "--head", head, "--state", "merged", "--json", "mergedAt,headRefName"]
    proc = _run(root, argv)
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
    if via == "squash":
        ticket_id = _ticket_id(root, card_id)
        head, gone = _task_branch(root, card_id)
        return _gh_merged_at(root, head, fuzzy=gone, ticket_id=ticket_id)
    tip_proc = _run(root, ["git", "rev-parse", _task_branch(root, card_id)[0]])
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
    head = _task_branch(root, card_id)[0]
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
