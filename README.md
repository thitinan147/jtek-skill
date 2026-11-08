# jtek-skill (v21)

***Constrain the outcome, not the agent.***

`jtek-skill` is an outcome-gated work queue for coding agents in a single Git repository. Instead of scripting every step the agent must follow, a deterministic Python gate ([`skills/jt-work-queue/scripts/gate.py`](skills/jt-work-queue/scripts/gate.py)) verifies the resulting diff, test execution, and review evidence before work can enter `review:`.

Designed for **Claude Code**, **Codex**, **Cursor**, and **Antigravity**.

## Install

```bash
npx skills add thitinan147/jtek-skill -g
```

## Two Commands

| Command | Who Invokes It | Purpose |
|---|---|---|
| [`/jt-work-queue`](skills/jt-work-queue/SKILL.md) | Human or Agent | Set up `card-loop/board.md`, capture a round brief, draft and add cards, pick the next ready card, implement with adaptive verification (`Quick` / `Standard`), and hand off to `review:`. Cannot merge. |
| [`/jt-review-work`](skills/jt-review-work/SKILL.md) | **Human only** | Read the queue, surface cards whose branches have already landed via [`skills/jt-review-work/scripts/landed.py`](skills/jt-review-work/scripts/landed.py), inspect `review:` evidence (`(<kind>)`, files touched outside `files:`, non-whitespace diffs on `style` cards), and mark `merge:`, `send-back:`, `drop:`, or move board lines. |

*(In Codex, use `$jt-work-queue` and `$jt-review-work`.)*

## Migrating from v20 to v21

### 1. Command Mapping (13 v20 skills → 2 v21 skills)

| v20 Command / Skill | v21 Replacement |
|---|---|
| `/jt-new-board` | `/jt-work-queue` (auto-detects when `card-loop/board.md` is missing) |
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

### 2. Migrating `card-loop/board.md`

- **`complete:` status (parent-child cards removed):** v21 stops the queue with `unknown-status` if a line uses `complete:`. Replace `- [ ] **<id>** ... complete:` with `- [x] **<id>** ... merge:` or remove the parent summary line. Dotted IDs (`1.1`, `1.2`) still work as normal independent cards.
- **`pair:` line (paired-repo support removed):** Ignored by the v21 gate; you may delete the `pair:` line from `card-loop/board.md`.
- **`<TEK_SKILLS>` row:** Removed from [`skills/jt-work-queue/assets/board.template.md`](skills/jt-work-queue/assets/board.template.md). Only `<REPO_SKILLS>` is used for `Standard` tier diff reviews; existing boards with a `<TEK_SKILLS>` row continue to work without error.

## Running Tests

```bash
python3 -m unittest discover -s tests
```
