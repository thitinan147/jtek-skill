#!/usr/bin/env python3
"""The jtek.py commands for the human and for whoever starts sessions: `init`, `next`, `sync`, `release`, and `reviewer`.

Run them as `jtek.py <command>`. They live here to keep jtek.py small. `j` is the jtek module.
"""
from __future__ import annotations

import json
import os
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
    A repo copy whose contents match the machine copy is removed without overwriting the machine copy.
    """
    user_plan = user_file_moves(j)
    main = j.main_root()
    top = Path(j.git("rev-parse", "--show-toplevel")).resolve()
    roots = [main] if top == main else [main, top]
    home = j.repo_home()
    repo_plan: list[tuple[str, Path, Path, Path]] = []
    planned_moves: dict[Path, Path] = {}
    for root in roots:
        dot = root / ".jtek"
        if dot.is_symlink():
            raise j.Refuse(f"{dot} is a symlink; not moving it")
        candidates: list[tuple[Path, Path]] = [(root / j.CONFIG, home / j.CONFIG)]
        if dot.is_dir():
            for name in ("verify.md", "features", "rules.md", "tickets"):
                candidates.append((dot / name, home / name))
        for src, dest in candidates:
            if not src.exists() and not src.is_symlink():
                continue
            if src.is_symlink():
                raise j.Refuse(f"{src} is a symlink; not moving it")
            existing = dest if (dest.exists() or dest.is_symlink()) else planned_moves.get(dest)
            if existing is not None:
                if j.same_content(src, existing):
                    repo_plan.append(("drop", src, dest, root))
                    continue
                raise j.Refuse(
                    f"{src} and {dest} both exist and differ; not overwriting {dest}. "
                    f"Compare them, then either move {dest} aside and run migrate again, "
                    f"or remove {src} yourself if {dest} is the copy to keep"
                )
            repo_plan.append(("move", src, dest, root))
            planned_moves[dest] = src

    home.mkdir(parents=True, exist_ok=True)
    moved: list[str] = []
    repo_moved = False
    for action, src, dest, root in repo_plan:
        if action == "drop":
            if src.is_dir():
                shutil.rmtree(src)
            else:
                src.unlink()
            moved.append(f"removed duplicate {src.relative_to(root)} (already at {dest})")
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dest))
            moved.append(f"{src.relative_to(root)} -> {dest}")
        repo_moved = True
    for root in roots:
        dot = root / ".jtek"
        if dot.is_dir():
            try:
                dot.rmdir()
                moved.append(f"removed empty {dot.relative_to(root)}/")
                repo_moved = True
            except OSError:
                left = sorted(p.name for p in dot.iterdir())
                print(f"left in {dot}: {', '.join(left)}. Those names are not jtek knowledge; delete them yourself if you want .jtek gone.")
    for src, dest in user_plan:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dest))
        moved.append(f"{src} -> {dest}")
    if not moved:
        raise j.Refuse(f"nothing to migrate: no {j.CONFIG} and no .jtek/verify.md, features, rules.md, or tickets in {main}, "
                       "and no ~/.config/jtek/agents.json or me.md")
    print(f"repository id: {home.relative_to(j.machine_root() / 'repos')}")
    for line in moved:
        print(f"moved: {line}")
    if repo_moved:
        print("These paths are gone from the work tree. Review `git status` and commit the removal.")
        print("jtek does not commit it. A checkout on another machine does not have this folder until you copy it or migrate there.")


def plain_text(path) -> str:
    """The text of a regular file. A symlink is not opened."""
    if not path.is_file() or path.is_symlink():
        return ""
    try:
        return path.read_text()
    except OSError:
        return ""


def header_value(text: str, key: str) -> str:
    prefix = f"{key}:"
    for line in text.splitlines():
        if line.startswith(prefix):
            return " ".join(line[len(prefix):].split())
    return ""


def claim_rows(j, known: set[str]) -> list[dict]:
    """Claims that have no ticket file. A local ticket never has one: its state is the claim folder.

    Read-only. The result file, when the session has written one, supplies the status, the pull
    request, and what the ticket is waiting for. A claim with no result is in progress.
    """
    root = j.state_dir() / "work"
    if not root.is_dir():
        return []
    rows = []
    for folder in sorted(path for path in root.iterdir() if path.is_dir() and not path.is_symlink()):
        ticket_id = folder.name
        if ticket_id in known or not j.ID_RE.match(ticket_id):
            continue
        ticket = plain_text(folder / "ticket.md")
        title = next((line[2:].strip() for line in ticket.splitlines() if line.startswith("# ")), "")
        result = plain_text(folder / "result.md")
        status = header_value(result, "status")
        waiting = header_value(result, "waiting")
        pr = header_value(result, "pr")
        if waiting == "-":
            waiting = ""
        if pr == "-":
            pr = ""
        if not pr and (folder / "meta.json").is_file() and not (folder / "meta.json").is_symlink():
            try:
                pr = " ".join(str(j.read_json(folder / "meta.json").get("pr") or "").split())
            except j.Refuse:
                pr = ""
        rows.append({"id": ticket_id, "title": title, "status": status or "In Progress", "repo": "",
                     "waiting": waiting, "pr": pr, "after": []})
    return rows


def file_rows(j, *, include_claims: bool = False, announce_empty: bool = True) -> list[dict]:
    """The rows of a repository with no board: one for each ticket file, read from its header.

    With `include_claims`, a claim that has no ticket file is a row too. `sync` leaves that out:
    it only tidies tickets the page already names.
    """
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
    if include_claims:
        rows.extend(claim_rows(j, {row["id"] for row in rows}))
    if not rows and announce_empty:
        print(f"no ticket files in {j.tickets_dir()}")
    return rows


def load_board(j, path: str | None, *, include_claims: bool = False, announce_empty: bool = True) -> list[dict]:
    """Rows that the launcher read from the board with its own tool, or the ticket files when there is no board.
    Every row is checked before any is used."""
    if not path:
        if j.has_board(j.base_branch()):
            raise j.Refuse("pass --board-file: the open tickets, read from the board and saved as JSON; "
                           "see references/starting-sessions.md")
        rows = file_rows(j, include_claims=include_claims, announce_empty=announce_empty)
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


def promote_verify_overrides(j, ticket_id: str) -> str:
    """Promote known knowledge files from verify.d/<ticket_id>/ into repo_home() on merge.

    If another ticket's verify.d tree has different bytes at the same relative path, hold without
    changing main files or removing any override tree. Identical bytes are not a conflict.
    """
    override = j.active_verify_dir(ticket_id)
    if override is None:
        return ""
    files = j.verify_override_files(override)
    if not files:
        return ""
    main_home = j.repo_home()
    siblings: list[Path] = []
    seen: set[Path] = set()
    for home in j.candidate_homes():
        vroot = home / j.VERIFY_OVERRIDE_DIR
        if not vroot.is_dir() or vroot.is_symlink():
            continue
        for entry in sorted(vroot.iterdir(), key=lambda p: p.name):
            if entry.name == ticket_id or not entry.is_dir() or entry.is_symlink():
                continue
            resolved = entry.resolve()
            if resolved not in seen:
                seen.add(resolved)
                siblings.append(entry)
    conflicts: list[str] = []
    for rel in files:
        src = override / rel
        clashing: list[str] = []
        for other in siblings:
            other_file = other / rel
            if not other_file.exists() and not other_file.is_symlink():
                continue
            if not j.same_content(src, other_file):
                clashing.append(other.name)
        if clashing:
            conflicts.append(f"{rel} conflicts with {', '.join(clashing)}")
    if conflicts:
        return f"hold: verify.d/{ticket_id} not promoted ({'; '.join(conflicts)})"
    for rel in files:
        src = override / rel
        dest = main_home / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(f"{dest.name}.{os.getpid()}.tmp")
        tmp.write_bytes(src.read_bytes())
        os.replace(tmp, dest)
    shutil.rmtree(override)
    return f"promoted verify.d/{ticket_id}: {', '.join(files)}"


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
                tidy = tidy_done(j, ticket_id, head=head) or "nothing to tidy"
                promo = promote_verify_overrides(j, ticket_id)
                detail = f"the pull request is merged; {tidy}" + (f"; {promo}" if promo else "")
                print(f"{ticket_id}\tboard: Status=Done\t{detail}")
            elif state == "unknown":
                forge = j.select_forge(j.base_branch())
                print(f"{ticket_id}\t-\tcould not read {row['pr']}; is `{forge}` installed and signed in?")
            elif state == "OPEN":
                clash = f", conflicts with {j.base_branch()}: the human sends it back, or a session brings it up to date" \
                    if j.pr_conflicts(row["pr"]) else ""
                print(f"{ticket_id}\t-\topen, CI: {ci}{clash}")
            else:
                print(f"{ticket_id}\t-\tPR state: {state}")


def repo_names(value: str) -> list[str]:
    """Comma-separated repository names from a ticket's `repo:` field, trimmed and deduplicated in order."""
    return list(dict.fromkeys(part.strip() for part in str(value or "").split(",") if part.strip()))


def next_step(j, row: dict, repo: str) -> tuple[str, str]:
    """What one ticket needs now. The first word is the action: `work`, `review`, and `board` are for a
    session to do. Every other word means do not start one."""
    ticket_id, status = row["id"], row["status"]
    repos = repo_names(row["repo"])
    if len(repos) > 1:
        if status in ("Done", "Cancelled"):
            return ("hold", "finished") if repo in repos else ("other", f"belongs to the repositories `{', '.join(repos)}`")
        return "board", f"several repositories ({', '.join(repos)}); split it into one ticket per repo"
    if repos and repos[0] != repo:
        return "other", f"belongs to the repository `{repos[0]}`"
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
    for row in load_board(j, args.board_file, include_claims=True):
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


CHOICE_CAP = 3


def ticket_choices(j, ticket_id: str, cap: int = CHOICE_CAP) -> list[str]:
    """`choice:` lines from one ticket's evidence, collapsed to one line and capped per ticket. Never raises."""
    try:
        path = j.work_dir(ticket_id) / "evidence.md"
    except j.Refuse:
        return []
    if not path.is_file() or path.is_symlink():
        return []
    try:
        text = path.read_text(errors="replace")
    except OSError:
        return []
    found: list[str] = []
    for line in text.splitlines():
        item = line.strip()
        while item.startswith(("- ", "* ")):
            item = item[2:].lstrip()
        if item.startswith("choice:"):
            body = " ".join(item[len("choice:"):].split())
            if body:
                found.append(body)
    if len(found) > cap:
        return found[:cap] + [f"… +{len(found) - cap}"]
    return found


def status(j, args) -> None:
    """Read-only readiness line and Thai table: in progress, waiting for review, waiting for merge, choices to confirm, and next actions.

    First line reports machine and repository readiness derived from `doctor.assess(j)`.
    Every row that `next` prints appears either in a group or under `ถัดไป`.
    Nothing is written: no claim, no release, no board change.
    """
    import doctor as doctor_mod

    report = doctor_mod.assess(j)
    readiness = doctor_mod.readiness_line(report)
    try:
        repo = this_repo(j)
    except j.Refuse:
        try:
            repo = j.main_root().name
        except j.Refuse:
            repo = ""
    if args.board_file:
        board_rows = load_board(j, args.board_file, include_claims=True, announce_empty=False)
    elif report["config"] is not None:
        board_rows = load_board(j, None, include_claims=True, announce_empty=False)
    else:
        board_rows = []
    doing: list[str] = []
    review: list[str] = []
    merge: list[str] = []
    choices: list[str] = []
    ranked: list[tuple[int, str, str, str, bool]] = []
    for row in board_rows:
        action, reason = next_step(j, row, repo)
        if action == "other":
            continue
        ticket_id = row["id"]
        detail = " ".join(str(reason).split())
        if not (action == "hold" and detail == "finished"):
            for choice in ticket_choices(j, ticket_id):
                choices.append(f"choice รอยืนยัน\t{ticket_id}\t{choice}")
        if action == "running":
            try:
                meta = j.read_json(j.work_dir(ticket_id) / "meta.json")
            except j.Refuse:
                meta = {}
            doing.append(f"กำลังทำ\t{ticket_id}\t{session_label(meta)}")
            ranked.append((6, ticket_id, action, detail, True))
        elif action == "review":
            review.append(f"รอรีวิว\t{ticket_id}\t{detail}")
            ranked.append((2, ticket_id, action, detail, True))
        elif action == "human" and detail.startswith("review and merge"):
            merge.append(f"รอ merge\t{ticket_id}\t{detail}")
            ranked.append((3, ticket_id, action, detail, True))
        elif action == "work":
            ranked.append((0, ticket_id, action, detail, False))
        elif action == "board":
            ranked.append((1, ticket_id, action, detail, False))
        elif action == "human":
            ranked.append((4, ticket_id, action, detail, False))
        elif action == "stuck":
            ranked.append((5, ticket_id, action, detail, False))
        elif action == "elsewhere":
            ranked.append((7, ticket_id, action, detail, False))
        else:
            ranked.append((8, ticket_id, action, detail, False))
    print(readiness)
    for lines, empty in (
        (doing, "กำลังทำ\t-"),
        (review, "รอรีวิว\t-"),
        (merge, "รอ merge\t-"),
        (choices, "choice รอยืนยัน\t-"),
    ):
        for line in lines or [empty]:
            print(line)
    if ranked:
        ranked.sort()
        for index, (_rank, ticket_id, action, detail, grouped) in enumerate(ranked):
            if index == 0 or not grouped:
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
