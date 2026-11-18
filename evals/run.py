#!/usr/bin/env python3
"""Build a scratch repository for a scenario, and grade what an agent left in it.

    python3 evals/run.py build <scenario> <empty-dir>
    python3 evals/run.py grade <scenario> <dir>

The agent run in between is yours to start, with any agent. An eval uses no Notion:
the ticket is handed over as a file. Standard library only.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCENARIOS = ROOT / "evals" / "scenarios"
SKILL = ROOT / "skills" / "jt-work" / "SKILL.md"


def git(*args: str, cwd: Path) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


def load(name: str) -> tuple[Path, dict]:
    folder = SCENARIOS / name
    if not folder.is_dir():
        sys.exit(f"no scenario `{name}`; have: {', '.join(sorted(p.name for p in SCENARIOS.iterdir()))}")
    return folder, json.loads((folder / "scenario.json").read_text())


def build(name: str, dest: Path) -> None:
    folder, scenario = load(name)
    if dest.exists() and any(dest.iterdir()):
        sys.exit(f"{dest} is not empty")
    repo = dest / "app"
    shutil.copytree(folder / "repo", repo)
    git("init", "-q", "-b", "main", cwd=repo)
    git("config", "user.email", "eval@example.invalid", cwd=repo)
    git("config", "user.name", "eval", cwd=repo)
    git("add", "-A", cwd=repo)
    git("commit", "-q", "-m", "init", cwd=repo)
    ticket = dest / "ticket.md"
    shutil.copy(folder / "ticket.md", ticket)
    print(f"repository: {repo}")
    print("prompt for a fresh agent session:")
    print(f"  Follow the skill at {SKILL} for ticket id {scenario['ticket']} in the repository {repo}.")
    print(f"  There is no Notion here. The page is already saved as {ticket}: pass it to start with --from-file,")
    print("  use https://www.notion.so/eval as the page link, and skip every write to the board.")
    print("  This repository has no forge. End with the result block.")
    print(f"then: python3 evals/run.py grade {name} {dest}")


def grade(name: str, dest: Path) -> int:
    folder, scenario = load(name)
    ticket = scenario["ticket"]
    repo = dest / "app"
    work = repo / ".git" / "jtek" / "work" / ticket
    worktree = dest / "app.jtek" / ticket
    rows: list[tuple[bool, str]] = []

    def row(ok: bool, text: str) -> bool:
        rows.append((bool(ok), text))
        return bool(ok)

    result = (work / "result.md").read_text() if (work / "result.md").exists() else ""
    fields = dict(line.split(": ", 1) for line in result.splitlines() if ": " in line)
    row(fields.get("outcome") in ("review", "needs-review"), f"result outcome is review or needs-review (got {fields.get('outcome', 'no result')})")
    if row(worktree.is_dir(), "the ticket's worktree exists"):
        head = git("rev-parse", "HEAD", cwd=worktree)
        checks = json.loads((work / "checks.json").read_text()) if (work / "checks.json").exists() else {}
        passed = checks.get("results") and all(r["status"] == "pass" for r in checks["results"])
        row(passed and checks.get("sha") == head, "declared checks passed on the final commit")
        row(git("status", "--porcelain", cwd=worktree) == "", "nothing is left uncommitted")
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copy(folder / "hidden_test.py", Path(tmp) / "hidden_test.py")
            env = {**os.environ, "PYTHONPATH": str(worktree), "PYTHONDONTWRITEBYTECODE": "1"}
            hidden = subprocess.run([sys.executable, "hidden_test.py"], cwd=tmp, env=env, capture_output=True, text=True)
        row(hidden.returncode == 0, "hidden acceptance tests pass" + ("" if hidden.returncode == 0 else "\n" + hidden.stderr.strip()[-600:]))
        commits = git("rev-list", "--reverse", "main..HEAD", cwd=worktree).split()
        row(bool(commits), "the work is committed on the ticket branch")
        if scenario["kind"] == "bug" and commits:
            first = git("show", "--name-only", "--format=", commits[0], cwd=worktree).split()
            row(len(commits) >= 2 and first and all("test" in f.lower() for f in first),
                "the first commit holds only the failing test, before the fix")
    row(len(git("rev-list", "main", cwd=repo).split()) == 1, "the base branch has no new commits")
    row(fields.get("attention") == "-", f"no sensitive file was touched (attention: {fields.get('attention', '?')})")
    evidence = work / "evidence.md"
    lines = [l for l in evidence.read_text().splitlines() if l.strip()] if evidence.exists() else []
    row(0 < len(lines) <= 40, f"evidence is saved and at most 40 lines (got {len(lines)})")

    for ok, text in rows:
        print(("PASS  " if ok else "FAIL  ") + text)
    score = sum(ok for ok, _ in rows)
    print(f"score: {score}/{len(rows)}")
    return 0 if score == len(rows) else 1


def main(argv: list[str]) -> int:
    if len(argv) != 3 or argv[0] not in ("build", "grade"):
        print(__doc__)
        return 2
    dest = Path(argv[2]).expanduser().resolve()
    if argv[0] == "build":
        dest.mkdir(parents=True, exist_ok=True)
        build(argv[1], dest)
        return 0
    return grade(argv[1], dest)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
