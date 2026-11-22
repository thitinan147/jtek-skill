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
MAX_RUN_OUTPUT = 20000
RUN_CITE = re.compile(r"\bruns? ([0-9]+(?:\s*(?:,\s*and|,|and)\s*[0-9]+)*)")


def cited_runs(text: str) -> list[int]:
    """Run numbers cited in brackets, such as `(run 3)`, `(runs 3 and 4)`, or `(run 7 stand-in, run 5 real service)`."""
    return [int(n) for group in re.findall(r"\(([^()]*)\)", text)
            for found in RUN_CITE.findall(group) for n in re.findall(r"[0-9]+", found)]
# Files a human should look at first when a ticket touches them.
SENSITIVE = [
    CONFIG, ".jtek/*", ".github/*", ".gitlab-ci.yml", "package-lock.json", "pnpm-lock.yaml", "yarn.lock",
    "poetry.lock", "uv.lock", "Cargo.lock", "go.sum", "Gemfile.lock",
    # Files that commonly define what a check command runs.
    "Makefile", "makefile", "GNUmakefile", "justfile", "Justfile", "package.json", "pyproject.toml", "setup.cfg",
    "tox.ini", "noxfile.py", "pytest.ini", "conftest.py",
]

class Refuse(Exception):
    """A rule is not met. The message says what to do next."""


def git(*args: str, cwd: Path | None = None, check: bool = True) -> str:
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise Refuse(f"git {' '.join(args)}: {proc.stderr.strip() or proc.stdout.strip()}")
    return proc.stdout.strip()


def common_dir() -> Path:
    try:
        out = git("rev-parse", "--git-common-dir")
    except Refuse:
        raise Refuse(f"{Path.cwd()} is not inside a git repository. Run jtek.py from the ticket's repository "
                     "or its worktree; `start` printed the worktree's path") from None
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


HEADINGS = ["Goal", "Done when", "Out of scope"]


def load_settings(base: str) -> dict:
    """The optional settings of jtek.json, checked in one place so `doctor` and `start` find a bad value,
    and not the first `check` after the ticket is claimed."""
    config = load_config(base)
    limit = config.get("max_failed_runs", MAX_FAILED_RUNS)
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise Refuse(f"`max_failed_runs` in {CONFIG} must be a whole number of at least 1")
    pr_state = config.get("pr_state") or ""
    try:
        shlex.split(pr_state)
    except (ValueError, AttributeError):
        raise Refuse(f'`pr_state` in {CONFIG} must be one command as text, such as "python3 scripts/pr-state.py"') from None
    names = {} if config.get("headings") is None else config["headings"]
    form = '{"Goal": "...", "Done when": "...", "Out of scope": "..."}'
    if not isinstance(names, dict) or any(not isinstance(v, str) or not v.strip() for v in names.values()):
        raise Refuse(f"`headings` in {CONFIG} must be an object such as {form}")
    unknown = [key for key in names if key not in HEADINGS]
    if unknown:
        raise Refuse(f"`headings` in {CONFIG} has the name `{unknown[0]}`. Its names are exactly: {', '.join(HEADINGS)}")
    own = {key: " ".join(value.split()).lower() for key, value in names.items()}
    if len(set(own.values())) != len(own):
        raise Refuse(f"`headings` in {CONFIG} gives two headings the same words")
    clash = [key for key, value in own.items() if any(value == other.lower() and other != key for other in HEADINGS)]
    if clash:
        raise Refuse(f"`headings` in {CONFIG} names `{clash[0]}` with the English name of another heading")
    return {"max_failed_runs": limit, "pr_state": pr_state.strip(), "headings": own}


# ---- ticket text -----------------------------------------------------------

def fenced(lines: list[str]):
    """Yield (line, inside a code fence). A heading quoted in a fence is text, not a heading."""
    fence = ""
    for line in lines:
        # As in CommonMark: a line such as ```npm test``` is inline code, not the start of a block.
        mark = re.match(r"^ {0,3}(`{3,})[^`]*$|^ {0,3}(~{3,})", line)
        if fence:
            yield line, True
            run = (mark.group(1) or mark.group(2)) if mark else ""
            if run[:1] == fence[0] and len(run) >= len(fence) and not line.strip().strip(fence[0]):
                fence = ""
        elif mark:
            fence = mark.group(1) or mark.group(2)
            yield line, True
        else:
            yield line, False


def parse_ticket(text: str) -> dict:
    fields: dict[str, str] = {}
    sections: dict[str, list[str]] = {}
    repeated: list[str] = []
    title, current = "", None
    for line, inside in fenced(text.splitlines()):
        if line.startswith("## ") and not inside:
            current = line[3:].strip().lower()
            if current in sections:
                repeated.append(line[3:].strip())
            sections.setdefault(current, [])
        elif current is not None:
            sections[current].append(line)
        elif inside:
            continue
        elif line.startswith("# ") and not title:
            title = line[2:].strip()
        else:
            match = re.match(r"^([A-Za-z][A-Za-z -]*):\s*(.*)$", line)
            if match:
                fields[match.group(1).strip().lower()] = match.group(2).strip()
    return {"title": title, "fields": fields, "sections": sections, "repeated": repeated}


def canon_status(value: str) -> str:
    """Notion's own spelling is `In progress`. Accept any case, and refuse a status this board does not have."""
    found = next((s for s in STATUSES if s.lower() == " ".join(value.split()).lower()), None)
    if value and not found:
        raise Refuse(f"`{value}` is not a status of the board; it has: {', '.join(STATUSES)}")
    return found or ""


def validate_ticket(ticket: dict, checks: dict[str, str]) -> list[str]:
    sections = ticket["sections"]
    if ticket.get("repeated"):
        raise Refuse(f"the ticket has the heading `{ticket['repeated'][0]}` twice, so it is not clear which one counts. "
                     "The human gives each heading once; an example of a heading goes inside a code block")
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
    try:
        data = json.loads(path.read_text()) if path.exists() else {}
    except ValueError:
        raise Refuse(f"{path} is damaged; a write was probably interrupted. If it is a ticket's meta.json, run "
                     "`jtek.py release <id>` and start again: the commits stay on the branch. "
                     "Any other file: delete it and run the command that wrote it") from None
    return data if isinstance(data, dict) else {}


def write_json(path: Path, data: dict) -> None:
    """Write beside the file and rename, so a killed run never leaves half a file."""
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n")
    os.replace(tmp, path)


def load_meta(ticket_id: str, tree: bool = False) -> dict:
    """With `tree`, the worktree must still be there."""
    meta = read_json(work_dir(ticket_id) / "meta.json")
    if not meta or meta.get("starting"):
        if work_dir(ticket_id).exists():
            raise Refuse(claimed(ticket_id))
        raise Refuse(f"{ticket_id} is not started in this repository ({main_root()}). If the ticket belongs to another "
                     "repository, run the command from there or from the ticket's worktree. Otherwise read its page and "
                     "run `jtek.py start`")
    if tree and not Path(meta["worktree"]).is_dir():
        raise Refuse(f"the worktree of {ticket_id} is gone: {meta['worktree']}. Run `jtek.py release {ticket_id}`; "
                     f"the commits are on the branch {meta['branch']}")
    return meta


def head_state(worktree: Path) -> tuple[str, str]:
    """Return the commit and the uncommitted files. Untracked files count: a new file that was
    never added would pass the checks here and be missing from the pull request."""
    sha = git("rev-parse", "HEAD", cwd=worktree)
    return sha, git("status", "--porcelain", cwd=worktree)


CLAIMED = (
    "{id} is already claimed and its session has not ended with a result. Pick another ticket. "
    "If that session died, the human tells a new session to take it over, and that session adds --resume"
)


def starting_now(meta: dict) -> bool:
    """True while the `start` that wrote this claim is still running."""
    try:
        pid = int(meta.get("pid") or 0)
        if not meta.get("starting") or pid <= 0:
            return False
        os.kill(pid, 0)  # signal 0 only asks whether that process is alive
        return True
    except (OSError, ValueError, TypeError):
        return False


def claimed(ticket_id: str) -> str:
    """Why a ticket that has a claim cannot be started now."""
    meta = read_json(work_dir(ticket_id) / "meta.json")
    if meta.get("worktree") and not meta.get("starting"):
        return CLAIMED.format(id=ticket_id)
    if starting_now(meta):
        return f"another session is starting {ticket_id} right now. Pick another ticket"
    return f"an earlier start of {ticket_id} was interrupted. Run `jtek.py release {ticket_id}`, then start again"


def patch_id(worktree: Path, base: str) -> str:
    """Identify the change by its content: the diff, and the content of every file it changes, before and after.
    A rebase keeps the verdict unless the base changed a file this change also touches.
    Whitespace counts: in Python or YAML, an indent is a change of behaviour."""
    # Hunk positions are left out below, so the same edit at another place of a file would look the same.
    # --raw adds one line per changed file with the full id of its content before and after, which tells them apart.
    diff = subprocess.run(["git", "diff", "--raw", "--patch", "--no-abbrev", "--no-ext-diff", "--no-textconv", "--binary",
                           "--no-renames", f"{base}...HEAD"], cwd=worktree, capture_output=True)
    kept = [re.sub(rb"^@@ .*? @@", b"@@", line) for line in diff.stdout.split(b"\n") if not line.startswith(b"index ")]
    return hashlib.sha256(b"\n".join(kept)).hexdigest() if diff.stdout.strip() else ""


def ticket_id_of_text(work: Path) -> str:
    """Identify what the ticket asks for, so that a ticket the human changed needs new evidence and a new verdict."""
    sections = parse_ticket((work / "ticket.md").read_text())["sections"]
    return hashlib.sha256(json.dumps(sections, sort_keys=True).encode()).hexdigest()


def current_verdict(ticket_id: str, meta: dict) -> dict:
    """The verdict, when it is for the change and the ticket as they are now."""
    work = work_dir(ticket_id)
    verdict = read_json(work / "verdict.json")
    worktree = Path(meta["worktree"])
    if (not verdict.get("verdict") or not worktree.is_dir() or verdict.get("patch") != patch_id(worktree, meta["base"])
            or verdict.get("ticket") != ticket_id_of_text(work)):
        return {}
    return verdict


def needs_verdict(meta: dict) -> bool:
    """The human may waive the review for a small ticket, but not for one that touches files that decide whether checks pass."""
    return bool(meta.get("review")) or attention(meta) != "-"


DIRTY_HINT = "commit them, or add build output to .gitignore"


def done_when_items(work: Path) -> list[str]:
    ticket = parse_ticket((work / "ticket.md").read_text())
    return [m.group(1).strip() for line in ticket["sections"].get("done when", [])
            if (m := re.match(r"^-\s*(\S.*)$", line))]


def attention(meta: dict) -> str:
    """Name what the human should look at before the diff: files that decide whether checks pass."""
    worktree = Path(meta["worktree"])
    if not worktree.is_dir():
        return "-"
    span = f"{meta['base']}...HEAD"
    # A rename is shown as a deletion and an addition, so a renamed test that lost lines is still seen.
    changed = git("-c", "core.quotePath=false", "diff", "--no-renames", "--name-only", span, cwd=worktree, check=False).splitlines()
    deleted = git("-c", "core.quotePath=false", "diff", "--no-renames", "--name-only", "--diff-filter=D", span, cwd=worktree, check=False).splitlines()
    try:
        config = load_config(meta["base"])
    except Refuse:
        config = {}
    commands = dict(config.get("checks", {})) if isinstance(config.get("checks"), dict) else {}
    for key in ("setup", "pr_state"):
        if config.get(key):
            commands[key] = config[key]
    run_by: dict[str, str] = {}
    for name, command in commands.items():
        try:
            tokens = shlex.split(str(command))
        except ValueError:
            continue
        for token in tokens:
            run_by.setdefault(token.removeprefix("./"), name)
    extra = config.get("watch") or []
    watch = SENSITIVE + [w for w in ([extra] if isinstance(extra, str) else extra if isinstance(extra, list) else [])
                         if isinstance(w, str)]
    removed: dict[str, int] = {}
    for line in git("-c", "core.quotePath=false", "diff", "--no-renames", "--numstat", span, cwd=worktree, check=False).splitlines():
        parts = line.split("\t")
        if len(parts) == 3 and parts[1].isdigit():
            removed[parts[2]] = int(parts[1])
    notes = []
    for path in changed:
        is_test = "test" in path.lower() or "spec" in path.lower()
        if path in run_by:
            notes.append(f"{path} (run by `{run_by[path]}`)")
        elif any(fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(path.rsplit("/", 1)[-1], pattern) for pattern in watch):
            notes.append(path)
        elif path in deleted and is_test:
            notes.append(f"{path} (test deleted)")
        elif is_test and removed.get(path):
            # Adding tests is normal. Removing or rewriting lines of an existing test is how a check gets weakened.
            notes.append(f"{path} ({removed[path]} test lines removed or changed)")
    return ", ".join(notes) or "-"


def board_line(outcome: str, waiting: str = "", pr: str = "") -> str:
    """What the session must now write on the ticket's page with its Notion tool. `-` means nothing."""
    if outcome == "review":
        return "Status=Review; Waiting=; " + (f"PR={pr}; " if pr else "") + "comment=result+evidence"
    if outcome == "needs-human":
        return f"Waiting={waiting}; comment=result"
    # A pull request that waits for its second look is still worth a link on the page.
    return f"PR={pr}" if pr else "-"


def write_result(ticket_id: str, outcome: str, status: str, note: str = "", waiting: str = "") -> str:
    work = work_dir(ticket_id)
    meta = load_meta(ticket_id)
    checks = read_json(work / "checks.json")
    verdict = current_verdict(ticket_id, meta)
    check_line = " ".join(f"{r['name']}={r['status']}" for r in checks.get("results", [])) or "not run"
    if checks.get("sha"):
        check_line += f" @{checks['sha'][:7]}"
    evidence = "-"
    if (work / "evidence.md").exists():
        text = (work / "evidence.md").read_text()
        seen = len(re.findall(r"^\s*\d+\.\s*seen:", text, re.M))
        not_run = len(re.findall(r"^\s*\d+\.\s*not run:", text, re.M))
        backed = len([line for line in re.findall(r"^\s*\d+\.\s*seen:.*$", text, re.M) if cited_runs(line)])
        evidence = f"{work / 'evidence.md'} ({seen} seen, {not_run} not run, {backed} of the seen cite a recorded run"
        cleanup = re.search(r"^\s*(-\s*)?clean-up:.*$", text, re.M | re.I)
        diff_runs = cited_runs(cleanup.group(0)) if cleanup else []
        read_diff = any("git diff" in (work / "runs" / f"{n}.txt").read_text(errors="replace").split("\n", 2)[1]
                        for n in diff_runs if (work / "runs" / f"{n}.txt").exists())
        evidence += ", clean-up rests on a recorded diff)" if read_diff else ", clean-up cites no recorded diff)"
    attached = sorted(p.name for p in (work / "evidence").glob("*")) if (work / "evidence").is_dir() else []
    if attached:
        evidence += f" (+{len(attached)} attached in {work / 'evidence'})"
    verdict_line = "none" if needs_verdict(meta) else "waived by the ticket"
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
        f"note: {' '.join(note.split()) or '-'}",
        f"board: {board_line(outcome, waiting, meta.get('pr', ''))}",
    ]
    if "comment=" in lines[-1]:
        # The comment the board line asks for, ready to paste as it is, so nobody has to put it together or cut it.
        lines.insert(-1, f"comment file: {work / 'board-comment.md'}")
    text = "\n".join(lines) + "\n"
    (work / "result.md").write_text(text)
    if "comment=" in lines[-1]:
        evidence_text = (work / "evidence.md").read_text() if (work / "evidence.md").exists() else ""
        (work / "board-comment.md").write_text(text + ("\n" + evidence_text if "comment=result+evidence" in lines[-1] else ""))
    return text


def ticket_paths(ticket_id: str) -> tuple[Path, str]:
    root = main_root()
    return root.parent / f"{root.name}.jtek" / ticket_id, f"jtek/{ticket_id}"


def cmd_other(args: argparse.Namespace) -> None:
    """Commands for the human and the launcher live in launcher.py and doctor.py beside this file.
    The copy of this file in the jt-review skill does not have them."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        import launcher
    except ImportError:
        raise Refuse(f"`{args.command}` is in launcher.py, in the scripts folder of the jt-work skill; run jtek.py from there") from None
    launcher.COMMANDS[args.command](sys.modules[__name__], args)


# ---- commands --------------------------------------------------------------

def refresh_base(base: str) -> str:
    """Bring the local base branch up to what the remote has, so a ticket starts from what is merged.
    Returns a note for the session, or "". Never rewrites history: only a fast-forward, and only when it is safe."""
    if not git("rev-parse", "--verify", "--quiet", f"refs/heads/{base}", check=False):
        return ""  # the base is not a local branch (JTEK_BASE names something else)
    if "origin" not in git("remote", check=False).split():
        return ""
    try:
        fetched = subprocess.run(["git", "fetch", "--quiet", "origin", base], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        fetched = None
    if fetched is None or fetched.returncode != 0:
        return f"note: could not fetch `{base}` from origin, so the ticket starts from the local `{base}`, which may be old"
    remote = f"refs/remotes/origin/{base}"
    if not git("rev-parse", "--verify", "--quiet", remote, check=False):
        return ""
    behind = int(git("rev-list", "--count", f"{base}..{remote}", check=False) or 0)
    ahead = int(git("rev-list", "--count", f"{remote}..{base}", check=False) or 0)
    if not behind:
        return ""
    if ahead:
        return (f"note: the local `{base}` and origin/{base} have each moved ({ahead} and {behind} commits), "
                f"so the ticket starts from the local `{base}`. The human brings them together")
    # Where is the base checked out? A branch that is checked out moves only by a merge in that worktree.
    holder, path = None, None
    for line in git("worktree", "list", "--porcelain").splitlines():
        if line.startswith("worktree "):
            path = Path(line[len("worktree "):])
        elif line == f"branch refs/heads/{base}":
            holder = path
    if holder is None:
        moved = subprocess.run(["git", "update-ref", f"refs/heads/{base}", remote], capture_output=True, text=True)
    else:
        moved = subprocess.run(["git", "merge", "--quiet", "--ff-only", remote], cwd=holder, capture_output=True, text=True)
    if moved.returncode != 0:
        raise Refuse(
            f"`{base}` is {behind} commits behind origin/{base}, and it could not be moved forward"
            + (f" in {holder}" if holder else "") + f": {' '.join((moved.stderr or moved.stdout).split())}. "
            f"The human updates `{base}` (`git pull --ff-only`); a ticket must start from what is merged"
        )
    return f"note: `{base}` was {behind} commits behind origin/{base} and was moved forward before the ticket started"


def cmd_start(args: argparse.Namespace) -> None:
    try:
        text = Path(args.from_file).read_text()
    except (OSError, ValueError) as err:
        raise Refuse(f"cannot read the ticket file as text: {err}") from None
    base = base_branch()
    # Before anything is read from the base: the checks and the settings come from it too.
    base_note = "" if args.no_fetch else refresh_base(base)
    english = {own: name for name, own in load_settings(base)["headings"].items()}
    if english:
        # The copy the session works from always has the three English headings, whatever the page calls them.
        lines = [f"## {english[' '.join(line[2:].split()).lower()]}"
                 if re.match(r"^##[ \t]", line) and not inside and " ".join(line[2:].split()).lower() in english else line
                 for line, inside in fenced(text.splitlines())]
        text = "\n".join(lines) + "\n"
    ticket = parse_ticket(text)
    fields = ticket["fields"]
    ticket_id = check_id(fields.get("id", ""))
    declared = load_checks(base)
    selected = validate_ticket(ticket, declared)
    wanted_repo = fields.get("repo", "")
    this_repo = str(load_config(base).get("name") or main_root().name)
    if wanted_repo and wanted_repo != this_repo:
        raise Refuse(
            f"{ticket_id} is for the repository `{wanted_repo}`, and this one is `{this_repo}`. "
            "Start the session in that repository"
        )
    status = canon_status(fields.get("status", ""))
    waiting = fields.get("waiting", "")
    work = work_dir(ticket_id)
    # A claim is parked once its session ended with a result. A parked claim can be picked up again.
    parked = (work / "result.md").exists()

    baseline = asked = ""
    if args.resume or parked:
        meta = load_meta(ticket_id, tree=True)
        if status not in ("Todo", "In Progress"):
            raise Refuse(f"{ticket_id} is `{status}`; only a ticket in Todo or In Progress can resume")
        try:
            asked = parked and "outcome: needs-human" in (work / "result.md").read_text()
        except FileNotFoundError:  # another session picked it up between the two lines
            raise Refuse(CLAIMED.format(id=ticket_id)) from None
        if (asked or waiting) and status != "Todo":
            # Only the human sets Todo, so a ticket that stopped with a question cannot be restarted by a session.
            raise Refuse(f"{ticket_id} stopped with a question. The human answers on the page and sets Status to Todo")
        if parked:
            try:
                # A rename happens once, so two sessions cannot both pick up the same parked ticket.
                (work / "result.md").rename(work / "last-result.md")
            except FileNotFoundError:
                raise Refuse(CLAIMED.format(id=ticket_id)) from None
            last = (work / "last-result.md").read_text()
            if "outcome: needs-human" in last:
                # The session that picks the ticket up must not have to open the state folder to learn what was asked.
                asked = next((line[6:].strip() for line in last.splitlines() if line.startswith("note: ")), "")
        checks_path = work / "checks.json"
        if checks_path.exists() and status == "Todo":
            # Only the human sets Todo, so only the human gives a ticket new tries.
            write_json(checks_path, {**read_json(checks_path), "failed_runs": 0})
        resumed = True
    else:
        resumed = False
        if work.exists():
            raise Refuse(claimed(ticket_id))
        if status != "Todo":
            raise Refuse(f"{ticket_id} is `{status or 'unset'}`, not Todo; the human releases a ticket by setting Status to Todo")
        if fields.get("after"):
            raise Refuse(f"{ticket_id} comes after {fields['after']}, which is not Done")
        work.parent.mkdir(parents=True, exist_ok=True)
        try:
            work.mkdir()  # atomic claim: the second session to try loses
        except FileExistsError:
            raise Refuse(claimed(ticket_id)) from None
        worktree, branch = ticket_paths(ticket_id)
        # A branch left by `release` holds earlier work on this ticket. Go on from it, and never delete it.
        kept = bool(git("rev-parse", "--verify", "--quiet", f"refs/heads/{branch}", check=False))
        # From here on a killed run leaves a claim that says so, and `release` can remove what it made.
        write_json(work / "meta.json", {"starting": True, "pid": os.getpid(), "kept": kept, "base": base})
        worktree.parent.mkdir(parents=True, exist_ok=True)
        for attempt in range(3):
            try:
                git("worktree", "prune")  # forget a worktree whose folder was deleted by hand
                # A failed try may have left the branch behind, so look again each time.
                exists = bool(git("rev-parse", "--verify", "--quiet", f"refs/heads/{branch}", check=False))
                git("worktree", "add", *([str(worktree), branch] if exists else ["-b", branch, str(worktree), base]))
                break
            except Refuse:
                # Two tickets that start in the same moment can trip over each other inside git. Try again before giving up.
                if attempt < 2:
                    time.sleep(0.3 * (attempt + 1))
                    continue
                if not kept:
                    git("branch", "-D", branch, check=False)
                (work / "meta.json").unlink()
                work.rmdir()
                raise
        meta = {"id": ticket_id, "source": " ".join(args.ref.split()), "base": base, "worktree": str(worktree), "branch": branch, "pr": ""}
        write_json(work / "meta.json", {**meta, "starting": True, "pid": os.getpid(), "kept": kept})
        logs = state_dir() / "baseline" / ticket_id

        def undo() -> None:
            git("worktree", "remove", "--force", str(worktree), check=False)
            if not kept:
                git("branch", "-D", branch, check=False)
            for path in sorted(work.rglob("*"), reverse=True):
                path.rmdir() if path.is_dir() else path.unlink()
            work.rmdir()

        def give_back(reason: str, log: Path) -> Refuse:
            undo()
            return Refuse(f"{reason}, so {ticket_id} was not started and is still Todo.\nlog: {log}\n{log_tail(log)}")

        setup = load_config(base).get("setup", "")
        if isinstance(setup, str) and setup.strip():
            # A new worktree has no installed dependencies. Install them before anything runs.
            if not run_command(setup, worktree, logs / "setup.log"):
                raise give_back(f"the setup command from {CONFIG} failed in the new worktree", logs / "setup.log")
        baseline = "skipped, because the work goes on from an existing branch" if kept else "skipped (--no-baseline)"
        if not args.no_baseline and not kept:
            # A check that is already red on the base is not this ticket's to fix. Find out before any edit.
            # One green run per base commit and command set is enough, so parallel tickets do not repeat it.
            base_sha = git("rev-parse", base)
            key = hashlib.sha256(json.dumps([base_sha, [(n, declared[n]) for n in selected]]).encode()).hexdigest()
            green = state_dir() / "baseline" / "green" / key
            baseline = f"passed earlier on {base} at {base_sha[:7]} with the same commands; not run again"
            if not green.exists():
                _, failed = run_checks(worktree, selected, declared, logs)
                if failed:
                    raise give_back(
                        f"check `{failed}` fails on {base} before any change (fix {base} first, or pass --no-baseline)",
                        logs / f"{failed}.log",
                    )
                green.parent.mkdir(parents=True, exist_ok=True)
                green.write_text(base_sha + "\n")
                baseline = f"{', '.join(selected)} passed on {base} at {base_sha[:7]} before any change"

    meta["checks"] = selected
    # Every change needs a verdict from a session that did not write it. The human may waive that per ticket.
    meta["review"] = ticket["fields"].get("review", "").lower() != "human"
    write_json(work / "meta.json", meta)
    (work / "ticket.md").write_text(text)
    print("jtek start: resumed" if resumed else "jtek start: allowed")
    if base_note:
        print(base_note)
    if not resumed and kept:
        print(f"note: the branch {branch} already existed, so the work goes on from its commits")
    print("board: Status=In Progress; Waiting=")
    print(f"id: {ticket_id}")
    print(f"worktree: {meta['worktree']}")
    print(f"branch: {meta['branch']}")
    print(f"base: {meta['base']}")
    print(f"ticket: {work / 'ticket.md'}  (a copy taken now; read this file)")
    print(f"checks: {', '.join(selected)}")
    if baseline:
        print(f"baseline: {baseline}")
    if asked:
        print(f"asked: {asked}")
        print("answer: on the page, so in the ticket file above")
    print(f"review: {'a verdict from a session that did not write the code is required' if meta['review'] else 'human only (the ticket says `review: human`)'}")
    if resumed and meta.get("pr"):
        # The human may have said why the ticket is back on the pull request, and nowhere else.
        clash = f" It conflicts with {base}." if pr_conflicts(meta["pr"], base) else ""
        print(f"pull request: {meta['pr']}{clash} Read its comments: the reason the ticket is back may be there")
    if resumed and (work / "verdict.json").exists():
        # A session that picks the ticket up learns here what the reviewer said, not from the state folder.
        last = read_json(work / "verdict.json")
        still = "it is for the change as it is now" if current_verdict(ticket_id, meta) else "the change or the ticket has moved on since"
        print(f"last verdict: {last.get('verdict')} by {last.get('by')} @{str(last.get('sha', ''))[:7]} ({still})")
        fails = int(meta.get("fails", 0))
        if fails:
            print(f"FAIL verdicts so far: {fails}" + (". That is three: stop with `--waiting input`, because the ticket or the "
                                                      "reviewer's standard needs the human" if fails >= 3 else ""))
    if resumed and (work / "review.md").exists():
        print(f"review notes: {work / 'review.md'}")
    kind = ticket["fields"].get("kind", "") or "not set; decide from the Goal"
    print(f"kind: {kind}")
    print("next: follow the playbook for this kind, step by step. Work only inside the worktree")


def ticket_env(ticket_id: str, worktree: Path) -> dict:
    """The session's own environment, plus the ticket id and the worktree, so that a command can pick
    its own port or data folder when several worktrees run at once. Nothing is read from it here."""
    return {**os.environ, "JTEK_TICKET": ticket_id, "JTEK_WORKTREE": str(worktree)}


def run_logged(argv: list[str], cwd: Path, env: dict, log: Path, stdin=None, err_log: Path | None = None) -> int | str:
    """Run one program with its arguments, no shell of jtek's own, with stdout in `log` and stderr there too,
    or in `err_log` when one is given. Returns the exit code, or the reason it did not run."""
    log.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(log, "w") as out, open(err_log or os.devnull, "w") as err:
            return subprocess.run(argv, cwd=cwd, stdout=out, stderr=err if err_log else subprocess.STDOUT,
                                  stdin=stdin, timeout=DEFAULT_TIMEOUT, env=env).returncode
    except (OSError, ValueError, subprocess.TimeoutExpired) as err:
        with open(log, "a") as out:
            out.write(f"\njtek: {err}\n")
        return f"did not run: {err}"


def run_command(command: str, worktree: Path, log: Path) -> bool:
    """Run one declared command."""
    try:
        argv = shlex.split(command)
    except ValueError as err:
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(f"jtek: {err}\n")
        return False
    return run_logged(argv, worktree, ticket_env(worktree.name, worktree), log) == 0


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
    meta = load_meta(args.id, tree=True)
    work = work_dir(args.id)
    worktree = Path(meta["worktree"])
    declared = load_checks(meta["base"])
    missing = [name for name in meta["checks"] if name not in declared]
    if missing:
        raise Refuse(f"{CONFIG} on {meta['base']} no longer declares: {', '.join(missing)}")
    sha, dirty = head_state(worktree)
    previous = read_json(work / "checks.json")
    limit = load_settings(meta["base"])["max_failed_runs"]
    if previous.get("failed_runs", 0) >= limit:
        raise Refuse(f"{limit} check runs have failed. One more guess usually means the design is wrong, not "
                     f"the line. Stop: `jtek.py stop {args.id} --waiting input --note \"<the cause you suspect>\"`")
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
        if failed_runs >= limit:
            print(f"next: {failed_runs} failed runs; stop with `jtek.py stop {args.id} --waiting input --note ...`")
        else:
            print(f"next: fix the cause, commit, run check again ({failed_runs}/{limit} failed runs)")
        sys.exit(1)
    if dirty:
        print(f"next: all checks pass, but these files are not committed; {DIRTY_HINT} and run check again")
        print(dirty)
    else:
        print(f"next: all checks pass at {sha[:7]}; go on with the next step of your playbook. "
              "Run check again after any new commit")


def read_file(path: str, what: str) -> str:
    try:
        return Path(path).read_text()
    except (OSError, ValueError) as err:
        raise Refuse(f"cannot read the {what} file: {err}") from None


def cmd_verdict(args: argparse.Namespace) -> None:
    meta = load_meta(args.id, tree=True)
    work = work_dir(args.id)
    sha, dirty = head_state(Path(meta["worktree"]))
    if dirty and args.verdict != "FAIL":
        # FAIL opens nothing, so it is allowed here: a reviewer must not have to delete the author's files to say so.
        raise Refuse("a pass is for a commit, and these files are not committed. If your review made them, remove "
                     f"them. If the author left them, give FAIL and say so in the notes\n{dirty}")
    patch = patch_id(Path(meta["worktree"]), meta["base"])
    if not patch:
        raise Refuse(f"the branch has no change against {meta['base']}, so there is nothing to give a verdict on")
    if args.verdict != "PASS" and not args.notes_file:
        raise Refuse(f"{args.verdict} needs --notes-file with the findings")
    notes_text = read_file(args.notes_file, "notes") if args.notes_file else ""
    finding = re.search(r"^\s*[-*]\s*reproduces:", notes_text, re.M)
    weigh = re.search(r"^\s*[-*]\s*to weigh:", notes_text, re.M)
    # The word of the verdict and the notes must say the same thing, because the human reads the word first.
    if args.verdict == "FAIL" and not finding:
        raise Refuse("FAIL needs at least one finding in the notes: a line `- reproduces: <what goes wrong>` with its steps. "
                     "Without one, the verdict is PASS or PASS+NOTES")
    if args.verdict != "FAIL" and finding:
        raise Refuse(f"the notes hold a finding (`- reproduces:`), so the verdict is FAIL, not {args.verdict}. "
                     "If it does not count as a finding, write it as a note")
    if args.verdict == "PASS+NOTES" and not weigh:
        raise Refuse("PASS+NOTES is for something the human should decide before merging: a line `- to weigh: <what>`. "
                     "Notes that only say what you saw are a PASS; give PASS and keep --notes-file")
    if args.notes_file:
        (work / "review.md").write_text(notes_text)
    else:
        (work / "review.md").unlink(missing_ok=True)  # notes of an earlier FAIL are not this verdict's
    if args.verdict == "FAIL":
        # `jt-work` stops after the third FAIL on one ticket, so the count has to live somewhere a session can read.
        meta = {**meta, "fails": int(meta.get("fails", 0)) + 1}
        write_json(work / "meta.json", meta)
    write_json(work / "verdict.json", {
        "verdict": args.verdict, "by": " ".join(args.by.split()), "sha": sha,
        "patch": patch, "ticket": ticket_id_of_text(work),
    })
    line = f"verdict: {args.verdict} by {' '.join(args.by.split())} @{sha[:7]}"
    notes = (work / "review.md").read_text() if args.notes_file else ""
    (work / "review-comment.md").write_text(f"`{line}`\n\n{notes}".rstrip() + "\n")
    print(line)
    if meta.get("pr"):
        print(f"comment file: {work / 'review-comment.md'}  (the verdict line and the notes, ready to post on {meta['pr']})")


def check_evidence(work: Path, text: str) -> None:
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        raise Refuse("the evidence file is empty")
    items = done_when_items(work)
    limit = max(MAX_EVIDENCE_LINES, len(items) + 10)
    if len(lines) > limit:
        raise Refuse(
            f"the evidence has {len(lines)} lines; the human reads it before the diff, so keep it to "
            f"{limit}. Say what you ran and saw for each `Done when` item, and cut the rest"
        )
    missing = [
        f"{n}. {item}" for n, item in enumerate(items, 1)
        if not re.search(rf"^\s*{n}\.\s*(seen|not run):", text, re.M)
    ]
    if missing:
        raise Refuse(
            "the evidence must account for every `Done when` item. Start one line per item with its number and "
            "`seen:` (the command or steps, and the result) or `not run:` (the reason). Missing:\n" + "\n".join(missing)
        )
    cited = sorted(set(cited_runs(text)))
    missing_runs = [n for n in cited if not (work / "runs" / f"{n}.txt").exists()]
    if missing_runs:
        raise Refuse(
            "the evidence cites " + ", ".join(f"run {n}" for n in missing_runs) + ", which `jtek.py run` never recorded "
            "for this ticket. Cite only the run numbers it printed"
        )
    if not re.search(r"^\s*(-\s*)?clean-up:", text, re.M | re.I):
        # The step that reads the diff once more is the easiest to skip at the end of a long session.
        raise Refuse(
            "the evidence has no `clean-up:` line. Read the diff as the `jt-cleanup` skill says, then add one line "
            "under Notes: `- clean-up: <what you removed>`, or `- clean-up: nothing to remove`"
        )


def cmd_run(args: argparse.Namespace) -> None:
    """Run a command the way a user would, and keep exactly what was run and what came back.
    The evidence then cites `(run <n>)`, so a reader can see the run behind each `seen:` line."""
    meta = load_meta(args.id, tree=True)
    work = work_dir(args.id)
    worktree = Path(meta["worktree"])
    command = list(args.command)
    # argparse hands everything after the id to the command, so options given there are read here.
    while command[:1] in (["--sh"], ["--cwd"]) and len(command) > 1:
        setattr(args, command[0][2:], command[1])
        command = command[2:]
    if command[:1] == ["--"]:
        command = command[1:]
    if bool(args.sh) == bool(command):
        raise Refuse("give one command after `--`, or one shell line with --sh \"<pipeline>\", not both and not neither")
    cwd = Path(args.cwd).expanduser().resolve() if args.cwd else worktree
    if not cwd.is_dir():
        raise Refuse(f"--cwd is not a folder: {cwd}")
    sha, dirty = head_state(worktree)
    runs = work / "runs"
    runs.mkdir(exist_ok=True)
    number = len(list(runs.glob("*.txt"))) + 1
    while True:
        try:
            (runs / f"{number}.txt").touch(exist_ok=False)  # exclusive, so two runs at once never share a number
            break
        except FileExistsError:
            number += 1
    shown = args.sh or shlex.join(command)
    # A shell line is what the session could type into its own shell; recording it adds no reach.
    argv = ["/bin/sh", "-c", args.sh] if args.sh else command
    out_file, err_file = runs / f"{number}.out", runs / f"{number}.err"
    started = time.monotonic()
    code = run_logged(argv, cwd, ticket_env(args.id, worktree), out_file, stdin=subprocess.DEVNULL, err_log=err_file)
    seconds = time.monotonic() - started

    def kept(path: Path) -> str:
        text = path.read_text(errors="replace")
        path.unlink()
        return text if len(text) <= MAX_RUN_OUTPUT else text[:MAX_RUN_OUTPUT] + f"\n... ({len(text) - MAX_RUN_OUTPUT} more characters not kept)\n"

    stdout, stderr = kept(out_file), kept(err_file)
    # When it ran somewhere else, say which commit that place was at, so a run of the base names the base.
    there = git("rev-parse", "HEAD", cwd=cwd, check=False) if cwd != worktree else ""
    record = (f"run: {number}\ncommand: {shown}\ncwd: {cwd}" + (f" (at commit {there})" if there else "")
              + f"\ncommit: {sha}" + (" (with uncommitted files)" if dirty else "")
              + f"\nexit: {code}\nseconds: {seconds:.2f}\n--- stdout ---\n{stdout}--- stderr ---\n{stderr}")
    (runs / f"{number}.txt").write_text(record)
    print(record if len(record) <= 4000 else record[:4000] + "\n... (the rest is in the run file)")
    print(f"recorded: run {number} in {runs / f'{number}.txt'}. Cite it in the evidence as (run {number})")


def cmd_evidence(args: argparse.Namespace) -> None:
    """Check an evidence file before it becomes the body of a pull request. Saves nothing."""
    load_meta(args.id)
    text = read_file(args.file, "evidence")
    check_evidence(work_dir(args.id), text)
    seen = len(re.findall(r"^\s*\d+\.\s*seen:", text, re.M))
    not_run = len(re.findall(r"^\s*\d+\.\s*not run:", text, re.M))
    print(f"evidence: the form is accepted ({seen} seen, {not_run} not run). Nothing was saved; pass the file to `finish`")


PR_HEAD_TRIES = 5
PR_HEAD_WAIT = float(os.environ.get("JTEK_PR_WAIT", "3"))


def pushed(worktree: Path, branch: str, sha: str) -> bool:
    """Whether the remote-tracking branch already holds this commit, so a pull request behind it is only late."""
    return git("rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{branch}", cwd=worktree, check=False) == sha


def cmd_finish(args: argparse.Namespace) -> None:
    meta = load_meta(args.id, tree=True)
    work = work_dir(args.id)
    worktree = Path(meta["worktree"])
    last = work / "result.md"
    if last.exists() and "outcome: needs-human" in last.read_text():
        raise Refuse(f"{args.id} stopped with a question. The human answers on the page and sets Status to Todo; then start again")
    if args.pr and args.no_pr:
        raise Refuse("pass --pr <url> or --no-pr, not both")
    if not args.pr and not args.no_pr and meta.get("no_pr"):
        args.no_pr = True  # an earlier finish already said there is no pull request, so `finish <id>` alone works again
    if args.pr and not re.match(r"^https?://[^\s;]+$", args.pr):
        raise Refuse("--pr takes the link of the pull request, as the forge gave it")
    config = load_config(meta["base"])
    if args.no_pr and config.get("forge") is not False and git("remote", cwd=worktree, check=False):
        raise Refuse("this repository has a remote, so the change needs a pull request: push the branch, open it, and pass "
                     f"--pr <url>. If the remote is not a forge, the human sets `\"forge\": false` in {CONFIG}")
    sha, dirty = head_state(worktree)
    checks = read_json(work / "checks.json")
    passed = checks.get("results") and all(r["status"] == "pass" for r in checks["results"])
    ran_all = [r["name"] for r in checks.get("results", [])] == meta["checks"]
    if dirty:
        raise Refuse(f"these files are not committed; {DIRTY_HINT} and run `jtek.py check {args.id}`\n{dirty}")
    if checks.get("dirty") or checks.get("sha") != sha or not passed or not ran_all:
        raise Refuse(f"checks have not passed on the current commit {sha[:7]}; run `jtek.py check {args.id}`")
    patch = patch_id(worktree, meta["base"])
    if not patch:
        raise Refuse(f"the branch has no change against {meta['base']}, so there is nothing to review. If the ticket "
                     f"needs no change, stop and say so: `jtek.py stop {args.id} --waiting input --note \"...\"`")
    about = ticket_id_of_text(work)
    saved = work / "evidence.md"
    if args.evidence_file:
        text = read_file(args.evidence_file, "evidence")
        check_evidence(work, text)
        saved.write_text(text)
        meta.update(evidence_patch=patch, evidence_ticket=about)
        write_json(work / "meta.json", meta)  # kept even when a later rule refuses this finish
    elif not saved.exists():
        raise Refuse(
            "no evidence yet; the human reviews the evidence before the diff. Write what you ran and saw for each "
            "`Done when` item to a file and pass --evidence-file <file>. Use the same text as the pull request body"
        )
    elif meta.get("evidence_patch") != patch:
        raise Refuse("the code changed after the evidence was saved, so the evidence describes an older change. "
                     "See each `Done when` item work again, and pass --evidence-file <file>")
    elif meta.get("evidence_ticket") != about:
        check_evidence(work, saved.read_text())
        raise Refuse("the ticket changed after the evidence was saved. Read the ticket file again, do what it now asks, "
                     "and pass --evidence-file <file>")
    else:
        check_evidence(work, saved.read_text())  # the ticket may have gained an item since
    for item in args.attach or []:
        source = Path(item)
        if not source.is_file():
            raise Refuse(f"cannot attach {item}: not a file")
        (work / "evidence").mkdir(exist_ok=True)
        (work / "evidence" / source.name).write_bytes(source.read_bytes())
    pr = args.pr or meta.get("pr", "")
    ci = ""
    if args.no_pr:
        pr = ""
        pr_note = f" No pull request: the branch {meta['branch']} is local."
    elif not pr:
        raise Refuse(
            "no PR yet; open it (ready, not draft) and pass --pr <url>. "
            "Only when this repository has no forge to open one on, pass --no-pr"
        )
    else:
        state, head, ci = pr_info(pr, meta["base"])
        for _ in range(PR_HEAD_TRIES):
            # A forge needs a moment after a push before the pull request shows the new commit.
            if state != "OPEN" or head == sha or not pushed(worktree, meta["branch"], sha):
                break
            time.sleep(PR_HEAD_WAIT)
            state, head, ci = pr_info(pr, meta["base"])
        if state == "DRAFT":
            raise Refuse(f"{pr} is a draft. Mark it ready for review, then finish again")
        if state != "unknown" and (state != "OPEN" or head != sha):
            late = " The branch is pushed, so the forge may only be late: run `finish` again in a moment" \
                if state == "OPEN" and pushed(worktree, meta["branch"], sha) else "; push the branch"
            raise Refuse(f"{pr} is {state} at {head[:7]}, not open at the current commit {sha[:7]}" + (late if late.startswith(";") else "." + late))
        if ci == "fail":
            raise Refuse(f"CI is failing on {pr}; a pull request with red CI is not ready for the human. Fix it first")
        if state == "OPEN" and pr_conflicts(pr, meta["base"]):
            raise Refuse(f"{pr} conflicts with {meta['base']}; a pull request that cannot merge is not ready for the human. "
                         "Bring the branch up to date as the `jt-babysit` skill says, then check and finish again")
        pr_note = "" if state == "OPEN" else " The PR link was not verified because `gh` could not read it."
    meta.update(pr=pr, ci=ci, no_pr=bool(args.no_pr))
    write_json(work / "meta.json", meta)
    verdict = current_verdict(args.id, meta)
    if not meta.get("review") and needs_verdict(meta):
        pr_note += " `review: human` is ignored because the change touches the files on the attention line."
    if needs_verdict(meta) and not verdict:
        print(write_result(args.id, "needs-review", "In Progress",
                           note="start a session that did not write this code and run jt-review for this id." + pr_note), end="")
        return
    if verdict.get("verdict") == "FAIL":
        fails = int(meta.get("fails", 0))
        if fails >= 3:
            raise Refuse(f"verdict is FAIL, the third or later on {args.id} ({fails}); stop with `jtek.py stop {args.id} "
                         "--waiting input`, because the ticket or the reviewer's standard needs the human")
        raise Refuse(f"verdict is FAIL ({fails} so far on this ticket); read {work / 'review.md'}, fix what reproduces, "
                     "commit, check, and get a new verdict")
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
    print(f"commit: {git('rev-parse', 'HEAD', cwd=Path(meta['worktree']), check=False) or 'unknown'}")
    print(f"base: {meta['base']}")
    print(f"main checkout: {main_root()}")
    print(f"diff: git -C {shlex.quote(meta['worktree'])} diff {meta['base']}...HEAD")
    try:
        declared = load_checks(meta["base"])
    except Refuse:
        declared = {}
    for name in meta["checks"]:
        print(f"check {name}: {declared.get(name, '(no longer declared)')}")
    print(f"pr: {meta.get('pr') or '-'}")


CI_QUERY = (
    '(if .state == "OPEN" and .isDraft then "DRAFT" else .state end) + " " + .headRefOid + " " + ([.statusCheckRollup[]? | (.conclusion // .state // "PENDING")] '
    '| if length == 0 then "none" '
    'elif any(.[]; . == "FAILURE" or . == "ERROR" or . == "TIMED_OUT" or . == "CANCELLED" or . == "ACTION_REQUIRED" or . == "STARTUP_FAILURE") then "fail" '
    'elif all(.[]; . == "SUCCESS" or . == "NEUTRAL" or . == "SKIPPED") then "pass" else "pending" end)'
)


PR_STATES = ["OPEN", "DRAFT", "MERGED", "CLOSED"]
CI_STATES = ["pass", "fail", "pending", "none"]


def pr_info(url: str, base: str = "") -> tuple[str, str, str]:
    """Return (state, head commit, CI state) of a pull request.
    State is OPEN, DRAFT, MERGED, or CLOSED. CI state is pass, fail, pending, or none.
    GitHub is read with `gh`; when it cannot answer, the result is ("unknown", "", "unknown").
    For another forge, `pr_state` in jtek.json names a command that gets the link as its last argument and
    prints those three words. It runs in the main checkout, so a ticket's branch cannot change what runs.
    A project that names its own command gets a refusal, and not "unknown", when that command does not answer."""
    custom = load_settings(base or base_branch())["pr_state"]
    command = ["gh", "pr", "view", url, "--json", "state,isDraft,headRefOid,statusCheckRollup", "-q", CI_QUERY]
    problem = ""
    try:
        if custom:
            command = shlex.split(custom) + [url]
        proc = subprocess.run(command, capture_output=True, text=True, timeout=60, cwd=main_root())
        parts = proc.stdout.split()
        if proc.returncode != 0:
            problem = f"ended with {proc.returncode}: {' '.join(proc.stderr.split())[:200]}"
        elif (len(parts) != 3 or parts[0] not in PR_STATES or parts[2] not in CI_STATES
              or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", parts[1])):
            problem = (f"printed `{' '.join(parts)[:120]}`. It must print three words: {', '.join(PR_STATES[:-1])} or "
                       f"{PR_STATES[-1]}; the full head commit; and {', '.join(CI_STATES[:-1])} or {CI_STATES[-1]}")
    except (OSError, ValueError, subprocess.TimeoutExpired) as err:
        problem = f"did not run: {type(err).__name__}: {err}"
    if problem and custom:
        raise Refuse(f"the `pr_state` command of {CONFIG} {problem}")
    return ("unknown", "", "unknown") if problem else (parts[0], parts[1], parts[2])


def pr_conflicts(url: str, base: str = "") -> bool:
    """Whether GitHub says the pull request cannot merge into its base as it is. Unknown counts as no:
    another forge, a `gh` that cannot answer, or a forge that has not worked it out yet."""
    if load_settings(base or base_branch())["pr_state"]:
        return False
    try:
        proc = subprocess.run(["gh", "pr", "view", url, "--json", "mergeable", "-q", ".mergeable"],
                              capture_output=True, text=True, timeout=60, cwd=main_root())
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0 and proc.stdout.strip() == "CONFLICTING"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jtek.py", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="write a jtek.json template").set_defaults(func=cmd_other)
    sub.add_parser("doctor", help="say what is set up in this repository and what is missing").set_defaults(func=cmd_other)

    start = sub.add_parser("start", help="claim a ticket and create its worktree")
    start.add_argument("ref", help="the link of the ticket's Notion page; it becomes the `source:` of the result")
    start.add_argument("--from-file", required=True, help="the page, read just now and saved in the ticket format")
    start.add_argument("--resume", action="store_true", help="take over a claim whose session died without a result")
    start.add_argument("--no-baseline", action="store_true", help="do not run the checks on the base first")
    start.add_argument("--no-fetch", action="store_true", help="do not fetch the base branch from origin first")
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
    finish.add_argument("--no-pr", action="store_true", help="only for a repository with no remote, or with `\"forge\": false` in jtek.json")
    finish.add_argument("--evidence-file", help="what was run and seen for each `Done when` item; needed again whenever the code changed")
    finish.add_argument("--attach", action="append", help="a screenshot, recording, or output file to keep with the evidence")
    finish.set_defaults(func=cmd_finish)

    run = sub.add_parser("run", help="run a command in the ticket's worktree and record exactly what ran and what came back")
    run.add_argument("id")
    run.add_argument("--sh", help="one shell line, for a pipe or a redirect")
    run.add_argument("--cwd", help="run somewhere else, such as the main checkout for the base")
    run.add_argument("command", nargs=argparse.REMAINDER)
    run.set_defaults(func=cmd_run)

    evidence = sub.add_parser("evidence", help="check the form of an evidence file before it becomes a pull request body")
    evidence.add_argument("id")
    evidence.add_argument("--file", required=True)
    evidence.set_defaults(func=cmd_evidence)

    stop = sub.add_parser("stop", help="stop and wait for the human")
    stop.add_argument("id")
    stop.add_argument("--waiting", required=True, choices=WAITING)
    stop.add_argument("--note", required=True)
    stop.set_defaults(func=cmd_stop)

    for name, func, text in (("result", cmd_result, "print the last result"),
                             ("show", cmd_show, "print what a reviewer needs"),
                             ("release", cmd_other, "only when the human asks: drop the claim and the worktree")):
        item = sub.add_parser(name, help=text)
        item.add_argument("id")
        item.set_defaults(func=func)

    for name, func, text in (
        ("next", cmd_other, "for whoever starts sessions: what each open ticket of this repository needs now"),
        ("sync", cmd_other, "read the pull request of each Review ticket from the forge, and remove the worktrees of finished tickets"),
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
    except KeyboardInterrupt:
        print("refused: interrupted. If this was `start`, run `jtek.py release <id>` before you start the ticket again")
        return 130
    except (OSError, ValueError, KeyError, TypeError, RecursionError) as err:
        # Not a rule, but a file or a value this script did not expect. Say it plainly instead of a traceback.
        if os.environ.get("JTEK_DEBUG"):
            raise
        print(f"refused: unexpected {type(err).__name__}: {err}. A file under {state_dir()} or an input file may be "
              "damaged or edited by hand. Set JTEK_DEBUG=1 to see where")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
