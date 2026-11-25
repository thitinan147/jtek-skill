#!/usr/bin/env python3
"""`jtek.py doctor`: say what is set up in a repository and what is missing, in the order to fix it.

Read-only. It runs no check and cannot see the board. Run it as `jtek.py doctor`.
"""
from __future__ import annotations

import re
import shlex
import shutil
import subprocess
import sys


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


def run(j, args=None) -> None:
    """`j` is the jtek module, for its git helper and its config reader."""
    rows: list[tuple[str, str, str]] = []  # (ok | missing | optional, what, what to do)

    try:
        found = re.search(r"(\d+)\.(\d+)", j.git("--version", check=False))
    except OSError:
        raise j.Refuse("git is not installed; install git 2.31 or later") from None
    version = (int(found.group(1)), int(found.group(2))) if found else (0, 0)
    rows.append(("ok" if version >= (2, 31) else "missing", f"git {version[0]}.{version[1]}", "install git 2.31 or later"))
    rows.append(("ok" if sys.version_info >= (3, 10) else "missing",
                 f"Python {sys.version_info[0]}.{sys.version_info[1]}", "run this script with Python 3.10 or later"))
    config: dict | None = None
    try:
        base = j.base_branch()
        rows.append(("ok", f"base branch `{base}`", ""))
        config = j.load_config(base)
        rows.append(("ok", f"{j.CONFIG} is committed on {base}", ""))
    except j.Refuse as err:
        base = ""
        hint = "; if this repository has no commit yet, make the first commit" if "base branch" in str(err) else ""
        rows.append(("missing", f"{j.CONFIG} on the base branch", str(err) + hint))
    if config is not None:
        board = str(config.get("board") or "").strip()
        rows.append(("ok", "`board`: the Notion database or FLO product link" if board
                     else f"no board: the tickets are files in {j.tickets_dir()}", ""))
        checks = config.get("checks") if isinstance(config.get("checks"), dict) else {}
        empty = [name for name, command in checks.items() if not isinstance(command, str) or not command.strip()]
        if not checks:
            rows.append(("missing", "checks", f"declare at least one check in {j.CONFIG}"))
        elif empty:
            rows.append(("missing", "checks without a command: " + ", ".join(empty),
                         f"fill them in or delete them in {j.CONFIG}, and commit it on {base}"))
        else:
            rows.append(("ok", "checks: " + ", ".join(checks), ""))
        commands = {name: command for name, command in checks.items() if isinstance(command, str)}
        for key in ("setup", "pr_state"):
            if isinstance(config.get(key), str) and config[key].strip():
                commands[key] = config[key]
        shell = [name for name, command in commands.items() if uses_shell(command)]
        if shell:
            rows.append(("missing", "commands that need a shell: " + ", ".join(shell),
                         "a command runs without a shell, so `&&`, `|`, `>`, `$(...)` and `$VAR` do nothing; "
                         "put the pipeline in a script and name the script"))
        setup = config.get("setup") if isinstance(config.get("setup"), str) else ""
        if re.search(r"\bvenv\b|virtualenv|ensurepip", setup):
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
                rows.append(("missing", "setup cannot create a venv (ensurepip is not available)",
                             "install the venv package for this Python (for example python3-venv) before the first start"))
        try:
            j.load_settings(base)
        except j.Refuse as err:
            rows.append(("missing", "the optional settings", f"{err}; fix it in {j.CONFIG}, and commit it on {base}"))
        rows.append(("ok" if str(checks.get("verify") or "").strip() else "optional", "a `verify` check that runs the real app",
                     "run the jt-harness skill once; without it a passing check only means the code compiles"))
        guide = bool(j.git("rev-parse", "--verify", "--quiet", f"{base}:.jtek/verify.md", check=False))
        rows.append(("ok" if guide else "optional", f".jtek/verify.md on {base}",
                     "run the jt-harness skill once, review what it wrote, and commit it"))
    rows.append(("ok" if j.git("remote", check=False) else "optional", "a remote",
                 "without a remote, tickets end with `finish --no-pr` and the human sets Done"))
    own_forge = bool(config and str(config.get("pr_state") or "").strip())
    if own_forge:
        rows.append(("ok", "`pr_state`: this repository reads pull requests with its own command", ""))
    else:
        rows.append(("ok" if shutil.which("gh") else "optional", "`gh` is installed",
                     "install the GitHub CLI, or for another forge set `pr_state` in jtek.json; "
                     "it is needed to read a pull request's state"))
    for state, what, todo in rows:
        print(f"{state:<9}{what}" + (f"\n         -> {todo}" if state != "ok" and todo else ""))
    if shutil.which("gh") and not own_forge:
        print("not checked: whether `gh` is signed in. Run `gh auth status` to see.")
    has_board = bool(config and str(config.get("board") or "").strip())
    if has_board:
        print("not checked: the board. This script cannot see it. Ask your agent to read the board with its tool\n"
              "         and compare it with references/notion.md, or references/flo.md, of the jt-work skill.")
    if any(state == "missing" for state, _, _ in rows):
        raise j.Refuse("something required is missing; fix the first `missing` line and run doctor again")
    if has_board:
        print("ready: write a ticket on the board, set it to Todo, and give its id to the jt-work skill")
    else:
        print("ready: this repository needs no board. Save a ticket with `jtek.py ticket <file> --save`, write\n"
              "       `status: Todo` in its file, and give its id to the jt-work skill; or start work that has\n"
              "       no ticket with `jtek.py start --local --from-file <file>`")
