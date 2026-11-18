#!/usr/bin/env python3
"""jtek inner loop: one ticket, one session, one worktree.

The board is a Notion database, which the agent reads and writes with its own
Notion tool. This script never talks to Notion: it takes the ticket as a file
and prints what to write back. Claims, logs, and results live under the
repository's common git directory, so every worktree sees the same claims and
no tracked file is shared between sessions.
Standard library only. Python 3.10+.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

STATUSES = ["Backlog", "Todo", "In Progress", "Review", "Done", "Cancelled"]
VERDICTS = ["PASS", "PASS+NOTES", "FAIL"]
WAITING = ["input", "approval"]
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
CONFIG = "jtek.json"
MAX_FAILED_RUNS = 3
MAX_EVIDENCE_LINES = 40
DEFAULT_TIMEOUT = 1800
# Files a human should look at first when a ticket touches them.
SENSITIVE = [
    CONFIG, ".jtek/*", ".github/*", ".gitlab-ci.yml", "package-lock.json", "pnpm-lock.yaml", "yarn.lock",
    "poetry.lock", "uv.lock", "Cargo.lock", "go.sum", "Gemfile.lock",
]

class Refuse(Exception):
    """A rule is not met. The message says what to do next."""


def git(*args: str, cwd: Path | None = None, check: bool = True) -> str:
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise Refuse(f"git {' '.join(args)}: {proc.stderr.strip() or proc.stdout.strip()}")
    return proc.stdout.strip()


def common_dir() -> Path:
    out = git("rev-parse", "--git-common-dir")
    return (Path.cwd() / out).resolve()


def state_dir() -> Path:
    override = os.environ.get("JTEK_STATE")
    return Path(override).expanduser().resolve() if override else common_dir() / "jtek"


def main_root() -> Path:
    for line in git("worktree", "list", "--porcelain").splitlines():
        if line.startswith("worktree "):
            return Path(line[len("worktree "):])
    raise Refuse("no main worktree found")


def base_branch() -> str:
    override = os.environ.get("JTEK_BASE")
    if override:
        return override
    head = git("symbolic-ref", "--short", "refs/remotes/origin/HEAD", check=False)
    if head.startswith("origin/"):
        return head[len("origin/"):]
    for name in ("main", "master"):
        if git("rev-parse", "--verify", "--quiet", f"refs/heads/{name}", check=False):
            return name
    raise Refuse("cannot find the base branch; set JTEK_BASE")


def load_config(base: str) -> dict:
    """The config comes from the base branch, never from the ticket or the worktree."""
    proc = subprocess.run(["git", "show", f"{base}:{CONFIG}"], capture_output=True, text=True)
    if proc.returncode != 0:
        raise Refuse(f"{CONFIG} is not committed on {base}; run `jtek.py init`, fill it in, and have the human merge it")
    try:
        config = json.loads(proc.stdout)
    except json.JSONDecodeError as err:
        raise Refuse(f"{CONFIG} on {base} is not valid JSON: {err}") from err
    if not isinstance(config, dict):
        raise Refuse(f"{CONFIG} on {base} must be a JSON object")
    return config


def load_checks(base: str) -> dict[str, str]:
    checks = load_config(base).get("checks", {})
    if not isinstance(checks, dict) or not checks:
        raise Refuse(f"{CONFIG} on {base} declares no checks; a ticket needs at least one real check")
    for name, cmd in checks.items():
        if not isinstance(cmd, str) or not cmd.strip():
            raise Refuse(f"check `{name}` in {CONFIG} has no command")
    return checks


# ---- ticket text -----------------------------------------------------------

def parse_ticket(text: str) -> dict:
    fields: dict[str, str] = {}
    sections: dict[str, list[str]] = {}
    title, current = "", None
    for line in text.splitlines():
        if line.startswith("## "):
            current = line[3:].strip().lower()
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
        elif line.startswith("# ") and not title:
            title = line[2:].strip()
        else:
            match = re.match(r"^([A-Za-z][A-Za-z -]*):\s*(.*)$", line)
            if match:
                fields[match.group(1).strip().lower()] = match.group(2).strip()
    return {"title": title, "fields": fields, "sections": sections}


def validate_ticket(ticket: dict, checks: dict[str, str]) -> list[str]:
    sections = ticket["sections"]
    if not any(line.strip() for line in sections.get("goal", [])):
        raise Refuse("ticket has no `## Goal`")
    done = [line for line in sections.get("done when", []) if re.match(r"^-\s*\S", line)]
    if not done:
        raise Refuse("ticket has no item under `## Done when`")
    other = [line for line in sections.get("done when", []) if line.strip() and not re.match(r"^-\s*\S", line)]
    if other:
        raise Refuse("`Done when` may hold only top-level list items, one outcome each, because every item must be "
                     f"answered in the evidence. Not an item: {other[0].strip()[:80]}")
    wanted = [name.strip() for name in ticket["fields"].get("checks", "").split(",") if name.strip()]
    unknown = [name for name in wanted if name not in checks]
    if unknown:
        raise Refuse(
            f"ticket names checks that {CONFIG} does not declare: {', '.join(unknown)}. "
            "A ticket may only name a declared check; it cannot add a command"
        )
    return wanted or list(checks)


# ---- per-ticket state ------------------------------------------------------

def check_id(ticket_id: str) -> str:
    if not ID_RE.match(ticket_id or ""):
        raise Refuse(f"bad ticket id `{ticket_id}`; use letters, digits, `.`, `_`, `-`")
    return ticket_id


def work_dir(ticket_id: str) -> Path:
    return state_dir() / "work" / check_id(ticket_id)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n")


def load_meta(ticket_id: str) -> dict:
    meta = read_json(work_dir(ticket_id) / "meta.json")
    if not meta:
        raise Refuse(f"{ticket_id} is not started; run `jtek.py start {ticket_id}`")
    return meta


def head_state(worktree: Path) -> tuple[str, str]:
    """Return the commit and the uncommitted files. Untracked files count: a new file that was
    never added would pass the checks here and be missing from the pull request."""
    sha = git("rev-parse", "HEAD", cwd=worktree)
    return sha, git("status", "--porcelain", cwd=worktree)


CLAIMED = (
    "{id} is already claimed and its session has not ended with a result. "
    "Pick another ticket. If that session died, the human runs start with --resume"
)
def patch_id(worktree: Path, base: str) -> str:
    """Identify the change by its content, so a rebase that changes nothing keeps its verdict."""
    diff = subprocess.run(["git", "diff", f"{base}...HEAD"], cwd=worktree, capture_output=True, text=True)
    proc = subprocess.run(["git", "patch-id", "--stable"], input=diff.stdout, capture_output=True, text=True)
    return proc.stdout.split()[0] if proc.stdout.split() else ""


DIRTY_HINT = "commit them, or add build output to .gitignore"


def done_when_items(work: Path) -> list[str]:
    ticket = parse_ticket((work / "ticket.md").read_text())
    return [m.group(1).strip() for line in ticket["sections"].get("done when", [])
            if (m := re.match(r"^\s*-\s*(\S.*)$", line))]


def attention(meta: dict) -> str:
    """Name what the human should look at before the diff: files that decide whether checks pass."""
    worktree = Path(meta["worktree"])
    if not worktree.is_dir():
        return "-"
    span = f"{meta['base']}...HEAD"
    changed = git("diff", "--name-only", span, cwd=worktree, check=False).splitlines()
    deleted = git("diff", "--name-only", "--diff-filter=D", span, cwd=worktree, check=False).splitlines()
    try:
        config = load_config(meta["base"])
    except Refuse:
        config = {}
    commands = dict(config.get("checks", {})) if isinstance(config.get("checks"), dict) else {}
    if config.get("setup"):
        commands["setup"] = config["setup"]
    run_by: dict[str, str] = {}
    for name, command in commands.items():
        try:
            tokens = shlex.split(str(command))
        except ValueError:
            continue
        for token in tokens:
            run_by.setdefault(token.removeprefix("./"), name)
    watch = SENSITIVE + [w for w in config.get("watch", []) if isinstance(w, str)]
    removed: dict[str, int] = {}
    for line in git("diff", "--numstat", span, cwd=worktree, check=False).splitlines():
        parts = line.split("\t")
        if len(parts) == 3 and parts[1].isdigit():
            removed[parts[2]] = int(parts[1])
    notes = []
    for path in changed:
        if path in run_by:
            notes.append(f"{path} (run by `{run_by[path]}`)")
        elif any(fnmatch.fnmatch(path, pattern) for pattern in watch):
            notes.append(path)
        elif path in deleted and "test" in path.lower():
            notes.append(f"{path} (test deleted)")
        elif "test" in path.lower() and removed.get(path):
            # Adding tests is normal. Removing or rewriting lines of an existing test is how a check gets weakened.
            notes.append(f"{path} ({removed[path]} test lines removed or changed)")
    return ", ".join(notes) or "-"


def board_line(outcome: str, waiting: str = "", pr: str = "") -> str:
    """What the session must now write on the ticket's page with its Notion tool. `-` means nothing."""
    if outcome == "review":
        return "Status=Review; Waiting=; " + (f"PR={pr}; " if pr else "") + "comment=result+evidence"
    if outcome == "needs-human":
        return f"Waiting={waiting}; comment=result"
    return "-"


def write_result(ticket_id: str, outcome: str, status: str, note: str = "", waiting: str = "") -> str:
    work = work_dir(ticket_id)
    meta = load_meta(ticket_id)
    checks = read_json(work / "checks.json")
    verdict = read_json(work / "verdict.json")
    check_line = " ".join(f"{r['name']}={r['status']}" for r in checks.get("results", [])) or "not run"
    if checks.get("sha"):
        check_line += f" @{checks['sha'][:7]}"
    evidence = "-"
    if (work / "evidence.md").exists():
        text = (work / "evidence.md").read_text()
        seen = len(re.findall(r"^\s*\d+\.\s*seen:", text, re.M))
        not_run = len(re.findall(r"^\s*\d+\.\s*not run:", text, re.M))
        evidence = f"{work / 'evidence.md'} ({seen} seen, {not_run} not run)"
    attached = sorted(p.name for p in (work / "evidence").glob("*")) if (work / "evidence").is_dir() else []
    if attached:
        evidence += f" (+{len(attached)} attached in {work / 'evidence'})"
    verdict_line = "none" if meta.get("review") else "waived by the ticket"
    if verdict:
        verdict_line = f"{verdict['verdict']} by {verdict['by']} @{verdict['sha'][:7]}"
    lines = [
        "jtek-result",
        f"id: {ticket_id}",
        f"status: {status}",
        f"outcome: {outcome}",
        f"waiting: {waiting or '-'}",
        f"checks: {check_line}",
        f"verdict: {verdict_line}",
        f"pr: {meta.get('pr') or '-'}",
        f"ci: {meta.get('ci') or '-'}",
        f"evidence: {evidence}",
        f"attention: {attention(meta)}",
        f"branch: {meta['branch']}",
        f"source: {meta['source']}",
        f"note: {note or '-'}",
        f"board: {board_line(outcome, waiting, meta.get('pr', ''))}",
    ]
    text = "\n".join(lines) + "\n"
    (work / "result.md").write_text(text)
    return text


# ---- the board ----------------------------------------------------------------

def load_board(path: str) -> list[dict]:
    """Rows that the launcher read from the board with its Notion tool: one object per open ticket."""
    try:
        rows = json.loads(Path(path).read_text())
    except (OSError, ValueError) as err:
        raise Refuse(f"cannot read the board file {path}: {err}") from None
    if not isinstance(rows, list) or not all(isinstance(row, dict) and row.get("id") for row in rows):
        raise Refuse("the board file must be a JSON list of objects, each with `id` and `status`; "
                     "see references/starting-sessions.md")
    for row in rows:
        after = row.get("after") or []
        row["after"] = [item.strip() for item in after.split(",") if item.strip()] if isinstance(after, str) else list(after)
        for key in ("status", "repo", "waiting", "pr", "title"):
            row[key] = str(row.get(key) or "").strip()
    return rows


# ---- commands --------------------------------------------------------------

def cmd_init(args: argparse.Namespace) -> None:
    path = Path(git("rev-parse", "--show-toplevel")) / CONFIG
    if path.exists():
        raise Refuse(f"{path} already exists")
    write_json(path, {"board": "", "setup": "", "checks": {"secrets": "", "lint": "", "types": "", "test": "", "audit": "", "verify": ""}})
    print(f"wrote {path}")
    print("`board` is the link of the Notion database that holds the tickets. The agent reads it to find a ticket.")
    print("`setup` installs dependencies in a new worktree, for example `npm ci`. Leave it empty when nothing is needed.")
    print("Fill in one command per check (no shell operators; put a pipeline in a script).")
    print("`secrets` is a secret scanner and `audit` a dependency audit, when the project has them.")
    print("Delete a check the project does not have. The human commits this file on the base branch.")


def cmd_start(args: argparse.Namespace) -> None:
    try:
        text = Path(args.from_file).read_text()
    except OSError as err:
        raise Refuse(f"cannot read the ticket file: {err}") from None
    ticket = parse_ticket(text)
    fields = ticket["fields"]
    ticket_id = check_id(fields.get("id", ""))
    base = base_branch()
    declared = load_checks(base)
    selected = validate_ticket(ticket, declared)
    wanted_repo = fields.get("repo", "")
    this_repo = str(load_config(base).get("name") or main_root().name)
    if wanted_repo and wanted_repo != this_repo:
        raise Refuse(
            f"{ticket_id} is for the repository `{wanted_repo}`, and this one is `{this_repo}`. "
            "Start the session in that repository"
        )
    status = fields.get("status", "")
    waiting = fields.get("waiting", "")
    work = work_dir(ticket_id)
    # A claim is parked once its session ended with a result. A parked claim can be picked up again.
    parked = (work / "result.md").exists()

    if args.resume or parked:
        meta = load_meta(ticket_id)
        if not Path(meta["worktree"]).is_dir():
            raise Refuse(f"worktree for {ticket_id} is gone; nothing to resume")
        if status not in ("Todo", "In Progress"):
            raise Refuse(f"{ticket_id} is `{status}`; only a ticket in Todo or In Progress can resume")
        asked = parked and "outcome: needs-human" in (work / "result.md").read_text()
        if (asked or waiting) and status != "Todo":
            # Only the human sets Todo, so a ticket that stopped with a question cannot be restarted by a session.
            raise Refuse(f"{ticket_id} stopped with a question. The human answers on the page and sets Status to Todo")
        (work / "result.md").unlink(missing_ok=True)
        checks_path = work / "checks.json"
        if checks_path.exists():
            write_json(checks_path, {**read_json(checks_path), "failed_runs": 0})
        resumed = True
    else:
        resumed = False
        if work.exists():
            raise Refuse(CLAIMED.format(id=ticket_id))
        if status != "Todo":
            raise Refuse(f"{ticket_id} is `{status or 'unset'}`, not Todo; the human releases a ticket by setting Status to Todo")
        if fields.get("after"):
            raise Refuse(f"{ticket_id} comes after {fields['after']}, which is not Done")
        work.parent.mkdir(parents=True, exist_ok=True)
        try:
            work.mkdir()  # atomic claim: the second session to try loses
        except FileExistsError:
            raise Refuse(CLAIMED.format(id=ticket_id)) from None
        root = main_root()
        worktree = root.parent / f"{root.name}.jtek" / ticket_id
        branch = f"jtek/{ticket_id}"
        try:
            worktree.parent.mkdir(parents=True, exist_ok=True)
            git("worktree", "add", "-b", branch, str(worktree), base)
        except Refuse:
            work.rmdir()
            raise
        logs = state_dir() / "baseline" / ticket_id

        def undo() -> None:
            git("worktree", "remove", "--force", str(worktree))
            git("branch", "-D", branch)
            work.rmdir()

        def give_back(reason: str, log: Path) -> Refuse:
            undo()
            return Refuse(f"{reason}, so {ticket_id} was not started and is still Todo.\nlog: {log}\n{log_tail(log)}")

        setup = load_config(base).get("setup", "")
        if isinstance(setup, str) and setup.strip():
            # A new worktree has no installed dependencies. Install them before anything runs.
            if not run_command(setup, worktree, logs / "setup.log"):
                raise give_back(f"the setup command from {CONFIG} failed in the new worktree", logs / "setup.log")
        if not args.no_baseline:
            # A check that is already red on the base is not this ticket's to fix. Find out before any edit.
            # One green run per base commit and command set is enough, so parallel tickets do not repeat it.
            base_sha = git("rev-parse", base)
            key = hashlib.sha256(json.dumps([base_sha, [(n, declared[n]) for n in selected]]).encode()).hexdigest()
            green = state_dir() / "baseline" / "green" / key
            if not green.exists():
                _, failed = run_checks(worktree, selected, declared, logs)
                if failed:
                    raise give_back(
                        f"check `{failed}` fails on {base} before any change (fix {base} first, or pass --no-baseline)",
                        logs / f"{failed}.log",
                    )
                green.parent.mkdir(parents=True, exist_ok=True)
                green.write_text(base_sha + "\n")
        meta = {
            "id": ticket_id, "source": args.ref,
            "base": base, "worktree": str(worktree), "branch": branch, "pr": "",
        }

    meta["checks"] = selected
    # Every change needs a verdict from a session that did not write it. The human may waive that per ticket.
    meta["review"] = ticket["fields"].get("review", "").lower() != "human"
    write_json(work / "meta.json", meta)
    (work / "ticket.md").write_text(text)
    print("jtek start: resumed" if resumed else "jtek start: allowed")
    print("board: Status=In Progress; Waiting=")
    print(f"id: {ticket_id}")
    print(f"worktree: {meta['worktree']}")
    print(f"branch: {meta['branch']}")
    print(f"base: {meta['base']}")
    print(f"ticket: {work / 'ticket.md'}  (a copy taken now; read this file)")
    print(f"checks: {', '.join(selected)}")
    print(f"review: {'a verdict from a session that did not write the code is required' if meta['review'] else 'human only (the ticket says `review: human`)'}")
    if resumed and (work / "review.md").exists():
        print(f"review notes: {work / 'review.md'}")
    kind = ticket["fields"].get("kind", "") or "not set; decide from the Goal"
    print(f"kind: {kind}")
    print("next: follow the playbook for this kind, step by step. Work only inside the worktree")


def run_command(command: str, worktree: Path, log: Path) -> bool:
    """Run one declared command without a shell. The ticket id is in the environment so that
    a command can pick its own port or data folder when several worktrees run at once."""
    env = {**os.environ, "JTEK_TICKET": worktree.name, "JTEK_WORKTREE": str(worktree)}
    log.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(log, "w") as handle:
            proc = subprocess.run(shlex.split(command), cwd=worktree, stdout=handle,
                                  stderr=subprocess.STDOUT, timeout=DEFAULT_TIMEOUT, env=env)
        return proc.returncode == 0
    except (OSError, ValueError, subprocess.TimeoutExpired) as err:
        with open(log, "a") as handle:
            handle.write(f"\njtek: {err}\n")
        return False


def run_checks(worktree: Path, names: list[str], declared: dict[str, str], logs: Path) -> tuple[list[dict], str | None]:
    """Run checks in order and stop at the first failure. Return the results and the failed name."""
    results: list[dict] = []
    for name in names:
        started = time.time()
        ok = run_command(declared[name], worktree, logs / f"{name}.log")
        results.append({"name": name, "status": "pass" if ok else "fail", "seconds": round(time.time() - started, 1)})
        if not ok:
            return results, name
    return results, None


def log_tail(log: Path) -> str:
    return "\n".join(log.read_text(errors="replace").splitlines()[-20:])


def cmd_check(args: argparse.Namespace) -> None:
    meta = load_meta(args.id)
    work = work_dir(args.id)
    worktree = Path(meta["worktree"])
    declared = load_checks(meta["base"])
    missing = [name for name in meta["checks"] if name not in declared]
    if missing:
        raise Refuse(f"{CONFIG} on {meta['base']} no longer declares: {', '.join(missing)}")
    sha, dirty = head_state(worktree)
    previous = read_json(work / "checks.json")
    logs = work / "logs"
    results, failed = run_checks(worktree, meta["checks"], declared, logs)
    failed_runs = previous.get("failed_runs", 0) + 1 if failed else 0
    write_json(work / "checks.json", {"sha": sha, "dirty": bool(dirty), "results": results, "failed_runs": failed_runs})
    for result in results:
        print(f"{result['name']}: {result['status']} ({result['seconds']}s)")
    if failed:
        log = logs / f"{failed}.log"
        print(f"log: {log}")
        print(log_tail(log))
        if failed_runs >= MAX_FAILED_RUNS:
            print(f"next: {failed_runs} failed runs; stop with `jtek.py stop {args.id} --waiting input --note ...`")
        else:
            print(f"next: fix the cause, commit, run check again ({failed_runs}/{MAX_FAILED_RUNS} failed runs)")
        sys.exit(1)
    if dirty:
        print(f"next: all checks pass, but these files are not committed; {DIRTY_HINT} and run check again")
        print(dirty)
    else:
        print(f"next: all checks pass at {sha[:7]}; go on with the next step of your playbook. "
              "Run check again after any new commit")


def cmd_verdict(args: argparse.Namespace) -> None:
    meta = load_meta(args.id)
    work = work_dir(args.id)
    sha, dirty = head_state(Path(meta["worktree"]))
    if dirty:
        raise Refuse(f"a verdict is for a commit, and these files are not committed; {DIRTY_HINT}\n{dirty}")
    if args.verdict != "PASS" and not args.notes_file:
        raise Refuse(f"{args.verdict} needs --notes-file with the findings")
    if args.notes_file:
        (work / "review.md").write_text(Path(args.notes_file).read_text())
    write_json(work / "verdict.json", {
        "verdict": args.verdict, "by": args.by, "sha": sha,
        "patch": patch_id(Path(meta["worktree"]), meta["base"]),
    })
    print(f"verdict: {args.verdict} by {args.by} @{sha[:7]}")


def cmd_finish(args: argparse.Namespace) -> None:
    meta = load_meta(args.id)
    work = work_dir(args.id)
    if args.pr:
        meta["pr"] = args.pr
        write_json(work / "meta.json", meta)
    sha, dirty = head_state(Path(meta["worktree"]))
    checks = read_json(work / "checks.json")
    passed = checks.get("results") and all(r["status"] == "pass" for r in checks["results"])
    ran_all = [r["name"] for r in checks.get("results", [])] == meta["checks"]
    if dirty:
        raise Refuse(f"these files are not committed; {DIRTY_HINT} and run `jtek.py check {args.id}`\n{dirty}")
    if checks.get("dirty") or checks.get("sha") != sha or not passed or not ran_all:
        raise Refuse(f"checks have not passed on the current commit {sha[:7]}; run `jtek.py check {args.id}`")
    if args.evidence_file:
        text = Path(args.evidence_file).read_text()
        lines = [line for line in text.splitlines() if line.strip()]
        if not lines:
            raise Refuse("the evidence file is empty")
        if len(lines) > MAX_EVIDENCE_LINES:
            raise Refuse(
                f"the evidence has {len(lines)} lines; the human reads it before the diff, so keep it to "
                f"{MAX_EVIDENCE_LINES}. Say what you ran and saw for each `Done when` item, and cut the rest"
            )
        items = done_when_items(work)
        missing = [
            f"{n}. {item}" for n, item in enumerate(items, 1)
            if not re.search(rf"^\s*{n}\.\s*(seen|not run):", text, re.M)
        ]
        if missing:
            raise Refuse(
                "the evidence must account for every `Done when` item. Start one line per item with its number and "
                "`seen:` (the command or steps, and the result) or `not run:` (the reason). Missing:\n" + "\n".join(missing)
            )
        (work / "evidence.md").write_text(text)
    for item in args.attach or []:
        source = Path(item)
        if not source.is_file():
            raise Refuse(f"cannot attach {item}: not a file")
        (work / "evidence").mkdir(exist_ok=True)
        (work / "evidence" / source.name).write_bytes(source.read_bytes())
    if not (work / "evidence.md").exists():
        raise Refuse(
            "no evidence yet; the human reviews the evidence before the diff. Write what you ran and saw for each "
            "`Done when` item to a file and pass --evidence-file <file>. Use the same text as the pull request body"
        )
    if args.no_pr:
        pr_note = f" No pull request: the branch {meta['branch']} is local."
    elif not meta["pr"]:
        raise Refuse(
            "no PR yet; open it (ready, not draft) and pass --pr <url>. "
            "Only when this repository has no forge to open one on, pass --no-pr"
        )
    else:
        state, head, ci = pr_info(meta["pr"])
        if state != "unknown" and (state != "OPEN" or head != sha):
            raise Refuse(f"{meta['pr']} is {state} at {head[:7]}, not open at the current commit {sha[:7]}; push the branch")
        if ci == "fail":
            raise Refuse(f"CI is failing on {meta['pr']}; a pull request with red CI is not ready for the human. Fix it first")
        meta["ci"] = ci
        write_json(work / "meta.json", meta)
        pr_note = "" if state == "OPEN" else " The PR link was not verified because gh could not read it."
    verdict = read_json(work / "verdict.json")
    if verdict.get("patch") != patch_id(Path(meta["worktree"]), meta["base"]):
        verdict = {}  # a verdict belongs to one change; new content needs a new verdict
    needs_verdict = meta.get("review")
    if not needs_verdict and attention(meta) != "-":
        # The human waived the review for a small ticket, but this one touches files that decide whether checks pass.
        needs_verdict = True
        pr_note += " `review: human` is ignored because the change touches the files on the attention line."
    if needs_verdict and not verdict:
        print(write_result(args.id, "needs-review", "In Progress",
                           note="start a session that did not write this code and run jt-review for this id." + pr_note), end="")
        return
    if verdict.get("verdict") == "FAIL":
        raise Refuse(f"verdict is FAIL; read {work / 'review.md'}, fix what reproduces, commit, check, and get a new verdict")
    print(write_result(args.id, "review", "Review",
                       note="the human reviews and merges; jtek never merges." + pr_note), end="")


def cmd_stop(args: argparse.Namespace) -> None:
    meta = load_meta(args.id)
    worktree = Path(meta["worktree"])
    if worktree.is_dir():
        _, dirty = head_state(worktree)
        if dirty:
            raise Refuse(
                "these files are not committed, and the next session would not know what they are. "
                f"Commit them as `wip: <what is unfinished>`, or add build output to .gitignore\n{dirty}"
            )
    print(write_result(args.id, "needs-human", "In Progress", note=args.note, waiting=args.waiting), end="")


def cmd_result(args: argparse.Namespace) -> None:
    path = work_dir(args.id) / "result.md"
    if not path.exists():
        raise Refuse(f"{args.id} has no result yet")
    print(path.read_text(), end="")


def cmd_show(args: argparse.Namespace) -> None:
    """Everything a reviewer needs, without the author's chat."""
    meta = load_meta(args.id)
    print(f"ticket: {work_dir(args.id) / 'ticket.md'}")
    print(f"worktree: {meta['worktree']}")
    print(f"diff: git -C {shlex.quote(meta['worktree'])} diff {meta['base']}...HEAD")
    try:
        declared = load_checks(meta["base"])
    except Refuse:
        declared = {}
    for name in meta["checks"]:
        print(f"check {name}: {declared.get(name, '(no longer declared)')}")
    print(f"pr: {meta.get('pr') or '-'}")


CI_QUERY = (
    '.state + " " + .headRefOid + " " + ([.statusCheckRollup[]? | (.conclusion // .state // "PENDING")] '
    '| if length == 0 then "none" '
    'elif any(.[]; . == "FAILURE" or . == "ERROR" or . == "TIMED_OUT" or . == "CANCELLED" or . == "ACTION_REQUIRED") then "fail" '
    'elif all(.[]; . == "SUCCESS" or . == "NEUTRAL" or . == "SKIPPED") then "pass" else "pending" end)'
)


def pr_info(url: str) -> tuple[str, str, str]:
    """Return (state, head commit, CI state) from the forge, or ("unknown", "", "unknown") when gh cannot answer.
    CI state is pass, fail, pending, or none."""
    try:
        proc = subprocess.run(
            ["gh", "pr", "view", url, "--json", "state,headRefOid,statusCheckRollup", "-q", CI_QUERY],
            capture_output=True, text=True, timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unknown", "", "unknown"
    parts = proc.stdout.split()
    if proc.returncode != 0 or len(parts) < 2:
        return "unknown", "", "unknown"
    return parts[0], parts[1], parts[2] if len(parts) > 2 else "unknown"


def tidy_done(ticket_id: str) -> None:
    """Remove the worktree of a finished ticket. Git refuses when it has uncommitted files, and then it stays."""
    meta = read_json(work_dir(ticket_id) / "meta.json")
    if meta and Path(meta["worktree"]).is_dir():
        if subprocess.run(["git", "worktree", "remove", meta["worktree"]], capture_output=True).returncode == 0:
            # -d deletes only a merged branch, so unmerged work is never lost here
            subprocess.run(["git", "branch", "-d", meta["branch"]], capture_output=True)


def cmd_sync(args: argparse.Namespace) -> None:
    """Done is read back from the forge, never assumed. Print what to write on the board, and tidy worktrees."""
    this_repo = str(load_config(base_branch()).get("name") or main_root().name)
    for row in sorted(load_board(args.board_file), key=lambda item: item["id"]):
        if row["repo"] not in ("", this_repo):
            continue
        if row["status"] == "Review" and row["pr"]:
            state, _, ci = pr_info(row["pr"])
            if state == "MERGED":
                print(f"{row['id']}\tboard: Status=Done\tthe pull request is merged")
                tidy_done(row["id"])
            elif state == "OPEN" and ci in ("fail", "pending"):
                print(f"{row['id']}\t-\tCI: {ci}")
            elif state not in ("OPEN", "unknown"):
                print(f"{row['id']}\t-\tPR state: {state}")
        elif row["status"] in ("Done", "Cancelled"):
            tidy_done(row["id"])


def next_step(row: dict, this_repo: str) -> tuple[str, str]:
    """What one open ticket needs now, for whoever starts sessions. The first word is the action:
    `work`, `review`, and `board` are for a session to do. Every other word means do not start one."""
    ticket_id, status = row["id"], row["status"] or "Backlog"
    if row["repo"] not in ("", this_repo):
        return "other", f"belongs to the repository `{row['repo']}`"
    if status == "Backlog":
        return "hold", "not released; the human sets Todo"
    if status in ("Done", "Cancelled"):
        return "hold", "finished"
    if status == "Review":
        return "human", "review and merge " + (row["pr"] or "the branch")
    work = work_dir(ticket_id)
    claimed, parked = (work / "meta.json").exists(), (work / "result.md").exists()
    if work.exists() and not parked:
        return "running", "a session holds the claim. If none is running, it died: the human runs start with --resume"
    if status == "Todo":
        if row["after"]:
            return "hold", "comes after " + ", ".join(row["after"])
        return "work", "the human answered, or asked for rework" if claimed else "new"
    if row["waiting"]:
        return "human", f"waiting for {row['waiting']}; answer on the page and set Status to Todo"
    if not claimed:
        return "elsewhere", "In Progress, and not claimed on this machine"
    outcome = dict(line.split(": ", 1) for line in (work / "result.md").read_text().splitlines() if ": " in line).get("outcome")
    if outcome == "review":
        return "board", f"the page does not show the result; write the `board:` line of `jtek.py result {ticket_id}`"
    if outcome == "needs-human":
        return "board", f"the page does not show the question; write the `board:` line of `jtek.py result {ticket_id}`"
    meta, verdict = load_meta(ticket_id), read_json(work / "verdict.json")
    if not verdict or verdict.get("patch") != patch_id(Path(meta["worktree"]), meta["base"]):
        return "review", "needs a verdict from a session that did not write the change"
    if verdict.get("verdict") == "FAIL":
        return "work", "the verdict is FAIL; the findings are in the review notes"
    return "work", "the verdict is in; finish"


def cmd_next(args: argparse.Namespace) -> None:
    this_repo = str(load_config(base_branch()).get("name") or main_root().name)
    for row in sorted(load_board(args.board_file), key=lambda item: item["id"]):
        action, reason = next_step(row, this_repo)
        if action != "other":
            print(f"{row['id']}\t{action}\t{reason}")


def cmd_doctor(args: argparse.Namespace) -> None:
    """Say what is set up and what is missing, in the order to fix it. Read-only: it runs no check."""
    rows: list[tuple[str, str, str]] = []  # (ok | missing | optional, what, what to do)

    try:
        found = re.search(r"(\d+)\.(\d+)", git("--version", check=False))
    except OSError:
        raise Refuse("git is not installed; install git 2.31 or later") from None
    version = (int(found.group(1)), int(found.group(2))) if found else (0, 0)
    rows.append(("ok" if version >= (2, 31) else "missing", f"git {version[0]}.{version[1]}", "install git 2.31 or later"))
    rows.append(("ok" if sys.version_info >= (3, 10) else "missing",
                 f"Python {sys.version_info[0]}.{sys.version_info[1]}", "run this script with Python 3.10 or later"))
    config: dict = {}
    try:
        base = base_branch()
        rows.append(("ok", f"base branch `{base}`", ""))
        config = load_config(base)
        rows.append(("ok", f"{CONFIG} is committed on {base}", ""))
    except Refuse as err:
        base = ""
        rows.append(("missing", f"{CONFIG} on the base branch", str(err)))
    if config:
        board = str(config.get("board") or "")
        rows.append(("ok" if board else "missing", "`board`: the Notion database link",
                     f"set `board` in {CONFIG} to the link of the board database, and commit it on {base}"))
        checks = config.get("checks") if isinstance(config.get("checks"), dict) else {}
        empty = [name for name, command in checks.items() if not str(command).strip()]
        if not checks:
            rows.append(("missing", "checks", f"declare at least one check in {CONFIG}"))
        elif empty:
            rows.append(("missing", "checks without a command: " + ", ".join(empty),
                         f"fill them in or delete them in {CONFIG}, and commit it on {base}"))
        else:
            rows.append(("ok", "checks: " + ", ".join(checks), ""))
        rows.append(("ok" if "verify" in checks and not empty else "optional", "a `verify` check that runs the real app",
                     "run the jt-harness skill once; without it a passing check only means the code compiles"))
        guide = bool(git("rev-parse", "--verify", "--quiet", f"{base}:.jtek/verify.md", check=False))
        rows.append(("ok" if guide else "optional", f".jtek/verify.md on {base}",
                     "run the jt-harness skill once, review what it wrote, and commit it"))
    rows.append(("ok" if git("remote", "get-url", "origin", check=False) else "optional", "a remote named origin",
                 "without a forge, tickets end with `finish --no-pr` and the human sets Done"))
    rows.append(("ok" if shutil.which("gh") else "optional", "`gh` is installed",
                 "install the GitHub CLI; it is needed to open pull requests and to read their state"))
    for state, what, todo in rows:
        print(f"{state:<9}{what}" + (f"\n         -> {todo}" if state != "ok" and todo else ""))
    if shutil.which("gh"):
        print("not checked: whether `gh` is signed in. Run `gh auth status` to see.")
    print("not checked: Notion. This script cannot see it. Ask your agent to read the board with its Notion tool\n"
          "         and compare the properties with references/notion.md of the jt-work skill.")
    if any(state == "missing" for state, _, _ in rows):
        raise Refuse("something required is missing; fix the first `missing` line and run doctor again")
    print("ready: write a ticket on the board, set it to Todo, and give its id to the jt-work skill")


def cmd_release(args: argparse.Namespace) -> None:
    meta = load_meta(args.id)
    work = work_dir(args.id)
    if Path(meta["worktree"]).is_dir():
        git("worktree", "remove", meta["worktree"])  # git refuses when it has uncommitted changes
    for path in sorted(work.rglob("*"), reverse=True):
        path.rmdir() if path.is_dir() else path.unlink()
    work.rmdir()
    print(f"released {args.id}; branch {meta['branch']} is kept. The board is not changed: set Status on the page yourself")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jtek.py", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="write a jtek.json template").set_defaults(func=cmd_init)
    sub.add_parser("doctor", help="say what is set up in this repository and what is missing").set_defaults(func=cmd_doctor)

    start = sub.add_parser("start", help="claim a ticket and create its worktree")
    start.add_argument("ref", help="the link of the ticket's Notion page; it becomes the `source:` of the result")
    start.add_argument("--from-file", required=True, help="the page, read just now and saved in the ticket format")
    start.add_argument("--resume", action="store_true")
    start.add_argument("--no-baseline", action="store_true", help="do not run the checks on the base first")
    start.set_defaults(func=cmd_start)

    check = sub.add_parser("check", help="run the declared checks in the worktree")
    check.add_argument("id")
    check.set_defaults(func=cmd_check)

    verdict = sub.add_parser("verdict", help="record a non-author verdict for the current commit")
    verdict.add_argument("id")
    verdict.add_argument("verdict", choices=VERDICTS)
    verdict.add_argument("--by", required=True)
    verdict.add_argument("--notes-file")
    verdict.set_defaults(func=cmd_verdict)

    finish = sub.add_parser("finish", help="move to Review when checks and verdict hold on the current commit")
    finish.add_argument("id")
    finish.add_argument("--pr")
    finish.add_argument("--no-pr", action="store_true", help="the repository has no forge; the branch stays local")
    finish.add_argument("--evidence-file", help="what was run and seen for each `Done when` item; required once")
    finish.add_argument("--attach", action="append", help="a screenshot, recording, or output file to keep with the evidence")
    finish.set_defaults(func=cmd_finish)

    stop = sub.add_parser("stop", help="stop and wait for the human")
    stop.add_argument("id")
    stop.add_argument("--waiting", required=True, choices=WAITING)
    stop.add_argument("--note", required=True)
    stop.set_defaults(func=cmd_stop)

    for name, func, text in (("result", cmd_result, "print the last result"),
                             ("show", cmd_show, "print what a reviewer needs"),
                             ("release", cmd_release, "human only: drop the claim and the worktree")):
        item = sub.add_parser(name, help=text)
        item.add_argument("id")
        item.set_defaults(func=func)

    for name, func, text in (
        ("next", cmd_next, "for whoever starts sessions: what each open ticket of this repository needs now"),
        ("sync", cmd_sync, "read the pull request of each Review ticket from the forge, and remove the worktrees of finished tickets"),
    ):
        item = sub.add_parser(name, help=text)
        item.add_argument("--board-file", required=True, help="the open tickets, read from the board and saved as JSON")
        item.set_defaults(func=func)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except Refuse as err:
        print(f"refused: {err}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
