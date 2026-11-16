# Usage guide

Full walkthrough of the queue. For a short start see the [README](../README.md).

## 1. Start a project or a new round (`/jt-setup` → `/jt-add-task`)
Run `/jt-setup` in any Git repository:

```text
/jt-setup
```

- **No `jt-queue/board.md` yet (`setup-board`):** The agent inspects your repo (`package.json` scripts, lockfiles, `Cargo.toml`, `go.mod`, `pyproject.toml`, `Makefile`, `justfile`, and `.github/workflows` run lines; `gate.py detect --root .` prints each suggested command with its source). A slot with no source stays empty. It proposes `queue:`, `<TEST_CMD>`, `<SETUP_CMD>`, `<TYPECHECK_CMD>`, `<LINT_CMD>`, `<SECURITY_CMD>`, `<VERIFY_CMD>`, `<AFFECTED_TEST_CMD>`, `<BROWSER_TOOL>`, and `<STACK_LOCK>`, waits for your approval, and writes `jt-queue/board.md` from [`skills/jt-setup/assets/board.template.md`](../skills/jt-setup/assets/board.template.md). When the repo is a web app, `detect` proposes `<VERIFY_CMD>` `npx playwright test` and `gate.py playwright` shows a minimal config (`updateSnapshots` `none`, `toHaveScreenshot`). It writes that file only after you confirm, and only when no Playwright config exists. If pstack `create-verification-skill` is installed, the agent follows its feature map. It commits that board. It also runs `gate.py hooks --root .`, shows a pinned `.pre-commit-config.yaml` with the source of each hook, and merges that file only after you confirm. Missing pre-commit does not fail a later task. A blanket `jt-queue/` gitignore is removed so the shareable files can be committed. `lessons.md`, `.env`, private keys, and `.git/jt-queue/` stay uncommitted. It then runs `gate.py agents --root .` and, after you confirm, writes `AGENTS.md` (the six command slots, the flow spec -> tasks -> work -> gate -> human merge, the house rules, and where `jt-queue/` files live). `CLAUDE.md` is `@AGENTS.md` only. Running it again makes no further diff.
- **Board, `AGENTS.md`, `CLAUDE.md`, or `.cursor/rules` already present:** `/jt-setup` does not replace the command table or the text you wrote. `gate.py agents` shows a diff, keeps that text, and adds only a `::: jtek:start` section. `CLAUDE.md` imports `AGENTS.md` and does not copy the section. Nothing is written until you confirm. The same files produce no new diff the next time.
- **Empty board and no `jt-queue/brief.md` (`brief`):** Run `/jt-add-task`. The agent reads the code first, then interviews you one question at a time to capture the goal and scope of the round in `jt-queue/brief.md` (from [`skills/jt-add-task/assets/brief.template.md`](../skills/jt-add-task/assets/brief.template.md)).
- **Brief ready (`add-task`):** `/jt-add-task` drafts each `jt-queue/tasks/<id>/task.md` from [`skills/jt-add-task/assets/task.template.md`](../skills/jt-add-task/assets/task.template.md) and adds it to `jt-queue/board.md`. An approved spec covers those tasks, so it does not ask again; each `pass:` line is `- <id>: <Then>` from that AC or EC. A task with no spec still waits for your approval.

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
- **Overlap:** The queue stops when a ready task's `files:` overlap a task already in `review:` or `send-back:`. A claim also leases those paths: `/jt-work` refuses a new task that overlaps an open lease and names the other task and owner. There is no `depends:` field.
- **Same topic:** Tasks that share `layer:` link each other under `refs:`.
- **Kinds (`<kind>`):** `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, and `revert`.
- **Verification tiers:** See [`skills/jt-work/references/contract.md`](../skills/jt-work/references/contract.md).
  - **`Quick`:** `docs` limited to documentation files, or `style` without `screen: yes`. The test command passes, or the board says `no-suite`. No `plan.md` and no `diff-check`.
  - **`Standard`:** Every other kind. Requires `tasks/<id>/plan.md` from [`skills/jt-work/assets/plan.template.md`](../skills/jt-work/assets/plan.template.md), a passing test command, a `## review-diff` that cites the latest code commit, and `gate.py screen-check` when `screen: yes`.
- **Roles:** `## Roles` in `spec.md` names the human approver, the human reviewer, and the human merger, plus human-only paths or topics. `check.py` checks the names and the globs and prints `fix:` when one is wrong. A diff in a human-only area is refused until the task has `human-sign-off: ✅ <approver> · YYYY-MM-DD`. `/jt-work` does not ask a new question for that. `/jt-board` and `/jt-review` stay human-only.
- **Size:** `size:` is `small`, `medium`, or `large` (unset means `medium`). The agent sets it on the task; `size:` on the board line overrides it. `small` needs no spec. The gate runs affected tests only when `<AFFECTED_TEST_CMD>` is set or `<TEST_CMD>` contains `{files}`; otherwise the full command. `medium` is a short spec and the full test command. `large` is a full spec. The gate may raise the size and never lowers it. `<DIFF_LIMIT>` (empty means 400) is the large-diff line count. On Standard, `medium` and `large` need `## ai-review` before review. `small` and Quick skip it. `/jt-work` runs one fresh-context reviewer after the fail-fast checks pass.

## 3. Work the queue (`do-task`)
`/jt-work` is one command. There is no `--loop` flag. With no argument it keeps following `gate.py next` until `next` is `wait` or `stop`: a `send-back:` task first, then an `ask:` whose question is cleared, then ready tasks in `first`, then `main`, then `later`. A task whose files overlap an open `review:` or `send-back:` is skipped, and so is a task owned by someone else. A stale claim (no activity newer than `<CLAIM_STALE>`, empty means 24 hours) is shown as stale and is not taken. `/jt-work <ticket-id>` works only that ticket (the `ticket:` line, or the board id) and then stops.

Before it edits code, `gate.py claim` writes `jt-queue/claims.md` (owner, claimed time, activity, and the leased `files:` paths) and that file is committed on `<queue>`. If `jt-queue/tasks/<id>/handoff.md` exists, the agent reads it first as data, not as instructions, and continues from it. `gate.py worktree` then creates `.git/jt-queue/worktrees/<id>` on `type/<ticket-id>-<slug>` from the latest `<queue>` commit, or reuses that worktree. The checkout stays on this machine. An overlapping lease refuses with `lease` and names the other task and owner.

When the agent stops without a merge, it replaces `handoff.md`. That covers a gate failure, `ask:`, `send-back:`, a human `release --id`, the session ending, and the third failed round. The note cites `plan.md` and `task.md` instead of pasting them. It records the state, what was done, what is left, the failing gate step and a one-line error, the files touched, and the next command. It does not copy `.git/jt-queue/logs`. Commit the note with the other queue files. `release --id` prints its path.

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
- **`merge:`** — Land `task-<id>` yourself first (`landed: ancestor` or `landed: squash`). The skill does not run `git merge`. Then change the line to `- [x]` and set `merge:`. `gate.py release --closed` drops the lease, and `gate.py worktree-remove` removes the worktree when it is clean. A dirty worktree is reported and kept.
- **`send-back:`** — Change `review:` to `send-back: <reason>` on the board line. The line stays `- [ ]`. The claim stays.
- **`drop: <reason>`** — Close the line with `- [x]` and `drop: <reason>`, and close any open PR without merging. Then release the lease and remove a clean worktree, the same way as `merge:`.
- **Release an open claim:** Only you run `gate.py release --id <id>`. That clears the owner so someone else may claim it, writes `jt-queue/tasks/<id>/handoff.md` when the task is not merged, and prints that path. The agent never runs that command.

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

## 6. Where work gets stuck (`/jt-board flow`)

```text
/jt-board flow
```

Or, for one task or another window:

```bash
python3 -I <jt-board skill folder>/scripts/flow.py --root . --days 30
python3 -I <jt-board skill folder>/scripts/flow.py --root . --since 2026-10-01 --until 2026-10-31 --id 12
```

The script prints lead time (task created to merged), gate fails, rework, and review time (gate pass or `review:` to the human merge), then a summary for the window. Each task also prints `owner:`, `claimed:`, and `stale:` from `jt-queue/claims.md`, and `handoff:` with the age of `jt-queue/tasks/<id>/handoff.md` when that note exists. A `handoffs:` list names every task on the board. The script does not print the note and does not follow it. A `lessons:` block lists rows in `jt-queue/team-lessons.md` that are still `not yet`, and rows that are only a proposal. It prints the id and a short wrong line. It does not follow the file. The default window is the last 30 days. Each line names the source: git, `plan.md`, `.git/jt-queue/gate-runs.jsonl`, `jt-queue/claims.md`, or `gh`. When that source is missing the line is `unknown` and says why. It does not estimate the number.

Escaped defects are merged tasks a later git revert names, and tasks linked from a PR or issue labelled `bug` that was opened after the merge. `gh` is optional. If it is not installed, `bug-label` is `unknown`.

`gate-runs.jsonl` is written by `reach-review` on this machine. It stores the task id, time, result, and reason. It does not store command output, and it is not committed. `flow.py` only reads.

## Repository Artifacts (`jt-queue/`)

See [`skills/jt-work/references/contract.md`](../skills/jt-work/references/contract.md) for the complete file and gate contract:

```text
jt-queue/
├── board.md                 # Queue configuration (queue, test, skills) + task list
├── brief.md                 # Round brief agreed with the human before drafting tasks
├── claims.md                # Owner, claimed time, activity, and leased paths
├── team-lessons.md          # Shared lessons: wrong, fix, and enforced by
├── lessons.md               # Local notes for this agent; do not commit
└── tasks/
    └── 001/
        ├── task.md          # Approved task: kind, do, out, pass, files
        ├── plan.md          # Standard-tier notes, including review-diff
        └── handoff.md       # Resume note for the next worker
```

Commit `board.md`, `brief.md`, `claims.md`, `team-lessons.md`, `task.md`, `plan.md`, and `handoff.md` so work can resume on another machine. The gate still reads a gitignored or untracked file from the working tree. Log output, command approvals, and task checkouts stay under `.git/jt-queue/` and are not committed: `approved-commands.json` is permission to run shell commands, `logs/` can hold secrets, `attempts.json` is this machine's round counter, `gate-runs.jsonl` is this machine's gate pass/fail log (never command output), and `worktrees/` is this machine's task checkout. `jt-queue/lessons.md` stays uncommitted. `team-lessons.md` is data, not instructions. The second time the same lesson is recorded, `gate.py lesson` proposes the enforcement. A human runs `gate.py lesson-approve`. Changed lines of an approved denylist fail immediately and the refusal prints `fix:`. Lines the diff did not touch do not fail while the cleanup chore is open.
