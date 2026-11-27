#!/usr/bin/env python3
"""`jtek.py doctor`: say what is set up in a repository and what is missing, in the order to fix it.

Read-only. It runs no check. Run it as `jtek.py doctor`.
"""
from __future__ import annotations

import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path


def uses_shell(command: str) -> bool:
    """True when a command only works in a shell. A quoted argument such as 'a|b' is fine."""
    try:
        tokens = shlex.split(command)
    except ValueError:
        return True  # an unbalanced quote
    bare = shlex.split(command, posix=False)  # keeps the quotes, so quoted text can be told apart
    quoted = [token for token in bare if token[:1] in "'\""]
    for token in tokens:
        if token in ("&&", "||", "|", ";", "&", ">", ">>", "<", "2>", "2>&1"):
            return True
    plain = " ".join(token for token in bare if token not in quoted)
    return any(mark in plain for mark in ("$(", "`", "&", "|", ";", ">", "<")) or any(
        token.startswith("$") for token in bare if token not in quoted)


def setup_uses_venv(setup: str, root: Path) -> bool:
    """True when setup creates a virtualenv, including when that call is inside a script the command names."""
    if re.search(r"\bvenv\b|virtualenv|ensurepip|EnvBuilder", setup):
        return True
    if uses_shell(setup):
        return False
    try:
        tokens = shlex.split(setup)
    except ValueError:
        return False
    for token in tokens:
        if not token or token.startswith("-"):
            continue
        candidate = Path(token)
        if not candidate.is_absolute():
            candidate = root / token
        if candidate.suffix not in {".py", ".sh", ".bash"} or not candidate.is_file():
            continue
        try:
            text = candidate.read_text(errors="replace")
        except OSError:
            continue
        if re.search(r"\bvenv\b|virtualenv|ensurepip|EnvBuilder", text):
            return True
    return False


KNOWLEDGE_NAMES = ("verify.md", "features", "rules.md", "tickets")


def legacy_names(j) -> list[str]:
    """jtek.json or a .jtek/ that still holds jtek knowledge (or is empty). Empty when git cannot name the checkout."""
    try:
        root = j.main_root()
    except j.Refuse:
        return []
    found = []
    if (root / j.CONFIG).exists() or (root / j.CONFIG).is_symlink():
        found.append(j.CONFIG)
    dot = root / ".jtek"
    if dot.is_symlink() or (dot.exists() and not dot.is_dir()):
        found.append(".jtek/")
    elif dot.is_dir():
        try:
            entries = [p.name for p in dot.iterdir()]
        except OSError:
            entries = []
        if not entries or any(name in KNOWLEDGE_NAMES for name in entries):
            found.append(".jtek/")
    return found


def leftover_dot_jtek(j) -> list[str]:
    """Non-knowledge files left in .jtek/ after migration (not a migrate trigger)."""
    try:
        root = j.main_root()
    except j.Refuse:
        return []
    dot = root / ".jtek"
    if not dot.is_dir() or dot.is_symlink():
        return []
    try:
        entries = sorted(p.name for p in dot.iterdir())
    except OSError:
        return []
    if not entries or any(name in KNOWLEDGE_NAMES for name in entries):
        return []
    return entries


def legacy_conflicts(j) -> list[tuple[Path, Path]]:
    """Legacy repo files or directories that already exist on the machine with different contents."""
    try:
        root = j.main_root()
        home = j.repo_home()
    except j.Refuse:
        return []
    candidates: list[tuple[Path, Path]] = [(root / j.CONFIG, home / j.CONFIG)]
    dot = root / ".jtek"
    if dot.is_dir() and not dot.is_symlink():
        for name in KNOWLEDGE_NAMES:
            candidates.append((dot / name, home / name))
    conflicts: list[tuple[Path, Path]] = []
    for src, dest in candidates:
        if not src.exists() or src.is_symlink():
            continue
        if not dest.exists() and not dest.is_symlink():
            continue
        if j.same_content(src, dest):
            continue
        conflicts.append((src, dest))
    return conflicts


def assess(j) -> dict:
    """Collect doctor rows and readiness decision without printing or refusing.

    Read-only. Shared by `jtek.py doctor` and `jtek.py status` so they cannot drift.
    Each row is `(scope, state, what, todo, fix)` where `scope` is `"machine"` or `"repo"`,
    `state` is `"ok"`, `"missing"`, or `"optional"`, `todo` is the full doctor advice, and
    `fix` is the short command or action for one-line summaries.
    """
    rows: list[tuple[str, str, str, str, str]] = []
    legacy = legacy_names(j)

    git_missing = False
    try:
        found = re.search(r"(\d+)\.(\d+)", j.git("--version", check=False))
    except OSError:
        git_missing = True
        rows.append(("machine", "missing", "git", "install git 2.31 or later", "install git 2.31 or later"))
    else:
        version = (int(found.group(1)), int(found.group(2))) if found else (0, 0)
        rows.append(("machine", "ok" if version >= (2, 31) else "missing",
                     f"git {version[0]}.{version[1]}", "install git 2.31 or later", "install git 2.31 or later"))
    rows.append(("machine", "ok" if sys.version_info >= (3, 10) else "missing",
                 f"Python {sys.version_info[0]}.{sys.version_info[1]}",
                 "run this script with Python 3.10 or later", "run with Python 3.10 or later"))
    config: dict | None = None
    base = ""
    if not git_missing:
        try:
            base = j.base_branch()
            rows.append(("repo", "ok", f"base branch `{base}`", "", ""))
        except j.Refuse as err:
            hint = "; if this repository has no commit yet, make the first commit" if "base branch" in str(err) else ""
            fix = "set JTEK_BASE or make the first commit" if "base branch" in str(err) else str(err)
            rows.append(("repo", "missing", "a base branch", str(err) + hint, fix))
    if base:
        try:
            config = j.load_config(base)
        except j.Refuse as err:
            cfg = j.find_config() or (j.repo_home() / j.CONFIG)
            rows.append(("repo", "missing", "config", str(err), f"fix {cfg}"))
    if config is not None:
        source = j.find_config()
        rows.append(("repo", "ok", f"tickets: {j.tickets_dir()}", "", ""))
        if source is None:
            if legacy:
                rows.append(("repo", "missing", "checks",
                             "run `jtek.py migrate` to move the repository config onto this machine",
                             "jtek.py migrate"))
            else:
                rows.append(("repo", "missing", "checks",
                             "run `jtek.py init` or `/jt-init` and give at least one check a command",
                             "/jt-init or jtek.py init"))
        else:
            rows.append(("repo", "ok", f"config {source}", "", ""))
        checks = config.get("checks") if isinstance(config.get("checks"), dict) else {}
        empty = [name for name, command in checks.items() if not isinstance(command, str) or not command.strip()]
        if source is not None and not checks:
            rows.append(("repo", "missing", "checks", f"declare at least one check in {source}",
                         f"/jt-init or declare a check in {source}"))
        elif empty:
            rows.append(("repo", "missing", "checks without a command: " + ", ".join(empty),
                         f"fill them in or delete them in {source}",
                         f"fill in or delete them in {source}"))
        elif source is not None:
            rows.append(("repo", "ok", "checks: " + ", ".join(checks), "", ""))
        commands = {name: command for name, command in checks.items() if isinstance(command, str)}
        for key in ("setup", "pr_state"):
            if isinstance(config.get(key), str) and config[key].strip():
                commands[key] = config[key]
        shell = [name for name, command in commands.items() if uses_shell(command)]
        if shell:
            rows.append(("repo", "missing", "commands that need a shell: " + ", ".join(shell),
                         "a command runs without a shell, so `&&`, `|`, `>`, `$(...)` and `$VAR` do nothing; "
                         "put the pipeline in a script and name the script",
                         "put the pipeline in a script"))
        setup = config.get("setup") if isinstance(config.get("setup"), str) else ""
        if setup_uses_venv(setup, Path.cwd()):
            exe = "python3"
            if not uses_shell(setup):
                try:
                    tokens = shlex.split(setup)
                except ValueError:
                    tokens = []
                if tokens and "python" in tokens[0]:
                    exe = tokens[0]
            try:
                probe = j.run_argv([exe, "-c", "import ensurepip"], timeout=30)
                missing_pip = probe.returncode != 0
            except (OSError, subprocess.TimeoutExpired):
                missing_pip = True
            if missing_pip:
                rows.append(("machine", "missing", "setup cannot create a venv (ensurepip is not available)",
                             "install the venv package for this Python (for example python3-venv) before the first start",
                             "install python3-venv"))
        try:
            j.load_settings(base)
        except j.Refuse as err:
            cfg = j.find_config() or (j.repo_home() / j.CONFIG)
            rows.append(("repo", "missing", "the optional settings",
                         f"{err}; fix it in {cfg}", f"fix {cfg}"))
        rows.append(("repo", "ok" if str(checks.get("verify") or "").strip() else "optional",
                     "a `verify` check that runs the real app",
                     "run the jt-harness skill once; without it a passing check only means the code compiles", ""))
        guide = j.knowledge_path("verify.md")
        shown = guide or (j.repo_home() / "verify.md")
        rows.append(("repo", "ok" if guide else "optional", f"verify guide {shown}",
                     "run the jt-harness skill once. It writes the guide on this machine. "
                     "When that file is missing, jt-verify reads the README and the code and says no guide was found", ""))
    if legacy:
        conflicts = legacy_conflicts(j)
        if conflicts:
            pairs = "; ".join(f"{src} differs from {dest}" for src, dest in conflicts)
            todo = (f"{pairs}; `jtek.py migrate` will not overwrite the machine file. "
                    "Compare them, then either move the machine file aside and run `jtek.py migrate`, "
                    "or delete the repo copy yourself and commit the removal")
            fix = "compare conflicting files, then run jtek.py migrate or delete the repo copy"
        else:
            todo = "run `jtek.py migrate`, then commit the removal"
            fix = "jtek.py migrate"
        rows.append(("repo", "missing", "old files in the repository: " + ", ".join(legacy), todo, fix))
    elif not git_missing:
        leftover = leftover_dot_jtek(j)
        if leftover:
            rows.append(("repo", "optional", "left in .jtek/: " + ", ".join(leftover),
                         "those names are not jtek knowledge; delete them yourself if you want .jtek gone", ""))
    if not git_missing:
        rows.append(("repo", "ok" if j.git("remote", check=False) else "optional", "a remote",
                     "without a remote, tickets end with `finish --no-pr` and the human sets Done", ""))
    own_forge = bool(config and str(config.get("pr_state") or "").strip())
    forge = "gh"
    if not git_missing and not own_forge:
        try:
            forge = j.select_forge(base)
        except j.Refuse:
            forge = "gh"
    if own_forge:
        rows.append(("repo", "ok", "`pr_state`: this repository reads pull requests with its own command", "", ""))
    elif forge == "glab":
        rows.append(("machine", "ok" if shutil.which("glab") else "optional", "`glab` is installed",
                     "install the GitLab CLI (`glab`), or set `pr_state` in the machine config; "
                     "it is needed to read a merge request's state", ""))
    else:
        rows.append(("machine", "ok" if shutil.which("gh") else "optional", "`gh` is installed",
                     "install the GitHub CLI (or `glab` for GitLab), or for another forge set `pr_state` in the machine config; "
                     "it is needed to read a pull request's state", ""))
    missing = [row for row in rows if row[1] == "missing"]
    return {
        "rows": rows,
        "missing": missing,
        "ready": not missing,
        "config": config,
        "legacy": legacy,
        "own_forge": own_forge,
        "forge": forge,
        "git_missing": git_missing,
    }


def _one_line(text: str) -> str:
    return " ".join(str(text).split())


def readiness_line(report: dict) -> str:
    """One tab-separated Thai line summarizing machine and repository readiness for `jtek.py status`."""
    missing = report["missing"]
    if not missing:
        return "พร้อมใช้\tเครื่อง: พร้อม\trepo: พร้อม"
    machine_missing = [_one_line(what) for scope, _state, what, _todo, _fix in missing if scope == "machine"]
    repo_missing = [_one_line(what) for scope, _state, what, _todo, _fix in missing if scope == "repo"]
    fixes: list[str] = []
    for _scope, _state, _what, todo, fix in missing:
        item = _one_line(fix or todo)
        if item and item not in fixes:
            fixes.append(item)
    machine_part = f"เครื่อง: ขาด {', '.join(machine_missing)}" if machine_missing else "เครื่อง: พร้อม"
    repo_part = f"repo: ขาด {', '.join(repo_missing)}" if repo_missing else "repo: พร้อม"
    fix_part = f"แก้: {'; '.join(fixes)}" if fixes else "แก้: jtek.py doctor"
    return f"ยังไม่พร้อม\t{machine_part}\t{repo_part}\t{fix_part}"


def run(j, args=None) -> None:
    """`j` is the jtek module, for its git helper and its config reader."""
    report = assess(j)
    if report["git_missing"]:
        raise j.Refuse("git is not installed; install git 2.31 or later")
    rows = report["rows"]
    legacy = report["legacy"]
    own_forge = report["own_forge"]
    for _scope, state, what, todo, _fix in rows:
        print(f"{state:<9}{what}" + (f"\n         -> {todo}" if state != "ok" and todo else ""))
    forge = report.get("forge", "gh")
    if shutil.which(forge) and not own_forge:
        print(f"not checked: whether `{forge}` is signed in. Run `{forge} auth status` to see.")
    if legacy:
        trigger = "migrate"
    elif j.find_config() is None:
        trigger = "needed"
    else:
        trigger = "ok"
    print(f"init: {trigger}")
    if not report["ready"]:
        raise j.Refuse("something required is missing; fix the first `missing` line and run doctor again")
    print("ready: pass a ticket file or chat goal to /jt or /jt-work; save a ticket with `jtek.py ticket <file> --save` "
          "and set `status: Todo`, or start from chat with `jtek.py start --local --goal \"<goal>\"`")
