#!/usr/bin/env python3
"""jtek inner loop: one ticket, one session, one worktree.

State lives under the repository's common git directory, so every worktree
sees the same claims and no tracked file is shared between sessions.
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

TEMPLATE = """# {title}
id: {id}
status: Backlog

## Goal

## Done when
-

## Out of scope
"""


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
    done = [line for line in sections.get("done when", []) if re.match(r"^\s*-\s*\S", line)]
    if not done:
        raise Refuse("ticket has no item under `## Done when`")
    wanted = [name.strip() for name in ticket["fields"].get("checks", "").split(",") if name.strip()]
    unknown = [name for name in wanted if name not in checks]
    if unknown:
        raise Refuse(
            f"ticket names checks that {CONFIG} does not declare: {', '.join(unknown)}. "
            "A ticket may only name a declared check; it cannot add a command"
        )
    return wanted or list(checks)


def set_fields(path: Path, updates: dict[str, str]) -> None:
    """Rewrite `key: value` lines in the ticket header. An empty value removes the line."""
    lines = path.read_text().splitlines()
    end = next((i for i, line in enumerate(lines) if line.startswith("## ")), len(lines))
    head, rest = lines[:end], lines[end:]
    pending = dict(updates)
    kept = []
    for line in head:
        match = re.match(r"^([A-Za-z][A-Za-z -]*):", line)
        key = match.group(1).strip().lower() if match else None
        if key in pending:
            value = pending.pop(key)
            if value:
                kept.append(f"{key}: {value}")
        else:
            kept.append(line)
    while kept and not kept[-1].strip():
        kept.pop()
    kept += [f"{key}: {value}" for key, value in pending.items() if value]
    path.write_text("\n".join(kept + [""] + rest) + "\n")


# ---- per-ticket state ------------------------------------------------------

def check_id(ticket_id: str) -> str:
    if not ID_RE.match(ticket_id or ""):
        raise Refuse(f"bad ticket id `{ticket_id}`; use letters, digits, `.`, `_`, `-`")
    return ticket_id


def work_dir(ticket_id: str) -> Path:
    return state_dir() / "work" / check_id(ticket_id)


def tickets_dir() -> Path:
    return state_dir() / "tickets"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n")


def load_meta(ticket_id: str) -> dict:
    meta = read_json(work_dir(ticket_id) / "meta.json")
    if not meta:
        raise Refuse(f"{ticket_id} is not started; run `jtek.py start {ticket_id}`")
    return meta


def mirror(meta: dict, updates: dict[str, str]) -> None:
    """A local ticket file is the source of truth for its status. Other sources are updated by the caller."""
    if meta.get("kind") == "local" and Path(meta["ticket"]).exists():
        set_fields(Path(meta["ticket"]), updates)


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
    notes = []
    for path in changed:
        if path in run_by:
            notes.append(f"{path} (run by `{run_by[path]}`)")
        elif any(fnmatch.fnmatch(path, pattern) for pattern in watch):
            notes.append(path)
        elif path in deleted and "test" in path.lower():
            notes.append(f"{path} (test deleted)")
    return ", ".join(notes) or "-"


def write_result(ticket_id: str, outcome: str, status: str, note: str = "", waiting: str = "") -> str:
    work = work_dir(ticket_id)
    meta = load_meta(ticket_id)
    checks = read_json(work / "checks.json")
    verdict = read_json(work / "verdict.json")
    check_line = " ".join(f"{r['name']}={r['status']}" for r in checks.get("results", [])) or "not run"
    if checks.get("sha"):
        check_line += f" @{checks['sha'][:7]}"
    evidence = str(work / "evidence.md") if (work / "evidence.md").exists() else "-"
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
        f"evidence: {evidence}",
        f"attention: {attention(meta)}",
        f"branch: {meta['branch']}",
        f"source: {meta['source']}",
        f"note: {note or '-'}",
    ]
    text = "\n".join(lines) + "\n"
    (work / "result.md").write_text(text)
    return text


# ---- commands --------------------------------------------------------------

def cmd_init(args: argparse.Namespace) -> None:
    path = Path(git("rev-parse", "--show-toplevel")) / CONFIG
    if path.exists():
        raise Refuse(f"{path} already exists")
    write_json(path, {"setup": "", "checks": {"lint": "", "types": "", "test": "", "verify": ""}})
    print(f"wrote {path}")
    print("`setup` installs dependencies in a new worktree, for example `npm ci`. Leave it empty when nothing is needed.")
    print("Fill in one command per check (no shell operators; put a pipeline in a script).")
    print("Delete a check the project does not have. The human commits this file on the base branch.")


def cmd_add(args: argparse.Namespace) -> None:
    folder = tickets_dir()
    folder.mkdir(parents=True, exist_ok=True)
    number = 1
    while True:
        ticket_id = check_id(args.id) if args.id else f"T-{number}"
        path = folder / f"{ticket_id}.md"
        try:
            with open(path, "x") as handle:
                handle.write(TEMPLATE.format(title=args.title, id=ticket_id))
            break
        except FileExistsError:
            if args.id:
                raise Refuse(f"ticket {ticket_id} already exists") from None
            number += 1
    print(f"added {ticket_id} in Backlog: {path}")
    print("The human fills it in and sets `status: Todo` to release it.")


def resolve_source(args: argparse.Namespace) -> tuple[str, str, str, Path | None]:
    """Return (kind, source label, ticket text, local ticket path)."""
    if args.from_file:
        return "external", args.ref, Path(args.from_file).read_text(), None
    candidate = Path(args.ref).expanduser()
    if not candidate.is_file():
        candidate = tickets_dir() / f"{args.ref}.md"
    if candidate.is_file():
        return "local", f"local:{candidate}", candidate.read_text(), candidate.resolve()
    if ID_RE.match(args.ref) and (work_dir(args.ref) / "meta.json").exists():
        # a ticket from another system that this machine already claimed: reuse its snapshot
        meta = load_meta(args.ref)
        return "external", meta["source"], (work_dir(args.ref) / "ticket.md").read_text(), None
    raise Refuse(f"no local ticket `{args.ref}`; for a ticket from another system pass --from-file")


def cmd_start(args: argparse.Namespace) -> None:
    kind, source, text, ticket_path = resolve_source(args)
    ticket = parse_ticket(text)
    ticket_id = check_id(args.id or ticket["fields"].get("id") or (ticket_path.stem if ticket_path else ""))
    base = base_branch()
    declared = load_checks(base)
    selected = validate_ticket(ticket, declared)
    status = ticket["fields"].get("status", "")
    work = work_dir(ticket_id)
    # A claim is parked once its session ended with a result. A parked claim can be picked up again.
    parked = (work / "result.md").exists()

    if args.resume or parked:
        meta = load_meta(ticket_id)
        if not Path(meta["worktree"]).is_dir():
            raise Refuse(f"worktree for {ticket_id} is gone; nothing to resume")
        if status not in ("Todo", "In Progress"):
            raise Refuse(f"{ticket_id} is `{status}`; only a ticket in Todo or In Progress can resume")
        (work / "result.md").unlink(missing_ok=True)
        checks_path = work / "checks.json"
        if checks_path.exists():
            write_json(checks_path, {**read_json(checks_path), "failed_runs": 0})
        resumed = True
    else:
        resumed = False
        if work.exists():
            raise Refuse(CLAIMED.format(id=ticket_id))
        # Another system has no atomic claim, so its launcher may have set In Progress already.
        allowed = ("Todo",) if kind == "local" else ("Todo", "In Progress")
        if status not in allowed:
            raise Refuse(f"{ticket_id} is `{status or 'unset'}`, not Todo; the human releases a ticket by setting `status: Todo`")
        for dep in [d.strip() for d in ticket["fields"].get("after", "").split(",") if d.strip()]:
            dep_path = tickets_dir() / f"{dep}.md"
            if kind == "local" and (
                not dep_path.exists() or parse_ticket(dep_path.read_text())["fields"].get("status") != "Done"
            ):
                raise Refuse(f"{ticket_id} comes after {dep}, which is not Done")
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

        def give_back(reason: str, log: Path) -> Refuse:
            git("worktree", "remove", "--force", str(worktree))
            git("branch", "-D", branch)
            work.rmdir()
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
            "id": ticket_id, "kind": kind, "source": source,
            "ticket": str(ticket_path) if ticket_path else "",
            "base": base, "worktree": str(worktree), "branch": branch, "pr": "",
        }

    meta["checks"] = selected
    # Every change needs a verdict from a session that did not write it. The human may waive that per ticket.
    meta["review"] = ticket["fields"].get("review", "").lower() != "human"
    write_json(work / "meta.json", meta)
    (work / "ticket.md").write_text(text)
    mirror(meta, {"status": "In Progress", "waiting": ""})
    print("jtek start: resumed" if resumed else "jtek start: allowed")
    print(f"id: {ticket_id}")
    print(f"worktree: {meta['worktree']}")
    print(f"branch: {meta['branch']}")
    print(f"base: {meta['base']}")
    print(f"ticket: {work / 'ticket.md'}  (a copy taken now; read this file)")
    print(f"checks: {', '.join(selected)}")
    print(f"review: {'a verdict from a session that did not write the code is required' if meta['review'] else 'human only (the ticket says `review: human`)'}")
    if resumed and (work / "review.md").exists():
        print(f"review notes: {work / 'review.md'}")
    print("next: work only inside the worktree, commit, then `jtek.py check " + ticket_id + "`")


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
        state, head = pr_info(meta["pr"])
        if state != "unknown" and (state != "OPEN" or head != sha):
            raise Refuse(f"{meta['pr']} is {state} at {head[:7]}, not open at the current commit {sha[:7]}; push the branch")
        pr_note = "" if state == "OPEN" else " The PR link was not verified because gh could not read it."
    verdict = read_json(work / "verdict.json")
    if verdict.get("patch") != patch_id(Path(meta["worktree"]), meta["base"]):
        verdict = {}  # a verdict belongs to one change; new content needs a new verdict
    if meta.get("review") and not verdict:
        print(write_result(args.id, "needs-review", "In Progress",
                           note="start a session that did not write this code and run jt-review for this id." + pr_note),
              end="")
        return
    if verdict.get("verdict") == "FAIL":
        raise Refuse(f"verdict is FAIL; read {work / 'review.md'}, fix what reproduces, commit, check, and get a new verdict")
    mirror(meta, {"status": "Review", "waiting": "", "pr": meta["pr"]})
    print(write_result(args.id, "review", "Review", note="the human reviews and merges; jtek never merges." + pr_note),
          end="")


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
    mirror(meta, {"waiting": args.waiting})
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
    print(f"checks: {', '.join(meta['checks'])}")
    print(f"pr: {meta.get('pr') or '-'}")


def pr_info(url: str) -> tuple[str, str]:
    """Return (state, head commit) from the forge, or ("unknown", "") when gh cannot answer."""
    try:
        proc = subprocess.run(
            ["gh", "pr", "view", url, "--json", "state,headRefOid", "-q", '.state + " " + .headRefOid'],
            capture_output=True, text=True, timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unknown", ""
    parts = proc.stdout.split()
    return (parts[0], parts[1]) if proc.returncode == 0 and len(parts) == 2 else ("unknown", "")


def tidy_done(ticket_id: str) -> None:
    """Remove the worktree of a finished ticket. Git refuses when it has uncommitted files, and then it stays."""
    meta = read_json(work_dir(ticket_id) / "meta.json")
    if meta and Path(meta["worktree"]).is_dir():
        if subprocess.run(["git", "worktree", "remove", meta["worktree"]], capture_output=True).returncode == 0:
            # -d deletes only a merged branch, so unmerged work is never lost here
            subprocess.run(["git", "branch", "-d", meta["branch"]], capture_output=True)


def cmd_list(args: argparse.Namespace) -> None:
    rows: dict[str, list[str]] = {status: [] for status in STATUSES}
    folder = tickets_dir()
    for path in sorted(folder.glob("*.md")) if folder.is_dir() else []:
        ticket = parse_ticket(path.read_text())
        fields = ticket["fields"]
        status = fields.get("status", "Backlog")
        if args.sync and status == "Review" and fields.get("pr"):
            state, _ = pr_info(fields["pr"])  # Done is read back from the forge, never assumed
            if state == "MERGED":
                set_fields(path, {"status": "Done"})
                status = "Done"
            elif state != "OPEN":
                fields["note"] = f"PR state: {state}"
        if args.sync and status == "Done":
            tidy_done(path.stem)
        extra = "".join(f"  [{key}: {fields[key]}]" for key in ("waiting", "after", "pr", "note") if fields.get(key))
        rows.setdefault(status, []).append(f"  {path.stem}  {ticket['title']}{extra}")
    for status, items in rows.items():
        print(f"{status} ({len(items)})")
        print("\n".join(items) if items else "  -")


def cmd_release(args: argparse.Namespace) -> None:
    meta = load_meta(args.id)
    work = work_dir(args.id)
    if Path(meta["worktree"]).is_dir():
        git("worktree", "remove", meta["worktree"])  # git refuses when it has uncommitted changes
    for path in sorted(work.rglob("*"), reverse=True):
        path.rmdir() if path.is_dir() else path.unlink()
    work.rmdir()
    print(f"released {args.id}; branch {meta['branch']} is kept")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jtek.py", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="write a jtek.json template").set_defaults(func=cmd_init)

    add = sub.add_parser("add", help="add a local ticket in Backlog")
    add.add_argument("--title", required=True)
    add.add_argument("--id")
    add.set_defaults(func=cmd_add)

    start = sub.add_parser("start", help="claim a ticket and create its worktree")
    start.add_argument("ref", help="local ticket id or path; with --from-file, a label such as the Notion URL")
    start.add_argument("--from-file", help="ticket text fetched from another system")
    start.add_argument("--id")
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

    listing = sub.add_parser("list", help="print the local board")
    listing.add_argument("--sync", action="store_true",
                         help="set Review tickets to Done when their PR is merged, and remove the worktrees of Done tickets")
    listing.set_defaults(func=cmd_list)
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
