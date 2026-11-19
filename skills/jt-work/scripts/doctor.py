#!/usr/bin/env python3
"""`jtek.py doctor`: say what is set up in a repository and what is missing, in the order to fix it.

Read-only. It runs no check and cannot see Notion. Run it as `jtek.py doctor`.
"""
from __future__ import annotations

import re
import shutil
import sys


def run(j) -> None:
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
    config: dict = {}
    try:
        base = j.base_branch()
        rows.append(("ok", f"base branch `{base}`", ""))
        config = j.load_config(base)
        rows.append(("ok", f"{j.CONFIG} is committed on {base}", ""))
    except j.Refuse as err:
        base = ""
        rows.append(("missing", f"{j.CONFIG} on the base branch", str(err)))
    if config:
        board = str(config.get("board") or "")
        rows.append(("ok" if board else "missing", "`board`: the Notion database link",
                     f"set `board` in {j.CONFIG} to the link of the board database, and commit it on {base}"))
        checks = config.get("checks") if isinstance(config.get("checks"), dict) else {}
        empty = [name for name, command in checks.items() if not str(command).strip()]
        if not checks:
            rows.append(("missing", "checks", f"declare at least one check in {j.CONFIG}"))
        elif empty:
            rows.append(("missing", "checks without a command: " + ", ".join(empty),
                         f"fill them in or delete them in {j.CONFIG}, and commit it on {base}"))
        else:
            rows.append(("ok", "checks: " + ", ".join(checks), ""))
        rows.append(("ok" if "verify" in checks and not empty else "optional", "a `verify` check that runs the real app",
                     "run the jt-harness skill once; without it a passing check only means the code compiles"))
        guide = bool(j.git("rev-parse", "--verify", "--quiet", f"{base}:.jtek/verify.md", check=False))
        rows.append(("ok" if guide else "optional", f".jtek/verify.md on {base}",
                     "run the jt-harness skill once, review what it wrote, and commit it"))
    rows.append(("ok" if j.git("remote", "get-url", "origin", check=False) else "optional", "a remote named origin",
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
        raise j.Refuse("something required is missing; fix the first `missing` line and run doctor again")
    print("ready: write a ticket on the board, set it to Todo, and give its id to the jt-work skill")
