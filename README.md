# jtek-skill (v22)

***Constrain the outcome, not the agent.***

`jtek-skill` is an outcome-gated work queue for coding agents in a single Git repository. Instead of scripting every step the agent must follow, a deterministic Python gate ([`skills/jt-work-queue/scripts/gate.py`](skills/jt-work-queue/scripts/gate.py)) verifies the resulting diff, test execution, and review evidence before work can enter `review:`.

Designed for **Claude Code**, **Codex**, **Cursor**, **Grok Build**, and **Antigravity**.

## Install

```bash
# Recommended: pin a release so later changes cannot reach you unreviewed
npx skills add thitinan147/jtek-skill#v22.0.0 -g

# Or follow the default branch (latest, unpinned)
npx skills add thitinan147/jtek-skill -g
```

After installing, read [SECURITY.md](SECURITY.md): the gate runs your test command, so a human must approve it first.

## How It Works

```text
Human + Agent (/jt-work-queue)                          Human Only (/jt-review-work)
+----------------------------------------------------+  +------------------------------+
| 1. setup     Write board.md and gitignore jt-queue |  | Inspect diff, test evidence, |
| 2. brief     Agree this round in brief.md          |  | scope warnings, and UI shots |
| 3. add-task  Draft tasks/<id>/task.md              |  |                              |
| 4. do-task   Commit code on task-<id>              -->  merge:     (after landed)    |
|              Quick / Standard evidence             |  | send-back:  (fix & redo)     |
|              reach-review -> mark review:          <--  drop:       (cancel)         |
+----------------------------------------------------+  +------------------------------+
```

1. **Queue files stay local, code lives on `task-<id>`:** Keep `jt-queue/` gitignored. The gate reads it from the working tree, so the board, brief, and task files are not committed or pushed. Commit implementation on `task-<id>`. Worktrees are optional.
2. **Deterministic gate before review:** The agent cannot mark a task `review:` on its own. `gate.py reach-review --root . --id <id>` checks the tier evidence. Quick requires the test command to pass (or `no-suite`). Standard also requires `tasks/<id>/plan.md` whose `## evidence` covers every `pass:` line and whose `## review-diff` cites the latest code commit with `verdict: pass` and a `checked:` line, and `gate.py screen-check` when `screen: yes`. After three failed test rounds the gate answers `next: ask`.
3. **Human holds the merge key:** `/jt-work-queue` does not merge into `<queue>` and does not mark `merge:`. Only a human invoking `/jt-review-work` can close or send a task back, and `merge:` is written only after `task-<id>` has landed.

## Two Commands

| Command | Who Invokes It | Purpose |
|---|---|---|
| [`/jt-work-queue`](skills/jt-work-queue/SKILL.md) | Human or Agent | Set up `jt-queue/board.md`, capture a round brief, draft and add tasks, pick the next ready task, implement with adaptive verification (`Quick` / `Standard`), and hand off to `review:`. Cannot merge. |
| [`/jt-review-work`](skills/jt-review-work/SKILL.md) | **Human only** | Read the queue, surface tasks whose branches have already landed via [`skills/jt-review-work/scripts/landed.py`](skills/jt-review-work/scripts/landed.py), inspect `review:` evidence (`(<kind>)`, files touched outside `files:`, non-whitespace diffs on `style` tasks), and mark `merge:`, `send-back:`, `drop:`, or move board lines. |

*(In Codex, use `$jt-work-queue` and `$jt-review-work`.)*

## Day-to-Day Usage

### 1. Start a project or a new round (`setup` → `brief` → `add-task`)
Run `/jt-work-queue` in any Git repository:

```text
/jt-work-queue
```

- **No `jt-queue/board.md` yet (`setup-board`):** The agent inspects your repo (`package.json`, lockfiles, `Cargo.toml`, `go.mod`, `pyproject.toml`; `gate.py detect --root .` prints the suggested `<TEST_CMD>` and `<SETUP_CMD>` with their source), proposes `queue:`, `<TEST_CMD>`, `<SETUP_CMD>`, `<TYPECHECK_CMD>`, `<LINT_CMD>`, `<BROWSER_TOOL>`, `<STACK_LOCK>`, and `<REPO_SKILLS>`, waits for your approval, and writes `jt-queue/board.md` from [`skills/jt-work-queue/assets/board.template.md`](skills/jt-work-queue/assets/board.template.md). It also makes sure `.gitignore` contains `jt-queue/`.
- **Empty board and no `jt-queue/brief.md` (`brief`):** The agent reads the code first, then interviews you one question at a time to capture the goal and scope of the round in `jt-queue/brief.md` (from [`skills/jt-work-queue/assets/brief.template.md`](skills/jt-work-queue/assets/brief.template.md)).
- **Brief ready (`add-task`):** The agent drafts each `jt-queue/tasks/<id>/task.md` from [`skills/jt-work-queue/assets/task.template.md`](skills/jt-work-queue/assets/task.template.md) and adds it to `jt-queue/board.md` after your approval.

### 2. Add one or multiple tasks at once
Pass your task directly to `/jt-work-queue`:

```text
# Add a single task
/jt-work-queue Add rate limiting to POST /api/login

# Break a feature into several tasks
/jt-work-queue Break user authentication into 3 tasks:
1. Database migration and User model (first)
2. POST /api/login and session middleware (main)
3. Login form UI and E2E check (main, screen: yes)
```

- **Priority sections:** Place urgent tasks under `## first`, normal work under `## main`, and deferred ideas under `## later`. Open work in `first` or `main` keeps `later` waiting.
- **Slices:** Cut work into vertical slices that can pass their own `pass:`, not into layers. There is no `depends:`, so put the task that must come first under `## first`.
- **Overlap:** The queue stops when a ready task's `files:` overlap a task already in `review:` or `send-back:`. There is no `depends:` field.
- **Same topic:** Tasks that share `layer:` link each other under `refs:`.
- **Kinds (`<kind>`):** `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, and `revert`.
- **Verification tiers:** See [`skills/jt-work-queue/references/contract.md`](skills/jt-work-queue/references/contract.md).
  - **`Quick`:** `docs` limited to documentation files, or `style` without `screen: yes`. The test command passes, or the board says `no-suite`. No `plan.md` and no `diff-check`.
  - **`Standard`:** Every other kind. Requires `tasks/<id>/plan.md` from [`skills/jt-work-queue/assets/plan.template.md`](skills/jt-work-queue/assets/plan.template.md), a passing test command, a `## review-diff` that cites the latest code commit, and `gate.py screen-check` when `screen: yes`.

### 3. Work the queue (`do-task`)
Each invocation of `/jt-work-queue` follows `gate.py next`: a `send-back:` task first, then an `ask:` whose question is cleared, then the first ready task in `first`, then `main`, then `later`.

```text
/jt-work-queue
```

Before the gate runs `<TEST_CMD>` (or a task `start:` / `click:` command), a human approves the exact command strings:

```bash
python3 skills/jt-work-queue/scripts/gate.py approve-commands --root . --id 001
```

Commit code on `task-<id>`, not `jt-queue/`. On `<queue>`, run `reach-review --root . --id <id>`. When it prints `allowed`: if there is no remote, run `reach-review --root . --id <id> --write --link local`. If a remote exists, push `task-<id>` and open one draft PR (`gh pr create --draft --base <queue> --head task-<id>`). `reach-review --write` refuses with `pr-missing` until that open draft PR has head `task-<id>` and base `<queue>`, then run `reach-review --root . --id <id> --write`. That writes `review:` on `jt-queue/board.md`.

### 4. Review and land (`review:` → `merge:` / `send-back:` / `drop:`)
When one or more tasks reach `review:`, the human runs:

```text
/jt-review-work
```

Or to inspect a specific task directly:

```text
/jt-review-work 001
```

`/jt-review-work` reads `jt-queue/board.md` from the working tree (from the `<queue>` branch only when that file is tracked). It flags files touched outside `files:` and non-whitespace changes on `style` tasks, checks whether `task-<id>` has landed, and records the decision on the board only:
- **`merge:`** — Land `task-<id>` yourself first (`landed: ancestor` or `landed: squash`). The skill does not run `git merge`. Then change the line to `- [x]` and set `merge:`.
- **`send-back:`** — Change `review:` to `send-back: <reason>` on the board line. The line stays `- [ ]`.
- **`drop: <reason>`** — Close the line with `- [x]` and `drop: <reason>`, and close any open PR without merging.

## Repository Artifacts (`jt-queue/`)

See [`skills/jt-work-queue/references/contract.md`](skills/jt-work-queue/references/contract.md) for the complete file and gate contract:

```text
jt-queue/
├── board.md                 # Queue configuration (queue, test, skills) + task list
├── brief.md                 # Round brief agreed with the human before drafting tasks
└── tasks/
    └── 001/
        ├── task.md          # Approved task: kind, do, out, pass, files
        └── plan.md          # Standard-tier notes, including review-diff
```

Add `jt-queue/` to `.gitignore`. The gate reads that folder from the working tree, so a personal queue is not committed or pushed. Log output and command approvals stay under `.git/jt-queue/`.

## Security

`jtek-skill` runs shell commands (your test command and any task `start`/`click`) on your machine; it is not a sandbox. Before the gate runs them, a human must review and approve them with `gate.py approve-commands --root . --id <id>`, and the gate refuses if they change afterwards. Read [SECURITY.md](SECURITY.md) for the full trust model, what leaves your machine (a draft PR push when a remote exists), and how to report a vulnerability.

<details>
<summary><strong>Migrating from v21 to v22</strong></summary>

- **`plan.md` needs more before `review:` (Standard tier):** copy [`skills/jt-work-queue/assets/plan.template.md`](skills/jt-work-queue/assets/plan.template.md). `## review-diff` needs `sha:` (the latest code commit), `verdict: pass`, and at least one `checked:` line. `## evidence` needs one filled row `| pass line | command | result |` for every `pass:` line of the task. A v21 plan is refused with a `detail:` that says what is missing.
- **Failed rounds are counted:** each failed `reach-review` (test, timeout, setup) prints `round <n> of 3`. The third answers `next: ask`. `gate.py ask` starts the count again.
- **Every refusal has a `hint:`**, and a failed `start` or `click` keeps its output under `.git/jt-queue/logs/` (`log:`).
- **New helper files:** `assets/brief.template.md`, `assets/lessons.template.md` (`jt-queue/lessons.md`), `references/playbooks.md`, `references/red-flags.md`.
- **`chosen:` is removed from `task.template.md`.** Existing task files that still have it keep working.
- See [CHANGELOG.md](CHANGELOG.md) for the full list.

</details>

<details>
<summary><strong>Migrating from v20 to v21</strong></summary>

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

</details>

## Running Tests

```bash
python3 -m unittest discover -s tests
```
