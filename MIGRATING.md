# Migrating

Upgrade notes for older queues and for `/scrum-spec`. For the full list of changes see [CHANGELOG.md](CHANGELOG.md).

## Migrating from v24.1 to v24.2

- **Size.** New. Unset `size:` stays `medium`, so an existing board still runs the full gate. `small` runs the full `<TEST_CMD>` unless you set `<AFFECTED_TEST_CMD>` or put `{files}` in `<TEST_CMD>`.
- **`<AFFECTED_TEST_CMD>`.** Optional. An empty cell is not in the `approve-commands` hash. Setting it is `commands-changed` until a human approves it.

## Migrating from v23 to v24

Command names changed. Queue files and spec files did not.

| Old command | New command |
|---|---|
| `/scrum-spec`, `/scrum-spec help` | `/jt-help` |
| `/scrum-spec split <flow>` | `/jt-spec-split <flow>` |
| `/scrum-spec ac <work>` | `/jt-spec-ac <work>` |
| `/scrum-spec handoff <work>` | `/jt-spec-handoff <work>` |
| `/scrum-spec board` | `/jt-board` |
| `/jt-work-queue` with no `jt-queue/board.md` | `/jt-setup` |
| `/jt-work-queue` to agree `brief.md` or add a task | `/jt-add-task` |
| `/jt-work-queue` to implement | `/jt-work` |
| `/jt-review-work` | `/jt-review` |
| `/jtek:jt-work-queue` | `/jtek:jt-setup`, `/jtek:jt-add-task`, or `/jtek:jt-work` |
| `/jtek:jt-review-work` | `/jtek:jt-review` |

- **No separate brief command.** When `gate.py next` prints `action: brief` or `action: add-task`, the command is `/jt-add-task`.
- **Spec files stay where they are.** `check.py` still requires the first line `<!-- scrum-spec -->`, still reads `scrum-spec/config.md`, and still fails an approval or a D line that has no human name and date or is signed by an AI. Do not rename that folder to make the commands match.
- **`jt-queue/` stays.** Boards, briefs, tasks, and command approvals in `.git/jt-queue/` keep working. You do not re-approve commands just because the skill was renamed.
- **Install one skill, or the set.** `npx skills add thitinan147/jtek-skill#v24.2.0 --skill jt-work` (space before the name). The plugin install is still the whole set.
- **v24.1 task branches.** `/jt-work` creates `type/<ticket-id>-<slug>` (for example `feat/BOOK-12-room-search`). Legacy `task-<id>-<slug>` still works; the gate prints `branch-deprecated:` when it finds one.

## Migrating from v22 to v23

- **Re-approve when lint or typecheck is set.** `LINT_CMD` and `TYPECHECK_CMD` are part of the `approve-commands` hash when the cell is not empty (the home table and each `## repos` block). A board that already has either command filled in refuses with `commands-changed` until a human runs `gate.py approve-commands` again. An empty cell is left out of the hash, so a board that never set them keeps its v22 approval.
- **Standard with no diff does not pass.** A Standard task whose branch has no diff outside `jt-queue/` is refused (`review-diff`, `no diff outside jt-queue/ to review`). It no longer answers `allowed` with `repo-review: skip`.
- **Lint and typecheck run on Standard.** A non-empty `LINT_CMD` or `TYPECHECK_CMD` runs in the task worktree after `TEST_CMD` and must exit 0. A failure counts as a round (`lint-failed`, `typecheck-failed`, `lint-timeout`, `typecheck-timeout`). Quick tier does not run them. An empty cell is `skip`.
- **`gates:` line.** `allowed` prints `tests`, `lint`, `typecheck`, `screen`, `review-diff`, `security`, `test-weakening` in that order.
- **Secrets stop the gate.** An added `.env` file (not `.env.example`), a private-key file, or an added `PRIVATE KEY` block refuses with `secret-suspect` and `next: ask`. The output names the file and never the value.
- **`test-weakening` is a report.** A deleted test file or an added `.skip` / `.only` / `xit` / `@skip` marker is printed on `allowed`. It does not refuse.
- **Lessons.** Copy the `enforced by` column from [`skills/jt-work/assets/lessons.template.md`](skills/jt-work/assets/lessons.template.md). The second time the same lesson appears, add a `chore` task whose `pass:` is a lint rule, a test, or a check, and cite it in that column.

## Migrating from v21 to v22

- **`plan.md` needs more before `review:` (Standard tier):** copy [`skills/jt-work/assets/plan.template.md`](skills/jt-work/assets/plan.template.md). `## review-diff` needs `sha:` (the latest code commit), `verdict: pass`, and at least one `checked:` line. `## evidence` needs one filled row `| pass line | command | result |` for every `pass:` line of the task. A v21 plan is refused with a `detail:` that says what is missing.
- **Failed rounds are counted:** each failed `reach-review` (test, timeout, setup) prints `round <n> of 3`. The third answers `next: ask`. `gate.py ask` starts the count again.
- **Every refusal has a `hint:`**, and a failed `start` or `click` keeps its output under `.git/jt-queue/logs/` (`log:`).
- **New helper files:** `assets/brief.template.md`, `assets/lessons.template.md` (`jt-queue/lessons.md`), `references/playbooks.md`, `references/red-flags.md`.
- **`chosen:` is removed from `task.template.md`.** Existing task files that still have it keep working.
- See [CHANGELOG.md](CHANGELOG.md) for the full list.

## Migrating from v20 to v21

### 1. Command Mapping (13 v20 skills → 2 v21 skills)

v24 split those two commands again. The v24 table at the top is the current mapping. The table below is what v21 did.

| v20 Command / Skill | v21 Replacement |
|---|---|
| `/jt-new-board` | `/jt-work-queue` (auto-detects when `jt-queue/board.md` is missing) |
| `/jt-find-skills` | Removed (v21 proposed `<REPO_SKILLS>` during board setup; that row is gone too) |
| `/jt-ask-brief` | `/jt-work-queue` (runs when queue is empty and no brief exists) |
| `/jt-new-card` | `/jt-work-queue <task>` |
| `/jt-next-step` | `/jt-work-queue` |
| `/jt-do-work` | `/jt-work-queue` |
| `jt-card-gate` | Merged into [`skills/jt-work/references/contract.md`](skills/jt-work/references/contract.md) |
| `/jt-read-board` | `/jt-review-work` |
| `/jt-open-work` | `/jt-review-work <id>` |
| `/jt-send-back` | `/jt-review-work` (`send-back:`) |
| `/jt-merge` | `/jt-review-work` (`merge:`) |
| `/jt-drop-card` | `/jt-review-work` (`drop: <reason>`) |
| `/jt-move-card` | `/jt-review-work` (move line between `first`, `main`, `later`, `closed`) |

### 2. Migrating `jt-queue/board.md`

- **`complete:` status (parent-child cards removed):** v21 stops the queue with `unknown-status` if a line uses `complete:`. Replace `- [ ] **<id>** ... complete:` with `- [x] **<id>** ... merge:` or remove the parent summary line. Dotted IDs (`1.1`, `1.2`) still work as normal independent cards.
- **`pair:` line (paired-repo support removed):** Ignored by the v21 gate; you may delete the `pair:` line from `jt-queue/board.md`.
- **`<TEK_SKILLS>` row:** Removed from [`skills/jt-setup/assets/board.template.md`](skills/jt-setup/assets/board.template.md). `<REPO_SKILLS>` was removed later as well: the agent reviews the diff itself. Existing boards with either row keep working; the gate never read them.

