# Migrating

Upgrade notes for older queues and for `/scrum-spec`. For the full list of changes see [CHANGELOG.md](CHANGELOG.md).

## Migrating from v24.8 to v24.9

- **Agent instructions.** Run `/jt-setup` again, or `gate.py agents --root .`, and confirm before `--write`. `AGENTS.md` is the single source. `CLAUDE.md` imports it (`@AGENTS.md`) and does not copy the section. Text you already wrote stays. The jtek section is the part between `::: jtek:start` and `::: jtek:end`.
- **Commands.** `detect` fills lint, typecheck, security, verify, and affected-test only when a script, a tool table, a Makefile or justfile target, or a CI `run` line already says so. An unknown slot stays empty. Confirm the table before it is written to the board or to `AGENTS.md`.
- **Board.** The command table is not rewritten. A short pointer to `AGENTS.md` is added at the end when you confirm. Re-running prints no further diff.
- **Install.** `npx skills add thitinan147/jtek-skill#v24.9.0 --skill jt-work`.

## Migrating from v24.7 to v24.8

- **Screen evidence.** A `screen: yes` task whose `pass:` line names an AC or EC id needs that id and a screenshot path in `## evidence` (`e2e/ac1.png`). A video or trace path is optional. Copy the rows in [`skills/jt-work/assets/plan.template.md`](skills/jt-work/assets/plan.template.md). A pass line with no AC id is unchanged.
- **Console errors.** An uncaught error, a console error, or a failed network load recorded in that section is `finding:` in the result cell. A row that still says the screen passed is `console-error`.
- **Snapshots.** `<VERIFY_CMD>` for a web app is `npx playwright test`. The gate does not run it when the command passes `--update-snapshots` or `-u`, or when the Playwright config would write missing snapshots. Set `updateSnapshots` to `none`. Updating baselines is a separate step you review. It is not part of the same task.
- **Setup.** Run `gate.py playwright --root .` on a web app and confirm before `--write`. An existing Playwright config is left as it is. If `create-verification-skill` is installed, `/jt-setup` follows its feature map.
- **Unchanged.** Fail-fast order (verify last), size tiers, `## ai-review`, and pre-commit hooks.
- **Install.** `npx skills add thitinan147/jtek-skill#v24.8.0 --skill jt-work`. Playwright CLI: `npm install -g @playwright/cli@latest` then `playwright-cli install --skills` (https://playwright.dev/docs/getting-started-cli and https://playwright.dev/agent-cli/skills).

## Migrating from v24.6 to v24.7

- **Hooks.** Optional. Run `/jt-setup` again, or `gate.py hooks --root .`, and confirm before `--write`. An existing `.pre-commit-config.yaml` is merged. Revs you already pinned stay. A file the merger cannot read is left untouched (`unparsed`).
- **Gate.** Nothing new to approve. Pre-commit is not part of `approve-commands` and not part of fail-fast. Size tiers and `## ai-review` are unchanged. When `pre-commit` is installed, `allowed` may print `hooks: ok` or `hooks: missing`.
- **Install.** `npx skills add thitinan147/jtek-skill#v24.7.0 --skill jt-work`. Install pre-commit from https://pre-commit.com/#install with `python3 -m pip install pre-commit`, then `pre-commit install`.

## Migrating from v24.5 to v24.6

- **Fresh-context review.** On Standard, effective size `medium` or `large` needs `## ai-review` in `plan.md` before `reach-review` prints `allowed`. Copy the new block from [`skills/jt-work/assets/plan.template.md`](skills/jt-work/assets/plan.template.md). `small` and Quick print `ai-review: skip` and need no new section.
- **One reviewer.** `/jt-work` runs `/interrogate` when it is installed, otherwise Matt `/pr`, otherwise `/ponytail-review` on a `large` task. It does not run two of them. With none installed, the section is the line `fallback: no reviewer skill installed`.
- **Not an approval.** Accepted findings are fixed and the gate runs again. The AI reviewer does not set `review:` and does not merge. `/jt-review` is still the only merge.
- **Unchanged.** Size tiers, `<AFFECTED_TEST_CMD>`, and the fail-fast order (secret, denylist, typecheck, lint, tests, verify) stay as in v24.5.
- **Install.** `npx skills add thitinan147/jtek-skill#v24.6.0 --skill jt-work`.

## Migrating from v24.4 to v24.5

- **Check order.** `reach-review` fails fast: secret scan, denylist, typecheck, lint, tests, verify. A failure prints `step:` and `skipped:` (the next step) so the cheapest problem is fixed first. Typecheck and lint run before tests. They still run only on Standard, and only when the cell is set.
- **Optional cells.** `<SECURITY_CMD>` is the secret scan when that program is installed (otherwise the built-in `secret-suspect` check, which still never prints the value). `<VERIFY_CMD>` runs after tests. `<DENYLIST>` or `jt-queue/denylist.txt` is `old -> replacement`. Empty means that step is skipped.
- **Approval.** Setting `<SECURITY_CMD>` or `<VERIFY_CMD>` is `commands-changed` until a human runs `approve-commands`. Leaving them empty keeps the current approval. `<DENYLIST>` is not a command.
- **Size.** `small`, `medium`, `large`, and `<AFFECTED_TEST_CMD>` are unchanged.
- **Install.** `npx skills add thitinan147/jtek-skill#v24.5.0 --skill jt-work`.

## Migrating from v24.3 to v24.4

- **Guards column.** New specs use `| # | Given | When | Then | Guards |`. Each EC's Guards cell names the AC it guards (`AC1`, or `AC1 AC2`). `check.py` errors when that cell is empty or names an AC that is not in the table. A spec that still has the old four columns does not fail: `check.py` prints `migration: Acceptance Criteria has no Guards column` and skips the link check. Add the column when you next edit the spec.
- **Approval and blocking questions.** A `✅` approval fails while an open question has Blocks `dev` or `AC`. Close or answer the question first. A question that Blocks `later` does not block approval. A spec that is still `❌ waiting for PO` is not failed for this reason.
- **Tasks from a spec.** `/jt-add-task` sets `spec:` and copies each owned AC and EC into `pass:` as `- <id>: <Then>`. The gate refuses `pass-ac` when a line does not match that Then, and `spec-unapproved` when the spec is not approved or a question still blocks `dev` or `AC`. Tasks with no `spec:` line are unchanged, including `small` tasks. Size tiers are unchanged.
- **One spec approval.** That approval covers the tasks derived from the spec, so `/jt-add-task` does not ask again and `/jt-work` does not ask you to approve each of those tasks or pass lines. `/jt-review` is still the only merge, and it is still human-only. Shell commands on the board still need the one-time `approve-commands` on each machine. That hash stays in `.git/jt-queue/approved-commands.json`.
- **Queue files to commit.** Commit `jt-queue/board.md`, `jt-queue/brief.md`, `jt-queue/tasks/<id>/task.md`, and `jt-queue/tasks/<id>/plan.md` (including `## decisions`) so the work can resume on another machine. If `.gitignore` ignores all of `jt-queue/`, remove that line. A queue that stays fully gitignored still runs from the working tree.
- **Keep local, and why.** `jt-queue/lessons.md` is notes for this agent, not the task a teammate resumes. `.git/jt-queue/approved-commands.json` is permission to run shell commands and must not travel in a commit. `.git/jt-queue/logs/` is command output and can hold secrets. `.git/jt-queue/attempts.json` is this machine's round counter. `.env` files (not `.env.example`) and private keys are secrets.
- **Install.** `npx skills add thitinan147/jtek-skill#v24.4.0 --skill jt-work`.

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
- **Install one skill, or the set.** `npx skills add thitinan147/jtek-skill#v24.3.0 --skill jt-work` (space before the name). The plugin install is still the whole set.
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

