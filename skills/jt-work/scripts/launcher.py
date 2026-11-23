#!/usr/bin/env python3
"""The jtek.py commands for the human and for whoever starts sessions: `init`, `next`, `sync`, and `release`.

Run them as `jtek.py <command>`. They live here to keep jtek.py small. `j` is the jtek module.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path


def init(j, args) -> None:
    path = Path(j.git("rev-parse", "--show-toplevel")) / j.CONFIG
    if path.exists():
        raise j.Refuse(f"{path} already exists")
    j.write_json(path, {"board": "", "setup": "", "checks": {"secrets": "", "lint": "", "types": "", "test": "", "audit": "", "verify": ""}})
    print(f"wrote {path}")
    print("`board` is the link of the Notion database or FLO product that holds the tickets. The agent reads it to find a ticket.")
    print("`setup` installs dependencies in a new worktree, for example `npm ci`. Leave it empty when nothing is needed.")
    print("Fill in one command per check (no shell operators; put a pipeline in a script).")
    print("`secrets` is a secret scanner and `audit` a dependency audit, when the project has them.")
    print("Delete a check the project does not have. The human commits this file on the base branch.")


def load_board(j, path: str) -> list[dict]:
    """Rows that the launcher read from the board with its own tool. Every row is checked before any is used."""
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
                state, head, ci = j.pr_info(row["pr"], j.base_branch())
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
            state, head, _ = j.pr_info(pr, meta["base"])
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
          + ". The board is not changed: set Status on the page yourself")


def doctor(j, args) -> None:
    import doctor as module
    module.run(j, args)


COMMANDS = {"init": init, "next": next_, "sync": sync, "release": release, "doctor": doctor}
