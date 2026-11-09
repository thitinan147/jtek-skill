# Migrating

Upgrade notes for older queues. For the full list of changes see [CHANGELOG.md](CHANGELOG.md).

## Migrating from v21 to v22

- **`plan.md` needs more before `review:` (Standard tier):** copy [`skills/jt-work-queue/assets/plan.template.md`](skills/jt-work-queue/assets/plan.template.md). `## review-diff` needs `sha:` (the latest code commit), `verdict: pass`, and at least one `checked:` line. `## evidence` needs one filled row `| pass line | command | result |` for every `pass:` line of the task. A v21 plan is refused with a `detail:` that says what is missing.
- **Failed rounds are counted:** each failed `reach-review` (test, timeout, setup) prints `round <n> of 3`. The third answers `next: ask`. `gate.py ask` starts the count again.
- **Every refusal has a `hint:`**, and a failed `start` or `click` keeps its output under `.git/jt-queue/logs/` (`log:`).
- **New helper files:** `assets/brief.template.md`, `assets/lessons.template.md` (`jt-queue/lessons.md`), `references/playbooks.md`, `references/red-flags.md`.
- **`chosen:` is removed from `task.template.md`.** Existing task files that still have it keep working.
- See [CHANGELOG.md](CHANGELOG.md) for the full list.

## Migrating from v20 to v21

### 1. Command Mapping (13 v20 skills → 2 v21 skills)

| v20 Command / Skill | v21 Replacement |
|---|---|
| `/jt-new-board` | `/jt-work-queue` (auto-detects when `jt-queue/board.md` is missing) |
| `/jt-find-skills` | `/jt-work-queue` (proposes `<REPO_SKILLS>` during board setup) |
| `/jt-ask-brief` | `/jt-work-queue` (runs when queue is empty and no brief exists) |
| `/jt-new-card` | `/jt-work-queue <task>` |
| `/jt-next-step` | `/jt-work-queue` |
| `/jt-do-work` | `/jt-work-queue` |
| `jt-card-gate` | Merged into [`skills/jt-work-queue/references/contract.md`](skills/jt-work-queue/references/contract.md) |
| `/jt-read-board` | `/jt-review-work` |
| `/jt-open-work` | `/jt-review-work <id>` |
| `/jt-send-back` | `/jt-review-work` (`send-back:`) |
| `/jt-merge` | `/jt-review-work` (`merge:`) |
| `/jt-drop-card` | `/jt-review-work` (`drop: <reason>`) |
| `/jt-move-card` | `/jt-review-work` (move line between `first`, `main`, `later`, `closed`) |

### 2. Migrating `jt-queue/board.md`

- **`complete:` status (parent-child cards removed):** v21 stops the queue with `unknown-status` if a line uses `complete:`. Replace `- [ ] **<id>** ... complete:` with `- [x] **<id>** ... merge:` or remove the parent summary line. Dotted IDs (`1.1`, `1.2`) still work as normal independent cards.
- **`pair:` line (paired-repo support removed):** Ignored by the v21 gate; you may delete the `pair:` line from `jt-queue/board.md`.
- **`<TEK_SKILLS>` row:** Removed from [`skills/jt-work-queue/assets/board.template.md`](skills/jt-work-queue/assets/board.template.md). Only `<REPO_SKILLS>` is used for `Standard` tier diff reviews; existing boards with a `<TEK_SKILLS>` row continue to work without error.

