---
name: jt-work-queue
description: Work the card queue in card-loop/board.md: set up the board, capture the brief, draft and add cards, pick the next card, implement with adaptive verification, and hand off to review. This command cannot merge.
license: MIT
compatibility: Codex, Claude Code, Cursor, Grok Build, and Antigravity. Needs a git repo.
metadata:
  author: Thitinan
  version: "21"
  short-description: Work the card queue in card-loop/board.md
---

# jt-work-queue

Read [references/contract.md](references/contract.md) for the full loop contract, board/card/plan formats, and skill rules. Templates live in `assets/` and the gate CLI lives at `scripts/gate.py` in this skill folder.

Run from the open repo root:

```bash
python3 <this-skill-dir>/scripts/gate.py next --root .
python3 <this-skill-dir>/scripts/gate.py ask --root . --id <id> --question "<question, blocker, and options>" [--refused <token>]
python3 <this-skill-dir>/scripts/gate.py reach-review --root . --id <id> [--write] [--link <url|local>]
python3 <this-skill-dir>/scripts/gate.py diff-check --root . --id <id>
python3 <this-skill-dir>/scripts/gate.py screen-check --root . --id <id>
python3 <this-skill-dir>/scripts/gate.py landed --root . --id <id>
```

## 1. Set up board (`action: setup-board`)

1. If the open repo is not a git repo, stop and say to run `git init` first.
2. If HEAD is not on a branch, stop and say to check out the branch that will hold the queue.
3. Copy `assets/board.template.md` from this skill to `card-loop/board.md`.
4. Write the current branch name after `queue:`, and replace `<REPO_NAME>` with the repo folder name.
5. Fill `<SETUP_CMD>`, `<TEST_CMD>`, `<TYPECHECK_CMD>`, `<LINT_CMD>`, `<BROWSER_TOOL>`, `<STACK_LOCK>`, and `<REPO_SKILLS>` from the open repo (`package.json`, `Cargo.toml`, `go.mod`, `pyproject.toml`). If `playwright` is in `package.json` or a `playwright` command is on PATH, write `playwright` (or `cypress`); do not put a session or MCP browser name.
6. Propose discovered skills with `on this machine` or `install this` (`npx skills add <source>@<skillId> -g -y`, following symlinks from home dot-folders to the real file so the same real path counts as one skill, and `https://skills.sh/api/search?q=<words>&limit=5`). Do not run an install command. Do not write `card-loop/board.md` until the human accepts.

## 2. Brief & Add cards (`action: brief` / `action: add-card`)

- **Brief:** Interview one round at a time until `want:`, `out:`, and `split:` are clear. Wait for the human to accept the draft before writing `card-loop/brief.md` on the queue branch.
- **Add cards:** Interview until each card has one ticket kind, one path, `do:`, `out:`, `files:`, `pass:`, `screen:`, and one Escape stop for **Plan**. Cards sharing `layer:` link each other under `refs:`. Do not split into parallel agents. Wait for the human to accept the draft from `assets/card.template.md`, then write `card-loop/backlog/<id>.md` and add `- [ ] **<id>** <short name> (<kind>)` to `card-loop/board.md` on the queue branch.

## 3. Pick and do work (`action: do-card`)

1. Run `gate.py next --root .`. If `landed-waiting:` is printed, tell the human to run `/jt-review-work` to close those cards; never mark `merge:` yourself.
2. If `reason` is `related`, report `ids` and stop or write `ask:`. Do not split into parallel agents.
3. On `card-<id>` (branched from `<queue>`):
   - For Standard tier cards, create `card-loop/plan/<id>.md` from `assets/plan.template.md` and follow **Plan** in `references/contract.md`. Quick tier (`docs` / `style`) does not require `plan/<id>.md`.
   - Use the existing check commands on the board (`<TEST_CMD>`, `<TYPECHECK_CMD>`, `<LINT_CMD>`). Do not create a new check script unless `do:` orders it (`refused: one-off-checker`).
   - Screen work uses JTek `python3 <this-skill-dir>/scripts/gate.py screen-check --root . --id <id>` or existing check commands on the board.
   - Before `review:` on Standard tier code changes, review this card's diff (via `<REPO_SKILLS>` or yourself if not installed). Do not skip that review; if you cannot review the diff, do not set `review:`. A note in the plan is not that review. Record `## review-diff` with the latest commit SHA and verify `python3 <this-skill-dir>/scripts/gate.py diff-check --root . --id <id>` exits 0.

## 4. Write ask & Open for review

- **Write ask:** On the queue branch, run `python3 <this-skill-dir>/scripts/gate.py ask --root . --id <id> --question "..." [--refused <token>]`, commit `card-loop/board.md` and `card-loop/backlog/<id>.md`, and pick the next card.
- **Open for review:** On the queue branch, run `reach-review --root . --id <id>`.
  - When `allowed` and no remote: run `reach-review --root . --id <id> --write --link local`.
  - When `allowed` and a remote exists: push `card-<id>` and run `gh pr create --draft --base <queue> --head card-<id> --title "<id>" --body "card <id>"` (if no open draft PR exists; do not open a duplicate, skip `gh pr create` if already open). If the draft PR cannot be opened, write `ask:`. The line must not be `review:`. Then run `reach-review --root . --id <id> --write`.
  - When `refused:`: if `next: retry`, follow **Three rounds** on this card; if `next: ask` (such as `refused: pr-missing`, `refused: one-off-checker`, `refused: related`), follow **Write ask**; if `next: stop`, stop the queue.
