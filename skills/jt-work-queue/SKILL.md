---
name: jt-work-queue
description: Work the card queue in card-loop/board.md: set up the board, capture a brief, draft and add cards, pick the next card, implement with adaptive verification, and hand off to review. This command cannot merge.
license: MIT
compatibility: Codex, Claude Code, Cursor, Grok Build, and Antigravity. Needs a git repo.
metadata:
  author: Thitinan
  version: "21"
  short-description: Work the card queue in card-loop/board.md
---

# jt-work-queue

*Constrain the outcome, not the agent.* Read [references/contract.md](references/contract.md) for board, card, plan, and tiered gate contracts. Templates live in [assets/board.template.md](assets/board.template.md), [assets/card.template.md](assets/card.template.md), and [assets/plan.template.md](assets/plan.template.md). The unified JTek gate CLI is [scripts/gate.py](scripts/gate.py).

```bash
python3 <this-skill-dir>/scripts/gate.py next --root .
python3 <this-skill-dir>/scripts/gate.py ask --root . --id <id> --question "<question, options, tried>" [--refused <token>]
python3 <this-skill-dir>/scripts/gate.py reach-review --root . --id <id> [--write] [--link <url|local>]
python3 <this-skill-dir>/scripts/gate.py diff-check --root . --id <id>
python3 <this-skill-dir>/scripts/gate.py screen-check --root . --id <id>
```

## 1. Intake & Setup (`gate.py next`)

1. Run `gate.py next --root .` and follow `action:` (`setup-board`, `brief`, `add-card`, `do-card`, `wait`, `stop`).
2. If `landed-waiting: <ids>` appears, tell the human to run `/jt-review-work` to close those cards. Never mark `merge:` or invoke `/jt-review-work` yourself.
3. **Setup board (`setup-board`):** Inspect the repo (`package.json`, lockfiles, `Cargo.toml`, `go.mod`, `pyproject.toml`) to detect `<TEST_CMD>`, `<SETUP_CMD>`, `<TYPECHECK_CMD>`, `<LINT_CMD>`, `<BROWSER_TOOL>`, `<STACK_LOCK>`, and `<REPO_SKILLS>`. Show the table with the source of each value (e.g. `TEST_CMD = npm test` from `package.json`) and **wait for human confirmation** before writing `card-loop/board.md` from [assets/board.template.md](assets/board.template.md).
4. **Brief & Add cards (`brief` / `add-card`):** Interview until intent, `do:`, `out:`, `files:`, and `pass:` are unambiguous. Wait for human approval before writing `card-loop/brief.md` or `card-loop/backlog/<id>.md` (from [assets/card.template.md](assets/card.template.md)) and adding `- [ ] **<id>** <name> (<kind>)` to `card-loop/board.md` on `<queue>`.

## 2. Select Execution Strategy & Minimum Evidence (`do-card`)

Choose your own implementation method (TDD, planning, subagents, worktrees are optional). The gate enforces only minimum outcome evidence by tier:

| Mode / Tier | When to Use | Minimum Evidence Checked by `gate.py` |
|---|---|---|
| **1. Direct Execution (`Quick`)** | `docs` (doc files only) or `style` without `screen: yes` | `<TEST_CMD>` green (or `no-suite`), no one-off checker. Skip `plan/<id>.md` and `diff-check`. |
| **2. Investigate & Debug (`Standard`)** | `fix` cards | `card-loop/plan/<id>.md` (from [assets/plan.template.md](assets/plan.template.md)), `<TEST_CMD>` green, `## review-diff` with latest code SHA (`gate.py diff-check`), plus JTek `gate.py screen-check` when `screen: yes`. |
| **3. Plan & Implement (`Standard`)** | `feat`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert` | Same as Standard above; review this card's diff via `<REPO_SKILLS>` or yourself before `review:`. Do not skip that review; if you cannot review the diff, do not set `review:`. A note in the plan is not that review. |
| **4. Decompose / Ask (`Critical`)** | Ambiguous intent, breaking contract, irreversible action, or oversized task | Do not guess. Run `gate.py ask` with options or a decomposition proposal, commit on `<queue>`, and move to the next card. |

## 3. Scope, Failure & Recovery, and Handoff

- **Scope Control:** Stay inside `do:` and never cross `out:`. Use `files:` as your starting point without reading the whole repo. Use the existing check commands on the board; never create a new check script unless `do:` orders it.
- **Failure & Recovery:** When `gate.py` refuses, obey `next:`:
  - `next: retry`: Read `detail:` and `log:`, fix the cause, and retry (at most **3 rounds** per card). After 3 failed rounds, run `gate.py ask` recording what was tried in all 3 rounds, commit on `<queue>`, and move to the next card.
  - `next: ask`: Run `gate.py ask` with the blocker from `detail:`, commit on `<queue>`, and move to the next card.
  - `next: stop`: Stop the entire queue and report to the human.
- **Continuous Improvement:** On recurring failures across cards, propose a new `chore` card with evidence for human approval. Never modify rule files (`SKILL.md` or `gate.py`) in the current card's diff.
- **Handoff:** Commit work on `card-<id>`. On `<queue>`, run `reach-review --root . --id <id>`. When `allowed`: if no remote, run `reach-review --root . --id <id> --write --link local`; if a remote exists, push `card-<id>`, open one draft PR (`gh pr create --draft --base <queue> --head card-<id>`), and run `reach-review --root . --id <id> --write`, then commit `card-loop/board.md` on `<queue>` and loop to the next card.
