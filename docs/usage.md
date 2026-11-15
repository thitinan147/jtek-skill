# Usage guide

Full walkthrough of the queue. For a short start see the [README](../README.md).

## 1. Start a project or a new round (`/jt-setup` → `/jt-add-task`)
Run `/jt-setup` in any Git repository:

```text
/jt-setup
```

- **No `jt-queue/board.md` yet (`setup-board`):** The agent inspects your repo (`package.json`, lockfiles, `Cargo.toml`, `go.mod`, `pyproject.toml`; `gate.py detect --root .` prints the suggested `<TEST_CMD>` and `<SETUP_CMD>` with their source), proposes `queue:`, `<TEST_CMD>`, `<SETUP_CMD>`, `<TYPECHECK_CMD>`, `<LINT_CMD>`, `<BROWSER_TOOL>`, and `<STACK_LOCK>`, waits for your approval, and writes `jt-queue/board.md` from [`skills/jt-setup/assets/board.template.md`](../skills/jt-setup/assets/board.template.md). It also makes sure `.gitignore` contains `jt-queue/`.
- **Empty board and no `jt-queue/brief.md` (`brief`):** Run `/jt-add-task`. The agent reads the code first, then interviews you one question at a time to capture the goal and scope of the round in `jt-queue/brief.md` (from [`skills/jt-add-task/assets/brief.template.md`](../skills/jt-add-task/assets/brief.template.md)).
- **Brief ready (`add-task`):** `/jt-add-task` drafts each `jt-queue/tasks/<id>/task.md` from [`skills/jt-add-task/assets/task.template.md`](../skills/jt-add-task/assets/task.template.md) and adds it to `jt-queue/board.md` after your approval.

## 2. Add one or multiple tasks at once
Pass your task directly to `/jt-add-task`:

```text
# Add a single task
/jt-add-task Add rate limiting to POST /api/login

# Break a feature into several tasks
/jt-add-task Break user authentication into 3 tasks:
1. Database migration and User model (first)
2. POST /api/login and session middleware (main)
3. Login form UI and E2E check (main, screen: yes)
```

- **Priority sections:** Place urgent tasks under `## first`, normal work under `## main`, and deferred ideas under `## later`. Open work in `first` or `main` keeps `later` waiting.
- **Slices:** Cut work into vertical slices that can pass their own `pass:`, not into layers. There is no `depends:`, so put the task that must come first under `## first`.
- **Frontend and backend in separate repos:** Keep one board and declare the other repo under `## repos` (see [section 5](#5-frontend-and-backend-in-two-repos)). Use `needs:` only for work that is not on this board; the gate prints it but does not check it.
- **Overlap:** The queue stops when a ready task's `files:` overlap a task already in `review:` or `send-back:`. There is no `depends:` field.
- **Same topic:** Tasks that share `layer:` link each other under `refs:`.
- **Kinds (`<kind>`):** `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, and `revert`.
- **Verification tiers:** See [`skills/jt-work/references/contract.md`](../skills/jt-work/references/contract.md).
  - **`Quick`:** `docs` limited to documentation files, or `style` without `screen: yes`. The test command passes, or the board says `no-suite`. No `plan.md` and no `diff-check`.
  - **`Standard`:** Every other kind. Requires `tasks/<id>/plan.md` from [`skills/jt-work/assets/plan.template.md`](../skills/jt-work/assets/plan.template.md), a passing test command, a `## review-diff` that cites the latest code commit, and `gate.py screen-check` when `screen: yes`.

## 3. Work the queue (`do-task`)
`/jt-work` is one command. There is no `--loop` flag. With no argument it keeps following `gate.py next` until `next` is `wait` or `stop`: a `send-back:` task first, then an `ask:` whose question is cleared, then ready tasks in `first`, then `main`, then `later`. A task whose files overlap an open `review:` or `send-back:` is skipped. `/jt-work <ticket-id>` works only that ticket (the `ticket:` line, or the board id) and then stops.

```text
/jt-work
/jt-work '#45'
```

Before the gate runs `<TEST_CMD>` (or a task `start:` / `click:` command), a human approves the exact command strings:

```bash
python3 skills/jt-work/scripts/gate.py approve-commands --root . --id 001
```

Commit code on the task branch `type/<ticket-id>-<slug>` (for example `feat/BOOK-12-room-search`; the slug is ASCII `a-z0-9` words joined by `-`). Legacy `task-<id>-<slug>` still works. Keep one branch per task; the gate refuses `task-branch-missing` when there are two. The commit subject and the PR title are `type(scope): summary (<ticket-id>)`, for example `feat(booking): add room search API (BOOK-12)`. The ticket id is copied from `ticket:`. The type is the task kind. On `<queue>`, run `reach-review --root . --id <id>`. When it prints `allowed`: if there is no remote, run `reach-review --root . --id <id> --write --link local`. If a remote exists, push the branch and open one draft PR (`gh pr create --draft --base <queue> --head feat/BOOK-12-room-search --title 'feat(booking): add room search API (BOOK-12)' --body 'Task <id> from jt-queue.'`). `reach-review --write` refuses with `pr-missing` until that open draft PR has the task branch as head and base `<queue>`, then run `reach-review --root . --id <id> --write`. That writes `review:` on `jt-queue/board.md`.

## 4. Review and land (`review:` → `merge:` / `send-back:` / `drop:`)
When one or more tasks reach `review:`, the human runs:

```text
/jt-review
```

Or to inspect a specific task directly:

```text
/jt-review 001
```

`/jt-review` reads `jt-queue/board.md` from the working tree (from the `<queue>` branch only when that file is tracked). It flags files touched outside `files:` and non-whitespace changes on `style` tasks, checks whether `task-<id>` has landed, and records the decision on the board only:
- **`merge:`** — Land `task-<id>` yourself first (`landed: ancestor` or `landed: squash`). The skill does not run `git merge`. Then change the line to `- [x]` and set `merge:`.
- **`send-back:`** — Change `review:` to `send-back: <reason>` on the board line. The line stays `- [ ]`.
- **`drop: <reason>`** — Close the line with `- [x]` and `drop: <reason>`, and close any open PR without merging.

## 5. Frontend and backend in two repos

Clone the repos side by side and keep the board in the one you open most (the home repo):

```text
~/work/app-fe/   # home: jt-queue/ lives here
~/work/app-be/
```

Tell the agent about the other repo:

```text
/jt-setup add repo be ../app-be
```

It runs `gate.py detect --root ../app-be`, shows you this block, and writes it after you confirm:

```text
## repos

### fe
path: .

### be
path: ../app-be
queue: main

| Value | In this repo |
|---|---|
| `<TEST_CMD>` | npm ci && npm test |
| `<SETUP_CMD>` | npm ci |
| `<TYPECHECK_CMD>` | |
| `<LINT_CMD>` | |
| `<STACK_LOCK>` | node · express · jest · no ORM |
```

Then approve the commands once: `approve-commands` now covers the `be` path, queue, and commands too.

A task that needs both sides stays one vertical slice:

```text
kind: feat
screen: yes
start:
- be: npm run dev
- fe: npm run dev
port: 4000, 3000
click: fe: npx playwright test login.spec.ts

files:
- be:src/routes/login.ts
- fe:src/pages/Login.tsx

repos: fe, be
land: be, fe
```

- The agent commits on `task-<id>` in both repos. `reach-review` runs each repo's `TEST_CMD` in its own worktree, starts both apps from the task branches for the screen check, and needs `## review-diff` to cite `fe: <sha>` and `be: <sha>`.
- `--write` records both PRs: `review: fe:<url> be:<url>`.
- In `/jt-review`, `landed.py` prints each repo's state in `land:` order. `merge:` needs `landed: all`. If the frontend landed before the backend it prints `order-warning:` so you can check nothing broke.

## Repository Artifacts (`jt-queue/`)

See [`skills/jt-work/references/contract.md`](../skills/jt-work/references/contract.md) for the complete file and gate contract:

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
