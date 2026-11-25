#!/usr/bin/env python3
"""`jtek.py doctor --agents` and `jtek.py reviewer`: which coding agents this machine has, and which one reviews.

Neither needs a repository. `doctor --agents` looks for the agent programs it knows on PATH, and runs the one
command that lists models, for the programs that have one. `reviewer` reads the owner's ordered list and prints
a command; it starts nothing. `j` is the jtek module.
"""
from __future__ import annotations

import json
import re
import shlex
import shutil
import subprocess
from pathlib import Path

LIST_TIMEOUT = 30

# (program, how a session that shares no conversation is started, the vendor of its models or "" when it
#  serves several, the arguments that list its models or None when it has no such command)
KNOWN = [
    ("claude", 'claude -p "<prompt>"', "anthropic", None),
    ("codex", 'codex exec "<prompt>"', "openai", None),
    ("cursor-agent", 'cursor-agent -p "<prompt>"', "", ["--list-models"]),
    ("agy", 'agy -p "<prompt>"', "", None),
    ("gemini", 'gemini -p "<prompt>"', "google", None),
]


def owner_file(j, name: str) -> tuple[Path, str]:
    """The machine file, or the old ~/.config/jtek path when that is the one that exists.

    The notice is one line when the old path is in use, and empty otherwise. A missing file returns the new path.
    """
    new = j.machine_root() / name
    old = Path.home() / ".config" / "jtek" / name
    if new.is_file() and not new.is_symlink():
        return new, ""
    if old.is_file() and not old.is_symlink():
        return old, f"notice: reading {old}. Run `jtek.py migrate` to move it to {new}."
    return new, ""


def one_line(value) -> str:
    return " ".join(str(value).split())  # a value cannot add a line to the output


def load_reviewers(j, path: Path) -> list[dict] | None:
    """The owner's list, in the owner's order, or None when there is no file. Every entry is checked before any is used."""
    if not path.is_file():
        return None
    form = ('{"reviewers": [{"command": "codex exec -m <model>", "vendor": "openai", "model": "<model>"}]}')
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError) as err:
        raise j.Refuse(f"cannot read {path}: {err}. Its form is {form}") from None
    entries = data.get("reviewers") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        raise j.Refuse(f"{path} must hold a `reviewers` list. Its form is {form}")
    reviewers = []
    for number, entry in enumerate(entries, 1):
        values = {key: one_line(entry.get(key) or "") if isinstance(entry, dict) and isinstance(entry.get(key), str) else ""
                  for key in ("command", "vendor", "model")}
        lacking = [key for key, value in values.items() if not value]
        if lacking:
            raise j.Refuse(f"entry {number} of {path} needs " + ", ".join(f"`{key}`" for key in lacking)
                           + f", each a line of text. Its form is {form}")
        try:
            values["program"] = shlex.split(values["command"])[0]
        except (ValueError, IndexError):
            raise j.Refuse(f"entry {number} of {path}: the command `{values['command']}` has an unbalanced quote") from None
        reviewers.append(values)
    return reviewers


def list_models(program: str, argv: list[str]) -> list[str] | str:
    """The model ids a program prints, or a sentence that says why there are none."""
    try:
        proc = subprocess.run([program, *argv], capture_output=True, text=True, timeout=LIST_TIMEOUT,
                              stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return f"`{' '.join([Path(program).name, *argv])}` gave no answer in {LIST_TIMEOUT} seconds"
    except OSError as err:
        return f"`{' '.join([Path(program).name, *argv])}` did not run: {one_line(err)}"
    ids = re.findall(r"^([A-Za-z0-9][\w.:\[\]=,/-]*) - \S", proc.stdout, re.M)
    if proc.returncode != 0 or not ids:
        return f"`{' '.join([Path(program).name, *argv])}` listed none (exit {proc.returncode}); is it signed in?"
    return ids


def report(j, args) -> None:
    found = 0
    for program, start, vendor, lister in KNOWN:
        path = shutil.which(program)
        if not path:
            print(f"absent   {program}")
            continue
        found += 1
        print(f"found    {program}  ({path})")
        print(f"         a session is usually started as: {start}  (check its own help)")
        print(f"         vendor: {vendor}" if vendor else "         vendor: several; it depends on the model you name")
        if lister is None:
            print("         models: this program has no command that lists them; see its own help for the names")
            continue
        models = list_models(path, lister)
        print(f"         models: {models}" if isinstance(models, str) else f"         models ({len(models)}): " + ", ".join(models))
    print("not checked: whether each program is signed in, and an agent this script does not know. A shell alias is "
          "not seen either.")
    path, notice = owner_file(j, "agents.json")
    if notice:
        print(notice)
    style, style_notice = owner_file(j, "me.md")
    if style_notice:
        print(style_notice)
    print(f"style: {style}" if style.is_file() else f"style: no file at {style}")
    reviewers = load_reviewers(j, path)
    if reviewers is None:
        print(f"reviewers: no list at {path}; `/jt-agents` proposes one, and the owner approves it")
    else:
        print(f"reviewers: {len(reviewers)} in {path}, in the owner's order")
        for entry in reviewers:
            state = "found " if shutil.which(entry["program"]) else "absent"
            print(f"         {state}  {entry['command']}  ({entry['vendor']}, {entry['model']})")
    if not found:
        print("no known agent program is on PATH; a reviewer is then a fresh session of your own agent")


def reviewer(j, args) -> None:
    """Print the command that starts the reviewer. The first entry of another vendor than the author's that is
    installed wins; without one, the first installed entry of the author's own vendor. It never says that no
    review is needed: with nothing to pick, the reviewer is a fresh session of the author's own model."""
    mine = one_line(args.vendor).lower()
    if not mine:
        raise j.Refuse("pass --vendor with the vendor of the model you run on, such as `anthropic` or `openai`")
    path, notice = owner_file(j, "agents.json")
    if notice:
        print(notice)
    reviewers = load_reviewers(j, path)
    fallback = "reviewer: a fresh session of your own model, one that shares none of this conversation"
    if reviewers is None:
        print(fallback)
        print(f"because: there is no list at {path}; `/jt-agents` proposes one, and the owner approves it")
        return
    if mine not in {entry["vendor"].lower() for entry in reviewers}:
        print(f"note: no entry of the list has the vendor `{mine}`. If your model's vendor is written another way "
              "there, pass it as the list writes it, or an entry of your own vendor may be picked")
    same = None
    for entry in reviewers:
        if not shutil.which(entry["program"]):
            print(f"skipped: {entry['command']}  ({entry['program']} is not installed)")
        elif entry["vendor"].lower() == mine:
            same = same or entry
            print(f"skipped: {entry['command']}  (the same vendor as yours: {entry['vendor']})")
        else:
            pick(entry, "the first entry of another vendor that is installed")
            return
    if same:
        pick(same, f"no entry of another vendor is installed, so the first of your own; start it as a session that "
                   "shares none of this conversation")
        return
    print(fallback)
    print(f"because: no entry of {path} is installed")


def pick(entry: dict, why: str) -> None:
    print(f"reviewer: {entry['command']}")
    print(f"vendor: {entry['vendor']}")
    print(f"model: {entry['model']}")
    print(f"because: {why}")
    print(f"by: pass `--by {shlex.quote(entry['model'])}` to `jtek.py verdict`; if another model answered, name that one")
