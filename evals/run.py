#!/usr/bin/env python3
"""Build a scratch repository for a scenario, and grade what an agent left in it.

    python3 evals/run.py build [--lean] <scenario> <empty-dir>
    python3 evals/run.py grade <scenario> <dir>

--lean hands the agent a short router and the reviewer's skill, with no step skills and no playbooks,
to measure whether the step text still helps a given model.

The agent run in between is yours to start, with any agent. An eval uses no Notion:
the ticket is handed over as a file. Standard library only.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCENARIOS = ROOT / "evals" / "scenarios"


def git(*args: str, cwd: Path) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


def load(name: str) -> tuple[Path, dict]:
    folder = SCENARIOS / name
    if not folder.is_dir():
        sys.exit(f"no scenario `{name}`; have: {', '.join(sorted(p.name for p in SCENARIOS.iterdir()))}")
    return folder, json.loads((folder / "scenario.json").read_text())


def copy_skills(skills: Path, lean: bool) -> None:
    ignore = shutil.ignore_patterns("__pycache__")
    if not lean:
        shutil.copytree(ROOT / "skills", skills, ignore=ignore)
        return
    # The router keeps its script, references, and worker rules; the step skills and playbooks stay behind.
    shutil.copytree(ROOT / "skills" / "jt-work", skills / "jt-work", ignore=shutil.ignore_patterns("__pycache__", "playbooks"))
    shutil.copy(ROOT / "evals" / "lean" / "jt-work.md", skills / "jt-work" / "SKILL.md")
    shutil.copytree(ROOT / "skills" / "jt-review", skills / "jt-review", ignore=ignore)


def build(name: str, dest: Path, lean: bool = False) -> None:
    folder, scenario = load(name)
    if dest.exists() and any(dest.iterdir()):
        sys.exit(f"{dest} is not empty")
    repo = dest / "app"
    shutil.copytree(folder / "repo", repo)
    git("init", "-q", "-b", "main", cwd=repo)
    # Nothing the agent sees may say it is being measured: a run that knows it is watched is not an ordinary run.
    git("config", "user.email", "sam.okafor@example.com", cwd=repo)
    git("config", "user.name", "Sam Okafor", cwd=repo)
    git("add", "-A", cwd=repo)
    git("commit", "-q", "-m", "init", cwd=repo)
    ticket = dest / "ticket.md"
    shutil.copy(folder / "ticket.md", ticket)
    # The skills are copied next to the repository, so the agent never reads the folder that holds the hidden tests.
    skills = dest / "tools" / "skills"
    copy_skills(skills, lean)
    (dest / "variant.txt").write_text("lean\n" if lean else "full\n")
    page = hashlib.sha256(f"{name}{dest}".encode()).hexdigest()[:32]
    print(f"repository: {repo}")
    print("prompt for a fresh agent session:")
    print(f"  Follow the skill at {skills / 'jt-work' / 'SKILL.md'} for ticket {scenario['ticket']} in the repository {repo}.")
    print(f"  The ticket page is saved as {ticket}: pass it to start with --from-file, and https://www.notion.so/{page}")
    print("  as the page link. No board tool is set up here, so skip the writes to the board.")
    print("  This repository has no remote. End with the result block.")
    print(f"then: python3 evals/run.py grade {name} {dest}")


def grade(name: str, dest: Path) -> int:
    folder, scenario = load(name)
    ticket = scenario["ticket"]
    variant = dest / "variant.txt"
    print(f"variant: {variant.read_text().strip() if variant.exists() else 'full'}")
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
    if "rests on a run" in fields.get("evidence", ""):
        print(f"note: {fields['evidence']}")

    trail = transcript(dest)
    if trail is None:
        print("note: no session transcript found for this folder, so what the agent opened is not graded")
    else:
        opened, commands = trail
        row("jt-work" in opened, "the agent read the jt-work skill (from its transcript, not its account)")
        print(f"skills read: {', '.join(opened) or 'none'}")
        print(f"jtek.py commands, in order: {' '.join(commands) or 'none'}")

    for ok, text in rows:
        print(("PASS  " if ok else "FAIL  ") + text)
    score = sum(ok for ok, _ in rows)
    print(f"score: {score}/{len(rows)}")
    return 0 if score == len(rows) else 1


def transcript(dest: Path, home: Path | None = None) -> tuple[list[str], list[str]] | None:
    """What the agent did, read from the session files of its agent rather than from its own report.
    Claude Code keeps them under ~/.claude/projects/<path with every other character turned into '-'>."""
    slug = re.sub(r"[^A-Za-z0-9]", "-", str(dest))
    folders = [p for p in ((home or Path.home()) / ".claude" / "projects").glob(f"{slug}*") if p.is_dir()]
    files = [f for folder in folders for f in sorted(folder.glob("*.jsonl"))]
    if not files:
        return None
    opened: list[str] = []
    commands: list[str] = []
    for path in files:
        for line in path.read_text(errors="replace").splitlines():
            try:
                content = json.loads(line).get("message", {}).get("content", [])
            except (ValueError, AttributeError):
                continue
            for part in content if isinstance(content, list) else []:
                if not isinstance(part, dict) or part.get("type") != "tool_use":
                    continue
                args = part.get("input") or {}
                found = re.search(r"/skills/(jt[a-z-]*)/SKILL\.md", str(args.get("file_path", "")))
                if found and found.group(1) not in opened:
                    opened.append(found.group(1))
                commands += re.findall(r"jtek\.py\s+([a-z]+)", str(args.get("command", "")))
    return opened, commands


def main(argv: list[str]) -> int:
    lean = argv[:2] == ["build", "--lean"]
    if lean:
        argv = [argv[0], *argv[2:]]
    if len(argv) != 3 or argv[0] not in ("build", "grade"):
        print(__doc__)
        return 2
    dest = Path(argv[2]).expanduser().resolve()
    if argv[0] == "build":
        dest.mkdir(parents=True, exist_ok=True)
        build(argv[1], dest, lean)
        return 0
    return grade(argv[1], dest)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
