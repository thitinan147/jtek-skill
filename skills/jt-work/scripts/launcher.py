#!/usr/bin/env python3
"""The jtek.py commands for the human and for whoever starts sessions: `init`, `next`, `sync`, `release`, and `reviewer`.

Run them as `jtek.py <command>`. They live here to keep jtek.py small. `j` is the jtek module.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


TEMPLATE = {"board": "", "setup": "", "checks": {"secrets": "", "lint": "", "types": "", "test": "", "audit": "", "verify": ""}}


def init(j, args) -> None:
    existing = j.find_config()
    path = j.repo_home() / j.CONFIG
    if existing is not None and existing != j.machine_config_path():
        raise j.Refuse(f"{existing} already exists")
    if path.exists():
        raise j.Refuse(f"{path} already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    j.write_json(path, TEMPLATE)
    print(f"wrote {path}")
    print("This file is on this machine. It is not in the repository, and it is not committed.")
    print("`board` is the link of the Notion database or FLO product that holds the tickets. The agent reads it to find a ticket.")
    print(f"Leave it empty to keep the tickets as files in {j.tickets_dir()}; no board is needed then.")
    print("With no config file at all, that empty board is already the default.")
    print("`setup` installs dependencies in a new worktree, for example `npm ci`. Leave it empty when nothing is needed.")
    print("Fill in one command per check (no shell operators; put a pipeline in a script).")
    print("`secrets` is a secret scanner and `audit` a dependency audit, when the project has them.")
    print("Delete a check the project does not have.")
    print(f"The repository id is `{j.repo_home().relative_to(j.machine_root() / 'repos')}` "
          "(host, non-default port, and path of the origin URL, or the checkout path when there is no origin).")
    j.remember_origin()


def user_file_moves(j) -> list[tuple[Path, Path]]:
    """~/.config/jtek/agents.json and me.md move beside the other machine files.

    Checked before anything is moved. A destination that already exists is refused, not overwritten.
    """
    planned: list[tuple[Path, Path]] = []
    root = j.machine_root()
    for name in ("agents.json", "me.md"):
        src = Path.home() / ".config" / "jtek" / name
        dest = root / name
        if src.is_symlink():
            raise j.Refuse(f"{src} is a symlink; not moving it")
        if not src.is_file():
            continue
        if dest.exists():
            raise j.Refuse(f"{dest} already exists; not overwriting it. Move that file aside and run migrate again")
        planned.append((src, dest))
    return planned


def migrate(j, args) -> None:
    """Move jtek.json and .jtek/ out of the repository and onto this machine.

    Also moves ~/.config/jtek/agents.json and me.md to ~/.jtek (or JTEK_HOME). The repository is left with
    those paths missing. The human commits the removal. This command does not commit, and it does not overwrite.
    """
    user_plan = user_file_moves(j)
    root = Path(j.git("rev-parse", "--show-toplevel"))
    home = j.repo_home()
    home.mkdir(parents=True, exist_ok=True)
    moved: list[str] = []
    repo_moved = False

    def take(src: Path, dest: Path) -> None:
        nonlocal repo_moved
        if not src.exists() and not src.is_symlink():
            return
        if src.is_symlink():
            raise j.Refuse(f"{src} is a symlink; not moving it")
        if dest.exists():
            raise j.Refuse(f"{dest} already exists; not overwriting it. Move that file aside and run migrate again")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dest))
        moved.append(f"{src.relative_to(root)} -> {dest}")
        repo_moved = True

    take(root / j.CONFIG, home / j.CONFIG)
    dot = root / ".jtek"
    if dot.is_symlink():
        raise j.Refuse(f"{dot} is a symlink; not moving it")
    if dot.is_dir():
        for name in ("verify.md", "features", "rules.md", "tickets"):
            take(dot / name, home / name)
        try:
            dot.rmdir()
        except OSError:
            left = sorted(p.name for p in dot.iterdir())
            print(f"left in {dot}: {', '.join(left)}. Those names are not jtek knowledge; delete them yourself if you want .jtek gone.")
    for src, dest in user_plan:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dest))
        moved.append(f"{src} -> {dest}")
    if not moved:
        raise j.Refuse(f"nothing to migrate: no {j.CONFIG} and no .jtek/verify.md, features, rules.md, or tickets in {root}, "
                       "and no ~/.config/jtek/agents.json or me.md")
    print(f"repository id: {home.relative_to(j.machine_root() / 'repos')}")
    for line in moved:
        print(f"moved: {line}")
    if repo_moved:
        print("These paths are gone from the work tree. Review `git status` and commit the removal.")
        print("jtek does not commit it. A checkout on another machine does not have this folder until you copy it or migrate there.")


def file_rows(j) -> list[dict]:
    """The rows of a repository with no board: one for each ticket file, read from its header."""
    rows = []
    for path in j.iter_ticket_files():
        try:
            ticket = j.parse_ticket(path.read_text())
        except (OSError, ValueError) as err:
            raise j.Refuse(f"cannot read the ticket file {path}: {err}") from None
        fields = ticket["fields"]
        rows.append({"id": fields.get("id") or path.stem, "title": ticket["title"], "status": fields.get("status", ""),
                     "repo": fields.get("repo", ""), "waiting": fields.get("waiting", ""), "pr": fields.get("pr", ""),
                     "after": j.open_after(fields.get("after", ""))})
    if not rows:
        print(f"no ticket files in {j.tickets_dir()}")
    return rows


def load_board(j, path: str | None) -> list[dict]:
    """Rows that the launcher read from the board with its own tool, or the ticket files when there is no board.
    Every row is checked before any is used."""
    if not path:
        if j.has_board(j.base_branch()):
            raise j.Refuse("pass --board-file: the open tickets, read from the board and saved as JSON; "
                           "see references/starting-sessions.md")
        rows = file_rows(j)
    else:
        try:
            rows = json.loads(Path(path).read_text())
        except (OSError, ValueError) as err:
            raise j.Refuse(f"cannot read the board file {path}: {err}") from None
    if not isinstance(rows, list) or not all(isinstance(row, dict) and row.get("id") for row in rows):
        raise j.Refuse("the board file must be a JSON list of objects, each with `id` and `status`; "
                       "see references/starting-sessions.md")
    for row in rows:
        row["id"] = j.check_id(str(row["id"]))
        after = row.get("after") or []
        row["after"] = [" ".join(str(item).split()) for item in (after.split(",") if isinstance(after, str) else
                                                               after if isinstance(after, list) else [after]) if str(item).strip()]
        for key in ("repo", "waiting", "pr", "title"):
            row[key] = " ".join(str(row.get(key) or "").split())  # one line: a value cannot add a line to the output
        row["status"] = j.canon_status(str(row.get("status") or "")) or "Backlog"
    return sorted(rows, key=lambda item: item["id"])


def this_repo(j) -> str:
    return str(j.load_config(j.base_branch()).get("name") or j.main_root().name)


def sync(j, args) -> None:
    """Done is read back from the forge, never assumed. Print what to write on the board, and tidy worktrees.
    Every ticket of this repository in Review, Done, or Cancelled gets a line, so silence never means success."""
    repo = this_repo(j)
    for row in load_board(j, args.board_file):
        if row["repo"] not in ("", repo):
            continue
        ticket_id, status = row["id"], row["status"]
        if status in ("Done", "Cancelled"):
            print(f"{ticket_id}\t-\t{status}; " + (tidy_done(j, ticket_id, row["pr"]) or "nothing to tidy on this machine"))
        elif status != "Review":
            continue
        elif not row["pr"]:
            print(f"{ticket_id}\t-\tno pull request on the page; the human sets Done after merging")
        elif not j.re.match(r"^https?://[^\s;]+$", row["pr"]):
            print(f"{ticket_id}\t-\tthe PR on the page is not a link; the human sets Done after merging")
        else:
            try:
                state, head, ci, _problem = j.pr_info(row["pr"], j.base_branch())
            except j.Refuse as err:
                print(f"{ticket_id}\t-\tcould not read {row['pr']}: {err}")
                continue
            if state == "MERGED":
                print(f"{ticket_id}\tboard: Status=Done\tthe pull request is merged; " + (tidy_done(j, ticket_id, head=head) or "nothing to tidy"))
            elif state == "unknown":
                print(f"{ticket_id}\t-\tcould not read {row['pr']}; is `gh` installed and signed in?")
            elif state == "OPEN":
                clash = f", conflicts with {j.base_branch()}: the human sends it back, or a session brings it up to date" \
                    if j.pr_conflicts(row["pr"]) else ""
                print(f"{ticket_id}\t-\topen, CI: {ci}{clash}")
            else:
                print(f"{ticket_id}\t-\tPR state: {state}")


def next_step(j, row: dict, repo: str) -> tuple[str, str]:
    """What one ticket needs now. The first word is the action: `work`, `review`, and `board` are for a
    session to do. Every other word means do not start one."""
    ticket_id, status = row["id"], row["status"]
    if row["repo"] not in ("", repo):
        return "other", f"belongs to the repository `{row['repo']}`"
    if status == "Backlog":
        return "hold", "not released; the human sets Todo"
    if status in ("Done", "Cancelled"):
        return "hold", "finished"
    if status == "Review":
        return "human", "review and merge " + (row["pr"] or "the branch")
    work = j.work_dir(ticket_id)
    try:
        meta = j.read_json(work / "meta.json")
    except j.Refuse:
        return "stuck", f"the claim's meta.json is damaged; the human runs `jtek.py release {ticket_id}`"
    claimed, parked = bool(meta.get("worktree")) and not meta.get("starting"), (work / "result.md").exists()
    if j.starting_now(meta):
        return "running", "a session is starting it right now"
    if work.exists() and not claimed:
        return "stuck", f"an earlier start was interrupted; the human runs `jtek.py release {ticket_id}`"
    if claimed and not Path(meta["worktree"]).is_dir():
        return "stuck", f"the worktree is gone; the human runs `jtek.py release {ticket_id}`"
    if claimed and not parked:
        return "running", "a session holds the claim. If none is running, it died: tell a new session to take it over"
    if status == "Todo":
        if row["after"]:
            return "hold", "comes after " + ", ".join(row["after"])
        return "work", "the human answered, or asked for rework" if claimed else "new"
    if row["waiting"]:
        return "human", f"waiting for {row['waiting']}; answer on the page and set Status to Todo"
    if not claimed:
        return "elsewhere", "In Progress, and not claimed on this machine"
    result = (work / "result.md").read_text()
    outcome = next((line[9:].strip() for line in result.splitlines() if line.startswith("outcome: ")), "")
    if outcome == "review":
        return "board", f"the page does not show the result; write the `board:` line of `jtek.py result {ticket_id}`"
    if outcome == "needs-human":
        return "board", f"the page does not show the question; write the `board:` line of `jtek.py result {ticket_id}`"
    verdict = j.current_verdict(ticket_id, meta)
    if not verdict:
        return "review", "needs a verdict from a session that did not write the change"
    if verdict.get("verdict") == "FAIL":
        return "work", "the verdict is FAIL; the findings are in the review notes"
    return "work", "the verdict is in; finish"


def next_(j, args) -> None:
    repo = this_repo(j)
    for row in load_board(j, args.board_file):
        action, reason = next_step(j, row, repo)
        if action != "other":
            print(f"{row['id']}\t{action}\t{reason}")


def off_branch(j, worktree: Path, branch: str) -> str:
    """Commits of the worktree that its branch does not have, for example made on a detached HEAD.
    Removing the worktree would leave them on no branch."""
    there = j.git("rev-parse", "--verify", "--quiet", f"refs/heads/{branch}", check=False)
    # Without the ticket's branch, any branch that holds the commits will do.
    count = j.git("rev-list", "--count", "HEAD", "--not", *([f"refs/heads/{branch}"] if there else ["--branches"]),
                  cwd=worktree, check=False)
    return "" if count == "0" else (f"{worktree} has commits that are not on the branch {branch}. Check the branch out "
                                    "there, or give those commits a branch of their own")


def tidy_done(j, ticket_id: str, pr: str = "", head: str | None = None) -> str:
    """Remove the worktree of a finished ticket, and its branch when the work is known to be merged.
    A worktree with uncommitted files stays. A branch is deleted only when all its commits are on the base, or
    the forge says the pull request merged at exactly the branch's commit; a squash merge is the second case.
    Return what happened, or an empty string when there was nothing to remove."""
    meta = j.read_json(j.work_dir(ticket_id) / "meta.json")
    if not meta.get("worktree") or not Path(meta["worktree"]).is_dir():
        return ""
    worktree, branch = Path(meta["worktree"]), meta["branch"]
    tip = j.git("rev-parse", "--verify", "--quiet", f"refs/heads/{branch}", check=False)
    try:
        if j.git("status", "--porcelain", cwd=worktree):  # a status that cannot be read is not a clean one
            return f"worktree kept, because it has uncommitted files: {worktree}"
        loose = off_branch(j, worktree, branch)
        if loose:
            return f"worktree kept: {loose}"
        # No --force: git itself refuses a worktree with changes, and one with submodules, whose commits may be nowhere else.
        j.git("worktree", "remove", str(worktree))
    except j.Refuse as err:
        return f"worktree kept: {err}"
    merged = j.git("rev-list", "--count", f"{j.base_ref(meta['base'])}..refs/heads/{branch}", check=False) == "0"
    if not merged and head is None and j.re.match(r"^https?://[^\s;]+$", pr):
        try:
            state, head, _, _problem = j.pr_info(pr, meta["base"])
            head = head if state == "MERGED" else ""
        except j.Refuse:
            head = ""
    if tip and (merged or head == tip):
        j.git("branch", "-D", branch, check=False)
        return "worktree and branch removed"
    return f"worktree removed; the branch {branch} is kept, because this script cannot see that its commits are merged"


def release(j, args) -> None:
    """Drop a claim. Work is never lost here: a worktree with uncommitted files stays, and a branch is deleted
    only when this script made it in a start that never finished, and it has no commit of its own."""
    work = j.work_dir(args.id)
    if not work.exists():
        raise j.Refuse(f"{args.id} is not claimed on this machine")
    try:
        meta = j.read_json(work / "meta.json")
    except j.Refuse:
        meta = {}  # damaged: treat everything as unknown, which is the careful path below
    if j.starting_now(meta):
        raise j.Refuse(f"a start of {args.id} is running right now (process {meta['pid']}). Wait for it, or end that session first")
    worktree, branch = (Path(meta["worktree"]), meta["branch"]) if meta.get("worktree") else j.ticket_paths(args.id)
    base = meta.get("base") or j.base_branch()
    exists = bool(j.git("rev-parse", "--verify", "--quiet", f"refs/heads/{branch}", check=False))
    own = j.git("rev-list", "--count", f"{j.base_ref(base)}..refs/heads/{branch}", check=False) if exists else "0"
    fresh = bool(meta.get("starting")) and meta.get("kept") is False and own == "0"
    if worktree.is_dir():
        if fresh:
            if j.git("status", "--porcelain", "--untracked-files=no", cwd=worktree):
                raise j.Refuse(f"{worktree} has edits to tracked files. Restore or commit them, then release again")
            if off_branch(j, worktree, branch):
                raise j.Refuse(off_branch(j, worktree, branch) + ", then release again")
            j.git("worktree", "remove", "--force", str(worktree))  # holds only what the setup command made
        elif j.git("status", "--porcelain", cwd=worktree):  # a status that cannot be read is not a clean one
            raise j.Refuse(f"{worktree} has uncommitted files. Commit or remove them, then release again")
        elif off_branch(j, worktree, branch):
            raise j.Refuse(off_branch(j, worktree, branch) + ", then release again")
        else:
            # No --force: git itself refuses a worktree with changes, and one with submodules.
            j.git("worktree", "remove", str(worktree))
    j.git("worktree", "prune", check=False)  # a worktree whose folder was deleted by hand is forgotten here
    if fresh and exists:
        j.git("branch", "-D", branch, check=False)
    for path in sorted(work.rglob("*"), reverse=True):
        path.rmdir() if path.is_dir() else path.unlink()
    work.rmdir()
    kept = exists and not fresh
    print(f"released {args.id}; " + (f"branch {branch} is kept, and the next start goes on from it" if kept
                                     else "the interrupted start is cleaned up")
          + (". A local ticket has no board" if j.LOCAL_RE.match(args.id) else ". The board is not changed: set Status on the page yourself"))


def guess(j, args) -> None:
    import guess as module
    module.run(j, args)


def session_label(meta: dict) -> str:
    """The stored session hash, or '-' . A value that is not that hash is not printed."""
    author = meta.get("author")
    if isinstance(author, str) and len(author) == 16 and all(char in "0123456789abcdef" for char in author):
        return f"session {author}"
    return "session -"


def status(j, args) -> None:
    """Read-only table: in progress, waiting for review, waiting for merge, and the one next action.

    The words are Thai. Nothing is written: no claim, no release, no board change.
    """
    repo = this_repo(j)
    doing: list[str] = []
    review: list[str] = []
    merge: list[str] = []
    ranked: list[tuple[int, str, str, str]] = []
    for row in load_board(j, args.board_file):
        action, reason = next_step(j, row, repo)
        if action == "other":
            continue
        ticket_id = row["id"]
        detail = " ".join(str(reason).split())
        if action == "running":
            try:
                meta = j.read_json(j.work_dir(ticket_id) / "meta.json")
            except j.Refuse:
                meta = {}
            doing.append(f"กำลังทำ\t{ticket_id}\t{session_label(meta)}")
        elif action == "review":
            review.append(f"รอรีวิว\t{ticket_id}\t{detail}")
            ranked.append((1, ticket_id, action, detail))
        elif action == "human" and detail.startswith("review and merge"):
            merge.append(f"รอ merge\t{ticket_id}\t{detail}")
            ranked.append((2, ticket_id, action, detail))
        if action == "work":
            ranked.append((0, ticket_id, action, detail))
        elif action == "stuck":
            ranked.append((3, ticket_id, action, detail))
    for lines, empty in ((doing, "กำลังทำ\t-"), (review, "รอรีวิว\t-"), (merge, "รอ merge\t-")):
        for line in lines or [empty]:
            print(line)
    if ranked:
        ranked.sort()
        _rank, ticket_id, action, detail = ranked[0]
        print(f"ถัดไป\t{action}\t{ticket_id}\t{detail}")
    else:
        print("ถัดไป\t-")


def doctor(j, args) -> None:
    if getattr(args, "agents", False):
        import agents
        agents.report(j, args)  # about the machine, so it needs no repository
        return
    import doctor as module
    module.run(j, args)


def reviewer(j, args) -> None:
    import agents
    agents.reviewer(j, args)


COMMANDS = {"init": init, "migrate": migrate, "guess": guess, "status": status, "next": next_, "sync": sync,
            "release": release, "doctor": doctor, "reviewer": reviewer}
