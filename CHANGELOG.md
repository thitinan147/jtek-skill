# Changelog

## 26.0.0 - inner loop only

This version is a rewrite. It does not read the `jt-queue/` files of earlier versions.

- Eleven skills, one per step: `jt-work` (start, check, stop, and the order of the steps, in playbooks for a feature, a bug, and a refactor), `jt-understand`, `jt-build`, `jt-debug`, `jt-verify`, `jt-cleanup`, `jt-ship`, `jt-review` (the non-author verdict), `jt-babysit` (conflicts, failing CI, and review comments on an open pull request), `jt-learn`, and `jt-harness` (builds a repository's verify guide, feature map, and `verify` check). The spec skills, `jt-board`, `jt-add-task`, `jt-setup`, `jt-help`, `gate.py`, and the `jt-queue/` files are removed.
- jtek no longer names or calls any other skill set.
- `jtek.py` replaces the gate. `start` claims a ticket and creates its worktree, `check` runs the declared checks, `verdict` records the reviewer's result, `finish` moves the ticket to Review, and `stop` waits for the human.
- Several tickets can run at once, each in its own session and worktree. A claim is an atomic directory under the git common directory, so the same ticket cannot be taken twice.
- Checks are declared in `jtek.json` and read from the base branch. A ticket can name a check and cannot add a command. `jtek.json` is the only file added to a repository.
- A ticket can be a local file or text fetched from Notion (`start <url> --from-file <file>`). Both become the same snapshot.
- Statuses are Backlog, Todo, In Progress, Review, Done, and Cancelled. `waiting: input | approval` is a field on an In Progress ticket.
- Review requires passing checks on the current commit, a `PASS` or `PASS+NOTES` verdict from a session that did not write the change, saved evidence, and a pull request. The human merges. A ticket with `review: human` waives the verdict. A change to the code makes the verdict stale. A rebase that changes nothing keeps it, and the checks run again.
- `jtek.json` may declare `setup`, a command that installs dependencies in each new worktree, and `watch`, a list of file patterns.
- The result has an `attention:` line. It names `jtek.json`, `.jtek/`, CI config, lockfiles, a file that a check runs, a deleted test, and `watch` matches when the ticket changes them.
- Declared commands run with `JTEK_TICKET` and `JTEK_WORKTREE` set.
- `finish --evidence-file` saves what was run and seen, in at most 40 lines. It is required, and it is also the pull request body. `--attach` keeps screenshots and output with it. The result has an `evidence:` line.
- A green run on the base is remembered per base commit, so parallel tickets do not repeat it.
- `list --sync` removes the worktree of each Done ticket, unless it has uncommitted files.
- `jt-work` gives the path of each step skill, for agents that cannot load a skill by name.
- `start` runs the ticket's checks on the base before any edit. If one fails, the ticket is not started and stays Todo. `--no-baseline` skips this.
- `stop` refuses while the worktree has uncommitted files. Unfinished work is committed as `wip: ...` first.
- Every session ends with the same `jtek-result` block.
- The skills never choose the next ticket and never merge.
- Skill and plugin metadata are `26.0.0`.

## 25.0.0 - the queue can plan a batch and still stop for a human

- Specs keep `## Roles`. The approver, reviewer, and merger are people. `human-only` paths and topics are project-defined. A diff there is `refused: human-only` until the task has the spec approver's `human-sign-off`. `/jt-board` and `/jt-review` stay human-only. The agent does not merge.
- `/jt-work` composes pstack `/no-comments` before the draft PR. `/jt-spec-ac` composes pstack `/statechart` when the story has states.
- `blocked-by:` skips a task until those ids are `merge:` or `drop:`. `<MAX_PARALLEL>` and `<MAX_REVIEW>` wait instead of starting. `<QUOTA>` is the budget for one run (`gate.py run-start` resets it).
- `/jt-setup` proposes a CODEOWNERS lock for approved tests. A human commits it.
- `allowed` prints `risk:` (`low`, `medium`, `high`). High suggests `/ponytail-review`. A diff over `<DIFF_LIMIT>` is `refused: diff-limit` with `fix:`.
- `gate.py resume` prints the handoff Next line as data. `gate.py merge-queue` prints the human merge order and does not merge. `gate.py flags` describes an optional self-hosted Unleash revert and does not call the server.
- `## repos` remains the multi-repo queue. `evals/queue.json` is the deterministic eval for risk. `gate.py title` checks `type(scope): summary`. release-please and commitlint are templates, not a CI gate.
- Docs follow a Diátaxis layout (`docs/index.md`). Architecture decisions use `docs/adr/`.
- `/jt-work --loop` plans at most 100 tickets from the latest queue commit, skips blocked and unclear tasks, and caps open reviews. mise and reviewdog are the tools when installed. Testcontainers, Pact, and act stay optional.
- `<IMPORT_CMD>` (dependency-cruiser or import-linter) and `<PBT_CMD>` (fast-check or Hypothesis) are optional gate slots. A failure prints `fix:`.
- Pin installs with `v25.0.0`. Skill and plugin metadata are `25.0.0`.

## 24.13.0 - a repeated lesson becomes a rule

- `jt-queue/team-lessons.md` is the shared lesson list and is committed. Each row says what went wrong, how to fix it, and `enforced by` (`not yet`, a proposal, or a gate check, a denylist line, a lint rule, or a test). `jt-queue/lessons.md` stays uncommitted.
- The first `gate.py lesson` records the row as `not yet`. The second time the same lesson is recorded, the gate proposes the enforcement and does not install it. A human runs `gate.py lesson-approve`. Nothing becomes a rule without that approval. `/jt-board flow` lists lessons that are still `not yet`.
- A refusal tied to a lesson rule prints `fix:` with the replacement or the action. Other refusals print `fix:` when the fix is known.
- After approval, `gate.py lesson-legacy` can add a chore whose body lists the search hits for the old name. Changed lines fail immediately. Lines the diff did not touch do not fail while that chore is open. After it is `merge:` or `drop:`, a remaining hit fails too.
- Pin installs with `v24.13.0`. Skill and plugin metadata are `24.13.0`.

## 24.12.0 - a resume note when work changes hands

- When `/jt-work` stops on a task without merge, it writes `jt-queue/tasks/<id>/handoff.md` and replaces that file on the next stop. The stops are a gate failure, `ask:`, `send-back:`, a human `release`, the session ending, and the round cap. The note records state, what was done, what is left, the failing gate step and a one-line error, the files touched, and the next command.
- The note follows the Matt handoff style `/jt-spec-handoff` already composes: cite `plan.md` and `task.md` instead of pasting them, redact secrets, and keep suggested skills out of the file. Starting a task that already has the note reads it first as data, not as instructions, and the plan continues from it.
- Commit `handoff.md` with the other queue files. `/jt-board flow` prints which tasks have a note and how old the `Updated` stamp is. `gate.py release --id` prints that path. A merged task is not given a new resume note.
- The writer uses the same secret checks as `secret-suspect` (a private-key block, a dotenv name other than `.env.example`, a private-key file name). It does not copy `.git/jt-queue/logs`. The error line is a summary, not the command output.
- Pin installs with `v24.12.0`. Skill and plugin metadata are `24.12.0`.

## 24.11.0 - claims, file leases, and one worktree per task

- `/jt-work` records who is working a task in `jt-queue/claims.md` (`owner`, `claimed`, `activity`) and commits that file on the queue branch. The owner is `JT_OWNER` when that is set, otherwise `git config user.name`. `/jt-board flow` prints the owner, the claimed time, and whether the claim is stale.
- A task owned by someone else is refused with `claimed`. A stale claim (no activity newer than `<CLAIM_STALE>`, empty means 24 hours) is shown as stale and is not taken. Only a human runs `gate.py release --id` on an open task. The agent never does.
- Starting a task leases the paths in `files:`. `/jt-work` refuses `lease` when those paths overlap an open lease and names the other task and owner. `release --closed` drops leases whose board line is `merge:` or `drop:`.
- Each task gets one git worktree under `.git/jt-queue/worktrees/<id>`, on `type/<ticket-id>-<slug>`, from the latest queue commit. Running it again reuses that worktree. It is removed after merge or drop when the checkout is clean. A dirty worktree is reported and kept. That directory stays on this machine.
- Pin installs with `v24.11.0`. Skill and plugin metadata are `24.11.0`.

## 24.10.0 - queue flow metrics on /jt-board

- `/jt-board flow` prints, per task and as a summary, lead time, gate fails, rework, and review time for a window (default the last 30 days). Each value names its source. A missing source prints `unknown` and the reason. The script does not guess.
- Lead time is the first git commit of `task.md` to the merge (`gh` `mergedAt` when exactly one merged PR matches, otherwise the commit that wrote `merge:`). Review time is the first `review:` commit, or the local gate-pass row, to that same merge. Rework is `plan.md` `round:` minus one, checked against how many times the board line entered `send-back:`. When those counts differ, rework is `unknown`.
- Gate fails count failed `reach-review` runs recorded in `.git/jt-queue/gate-runs.jsonl`. `reach-review` appends one row per pass or gate failure (id, time, result, reason). It does not store command output. The file stays on this machine, with `attempts.json`. Older tasks have no rows, so their gate fails stay `unknown`.
- Escaped defects list merged tasks that a later git revert names, and tasks linked from a PR or issue labelled `bug` opened after the merge. `gh` is used only when it is installed. If it is missing, `bug-label` is `unknown` rather than zero.
- The spec `board.html` command is unchanged. The gate checks, who may merge, and which queue files are committed are unchanged.
- Pin installs with `v24.10.0`. Skill and plugin metadata are `24.10.0`.

## 24.9.0 - AGENTS.md is the repo's agent instructions

- `/jt-setup` writes `AGENTS.md` at the repo root. It lists `TEST_CMD`, `LINT_CMD`, `TYPECHECK_CMD`, `SECURITY_CMD`, `VERIFY_CMD`, and `AFFECTED_TEST_CMD`, the flow spec -> tasks -> work -> gate -> human merge, the house rules, and where `jt-queue/` files live.
- `CLAUDE.md`, when created or already present, is an `@AGENTS.md` import. It does not repeat that file.
- An existing `AGENTS.md`, `CLAUDE.md`, `.cursor/rules`, or board is not replaced. `gate.py agents` shows a diff, keeps the current text, and adds only a `::: jtek:start` section. The same files produce no new diff on the next run. `unparsed` means the file is left untouched.
- `gate.py detect` proposes those slots from `package.json` scripts, `pyproject.toml`, `Makefile`, `justfile`, `go.mod`, `Cargo.toml`, and `.github/workflows` run lines. A slot with no source stays empty.
- Pin installs with `v24.9.0`. Skill and plugin metadata are `24.9.0`.

## 24.8.0 - screen evidence a human can review

- On a screen task, `/jt-work` drives the app with Microsoft's Playwright CLI (`playwright-cli -s=<ticket-id>`, one session per worktree), not Playwright MCP. It reads console and network errors. An uncaught error or a console error on a touched screen is `finding:` in `plan.md` `## evidence`, next to a screenshot path for that AC id. A short video or trace path is optional.
- The gate still decides with `<VERIFY_CMD>` (`npx playwright test`, including `toHaveScreenshot`). `reach-review` refuses `snapshot-update` instead of running `--update-snapshots`, `-u`, or a Playwright config that would write baselines. `updateSnapshots` must be `none`. A baseline change is a separate step a human reviews. This task does not accept new snapshots.
- A `screen: yes` pass line that names an AC or EC id must quote that id in `## evidence` and name a screenshot path. Missing either is `evidence-missing`. A console or network error in that section that is not marked `finding:` is `console-error`.
- `/jt-setup` proposes `<VERIFY_CMD>` `npx playwright test` and a minimal `playwright.config.ts` when `gate.py detect` sees a web app. `--write` creates the file only when none exists. When pstack `create-verification-skill` is installed, `feature-map:` says so and the agent follows that map.
- Install docs name `npm install -g @playwright/cli@latest`, `playwright-cli install --skills`, and the official Playwright CLI and skills pages. The board slot is `VERIFY_CMD`.
- SkillSpector treats `npx playwright test` as that verify command, not an unpinned MCP server (`.skillspector-baseline.yaml`).
- Fail-fast order, size tiers, `## ai-review`, and pre-commit hooks are unchanged.
- Pin installs with `v24.8.0`. Skill and plugin metadata are `24.8.0`.

## 24.7.0 - pre-commit hooks as an early warning

- `/jt-setup` runs `gate.py hooks` and shows a `.pre-commit-config.yaml` with the source of each hook. It waits for confirmation. `--write` merges into an existing file. Existing repos, revs, and hook ids stay.
- The proposal pins typos, plus actionlint and zizmor when `.github/workflows` exists. It adds the board's `LINT_CMD` or secret scan only when that command is a cheap local tool, and a commit-msg hook (commitlint when that config exists, otherwise conventional-pre-commit).
- `reach-review` does not run pre-commit and does not fail when it is missing. When the `pre-commit` program is installed, `allowed` prints `hooks: ok` or `hooks: missing`.
- Size tiers, the fail-fast order, and `## ai-review` are unchanged.
- This repo checks typos, actionlint, and zizmor on commit.
- Pin installs with `v24.7.0`. Skill and plugin metadata are `24.7.0`.

## 24.6.0 - one fresh-context review before the human

- After the fail-fast checks pass, `/jt-work` invokes one reviewer in a fresh context that cannot read the implementer's chat. It receives only the spec acceptance criteria and edge cases, `task.md`, and the diff.
- The one reviewer is pstack `/interrogate` when that skill is installed, otherwise Matt `/pr`, otherwise `/ponytail-review` when the effective size is `large`. No second reviewer. If none of those skills is installed, `plan.md` records `fallback: no reviewer skill installed`.
- Findings go in `## ai-review` as `accepted:` or `rejected:` plus a reason. Accepted findings are fixed and the gate runs again. The reviewer does not approve or merge. `/jt-review` stays human-only.
- The gate requires that section on Standard `medium` and `large` (`refused: ai-review`). `small` and Quick print `ai-review: skip`. Size tiers and the fail-fast order are unchanged. `large` still prints `size-hooks:`; `worktree-rounds` is still only recorded.
- Pin installs with `v24.6.0`. Skill and plugin metadata are `24.6.0`.

## 24.5.0 - fail fast, cheapest check first

- `reach-review` stops at the first failure and prints `step:` and `skipped:` (the next step). Order: secret scan, deprecated-name denylist, `<TYPECHECK_CMD>`, `<LINT_CMD>`, tests, `<VERIFY_CMD>`.
- Secret scan runs `<SECURITY_CMD>` when that program is installed (the TruffleHog slot). Otherwise it keeps the v23 `secret-suspect` check. The output names the file and never the value, and the scan's own output is not printed.
- `<DENYLIST>`, or `jt-queue/denylist.txt` when the cell is empty, lists `old -> replacement` (for example `dmedasset -> dmecasset`). A hit in the diff fails with `deprecated-name` and names the replacement. An empty list skips the step.
- On Standard, typecheck runs before lint, and both run before tests. Quick still skips typecheck and lint. `<VERIFY_CMD>` runs after tests on every tier when the cell is set. Empty cells stay `skip`.
- Non-empty `<SECURITY_CMD>` and `<VERIFY_CMD>` join the `approve-commands` hash (home table and each `## repos` block). Empty cells stay out, so an existing approval still matches. `<DENYLIST>` is not a shell command and is not part of the hash.
- Size tiers and `<AFFECTED_TEST_CMD>` are unchanged. `allowed` prints `gates:` as `secret`, `denylist`, `typecheck`, `lint`, `tests`, `verify`, `screen`, `review-diff`, `test-weakening`.
- Pin installs with `v24.5.0`. Skill and plugin metadata are `24.5.0`.

## 24.4.0 - one spec approval, traced to the task

- `check.py` fails a `✅` approval while an open question Blocks `dev` or `AC`. A question that Blocks `later` does not. A spec still waiting for the PO does not fail for that reason.
- Acceptance Criteria gains a `Guards` column. Each EC names the AC it guards. An empty link, or a link to an AC that is not in the table, is an error. A table without that column prints `migration:` and still checks.
- A task with `spec:` must copy each `pass:` line from that row (`- <id>: <Then>`). The gate refuses `pass-ac` when the id or the Then does not match, and `spec-unapproved` when the spec is not approved. Tasks with no `spec:` line are unchanged. Size tiers are unchanged.
- One spec approval covers the tasks derived from it. `/jt-add-task` does not ask again for those tasks. `/jt-work` does not ask the human to approve each of them or their pass lines. `/jt-review` stays human-only. Shell commands still need the one-time `approve-commands` on each machine.
- Commit the queue files a teammate needs: `jt-queue/board.md`, `brief.md`, `tasks/<id>/task.md`, and `plan.md` (including `## decisions`). Leave local files uncommitted: `lessons.md` (notes for this agent, not the task); `.git/jt-queue/approved-commands.json` (permission to run shell commands; it must not travel in a commit); `.git/jt-queue/logs/` (command output can hold secrets); `.git/jt-queue/attempts.json` (this machine's round counter); `.env` files and private keys.
- Pin installs with `v24.4.0`. Skill and plugin metadata are `24.4.0`.

## 24.3.0 - compose external method skills

- `/jt-work` invokes obra/superpowers **executing-plans** and **test-driven-development** for Standard work; [playbooks.md](skills/jt-work/references/playbooks.md) is a short gate-habits fallback instead of inlined TDD and per-kind method text.
- Spec skills invoke Matt Pocock **grill-me** and superpowers **brainstorming** for questioning (outcomes unchanged: `check.py`, blocking questions, `(Recommended)` options). `/jt-spec-handoff` follows Matt Pocock **handoff** style; the `spec.md` template and checker rules stay.
- README and `skills/jt-help/references/install-before-use.md` move superpowers (`executing-plans`, `test-driven-development`, `brainstorming`) and **grill-me** to **Required**; official install links only in the reference file.
- Pin installs with `v24.3.0`. Skill and plugin metadata are `24.3.0`.

## 24.2.1 - install before use

- README and `/jt-help` document a fixed **Install before use** checklist: required tools, recommended skills, and optional tools with copy-paste install commands, the jtek step each plugs into, and board slots (`TEST_CMD`, `AFFECTED_TEST_CMD`, `LINT_CMD`, `SECURITY_CMD`, `VERIFY_CMD`). The list lives in `skills/jt-help/references/install-before-use.md` with official install URLs (no markdown links in references).
- Vitest, Jest, and pytest-testmon rows point at `<AFFECTED_TEST_CMD>` for `small` tasks, on top of v24.2.0 size tiers.
- Pin installs with `v24.2.1`. Skill and plugin metadata are `24.2.1`.

## 24.2.0 - size the process to the work

- A task has `size:` `small`, `medium`, or `large`, set when the task or the spec is created. A `size:` token on the board line overrides it. Unset stays `medium`, so an existing board still runs the full gate.
- `small` runs the full `<TEST_CMD>` unless the board sets `<AFFECTED_TEST_CMD>` or `<TEST_CMD>` contains `{files}`. The name-stem heuristic fills `{files}`. The cell can also be a command that selects its own tests (`npx vitest --changed`, `npx jest --findRelatedTests {files}`, `pytest --testmon`). When no affected test can be named, `small` still runs the full suite and prints `affected: none -> full suite`. `medium` and `large` run `<TEST_CMD>` unchanged. `small` needs no spec (`/jt-add-task`). `medium` is a short spec. `large` is a full spec.
- The gate raises that size, and never lowers it, when the diff touches auth or a migration or `.sql` file, or is larger than `<DIFF_LIMIT>` lines (empty means 400). `allowed` then prints `size-from:` and `escalate:` (`auth`, `migrations`, or `diff`).
- `large` prints `size-hooks: worktree-rounds, fresh-context-review, high-risk`. Those three are recorded only; this version does not run them.
- An empty `<AFFECTED_TEST_CMD>` is not part of the command approval. Setting it is `commands-changed` until a human approves it.

## 24.1.0 - conventional task branches

- `gate.py` and `landed.py` find the task branch as `type/<ticket-id>-<slug>` (for example `feat/BOOK-12-room-search`), using `ticket:` from `task.md` and the task kind. Legacy `task-<id>` / `task-<id>-<slug>` still work; `reach-review` prints `branch-deprecated:` when it uses one.
- `/jt-work` skill text, `contract.md`, README **Names**, and the usage docs describe the conventional branch as the default. Worktree temp dirs use the `jt-work-` prefix.
- Pin installs with `v24.1.0`. Skill and plugin metadata are `24.1.0`.

## 24.0.0 - commands that say what they do

- **Breaking:** `/jt-work-queue` is three commands. `/jt-setup` writes the board. `/jt-add-task` agrees the brief and drafts tasks (the gate's `brief` and `add-task` actions both print this command). `/jt-work` implements the next ready task. `/jt-review-work` is `/jt-review`. Plugin names follow the skill names (`/jtek:jt-work`, `/jtek:jt-review`, and the rest).
- **Breaking install:** each skill is a folder you can install alone, `npx skills add thitinan147/jtek-skill --skill <name>` with a space before the name. The Claude Code plugin still installs the whole set.
- The spec workflow from [scrum-spec](https://github.com/thitinan147/scrum-spec) 0.5.0 (`81d88ea`) is here as `/jt-spec-split`, `/jt-spec-ac`, `/jt-spec-handoff`, and `/jt-board`. `/jt-help` lists every command, the order, and which are human-only. Command names do not use the word scrum.
- `gate.py` checks the same things as v23. `next` prints the new command for the action. The refusal tokens, the approval hash, the `gates:` line, and the secret and test-weakening reports are unchanged.
- `check.py` is unchanged, including a human name and date on approvals and D lines, and a failure when an AI signed one. `check.py` and `board.py` still share one `specdoc.py`. The marker `<!-- scrum-spec -->` and `scrum-spec/config.md` stay, because the checker reads them. Existing spec files and `jt-queue/` boards need no rewrite.
- Names the skills write: a commit and a draft PR title are `type(scope): summary (<ticket-id>)`, using the id the ticket already has (`BOOK-12`, `#45`, a Notion id). The skills require an id and do not check its shape. `/jt-work` is one command with no `--loop` flag. It works ready tasks in board order and skips blocked ones, or only the ticket id it was given. The branch `gate.py` finds is still `task-<id>-<slug>`. The conventional branch `type/<ticket-id>-short-slug` is documented and not enforced.
- See [MIGRATING.md](MIGRATING.md).

## 23.0.0 - the gate runs the checks it already named

- **Breaking:** a Standard task with no diff outside `jt-queue/` no longer passes `reach-review`. A `(feat)` branch with zero commits used to answer `allowed` and `repo-review: skip` with no plan and no evidence. It is now `review-diff` / `no diff outside jt-queue/ to review`.
- **Breaking:** on Standard, a non-empty `<LINT_CMD>` or `<TYPECHECK_CMD>` runs in the task worktree after `<TEST_CMD>` and must exit 0 (`lint-failed`, `typecheck-failed`, and the matching timeouts; each counts as a round). An empty cell is `skip` and is not run. Quick tier does not run them. The same commands run per repo when a task lists `repos:`.
- **Breaking for boards that already set those cells:** `LINT_CMD` and `TYPECHECK_CMD` are now part of the `approve-commands` hash (home table and each `## repos` block) when the cell is not empty. Setting or changing one is `commands-changed` until a human approves it again. Empty cells stay out of the hash, so a v22 approval still matches. See [MIGRATING.md](MIGRATING.md).
- `allowed` prints one `gates:` line in a fixed order: `tests`, `lint`, `typecheck`, `screen`, `review-diff`, `security`, `test-weakening`.
- `reach-review` refuses with `secret-suspect` and `next: ask` when the diff adds a file whose name starts with `.env` (`.env.example` is allowed), a private-key file (`*.pem`, `id_rsa`, `id_dsa`, `id_ecdsa`, `id_ed25519`; not `*.pub`), or a `PRIVATE KEY` block. The output names the file or `file:line` and never the value.
- A deleted test file, or an added `.skip` / `.only` / `xit` / `@skip` / `xfail` marker, is reported as `test-weakening` on `allowed`. It does not refuse: the same diff can be a rename or a skip the task asked for, and the human judges it the way they already judge `outside-files:`.
- `assets/lessons.template.md` has an `enforced by` column. The second time the same lesson appears, add a `chore` task whose `pass:` is a lint rule, a test, or a gate check, and cite that check in the column.

## 22.2.0 - task branches say what they hold

- Task branches can be named `task-<id>-<slug>`, for example `task-12-login-rate-limit`. The slug is ASCII `a-z0-9` words joined by `-`; any other name is not seen as the task branch. The gate and `landed.py` find the branch by its `task-<id>` prefix, so nothing is stored on the board, and renaming the task later does not lose the branch. A plain `task-<id>` still works, so existing branches and open PRs need no change.
- One branch per task: when `task-<id>` and `task-<id>-<slug>` (or two slugs) both exist, `reach-review` refuses with `task-branch-missing`, and `detail:` names the branches to choose from.
- `landed` still finds a squash-merged slug branch after the branch was deleted from your clone, by matching the merged PR's head against `task-<id>-<slug>`.
- Fix: the documented draft PR command now passes `--title '<id>: <name>'` (single-quoted, since the name is board text) and `--body`. Without them `gh pr create` refuses when an agent runs it, because it cannot prompt. The body leaves out `do:` and `pass:` so task text stays in your gitignored `jt-queue/`.
- `getting-started.md` uses slug branches in the walkthrough; `plan.template.md` shows `Branch: task-<id>-<slug>`.
- CHANGELOG: the 22.0.0 and 22.1.0 entries are one list each again.

## 22.1.0 - one board for frontend and backend

- New, opt-in: a `## repos` section on the board declares sibling repos (one `### <name>` block each with `path:`, `queue:`, and the usual command table). Without it nothing changes, and existing command approvals still match.
- `next` stops with `repo-invalid`, `not-ready` (for example `be.TEST_CMD`), or `repo-missing` when a repo block is wrong or the repo is not at its path.
- A task can list `repos: fe, be`. `reach-review` then needs `task-<id>` in every listed repo, runs each repo's `TEST_CMD` in its own worktree, needs a `<repo>: <sha>` line per repo in `## review-diff`, reports `outside-files:` per repo, and refuses code in an unlisted repo (`repo-undeclared`). `--write` records one PR link per repo.
- `start:` can list `- <repo>: <command>` lines: the screen check starts every repo from its task branch and waits for all ports before `click:`.
- `landed.py` and `gate.py landed` answer `landed: all` only when every repo has landed, in `land:` order, with `order-warning:` when a repo landed out of order.
- `approve-commands` covers each repo's `path:`, `queue:`, `TEST_CMD`, `SETUP_CMD`, and a task's `start:` list with its `repos:`. Once a board has `## repos`, it always needs approval, even when every repo is `no-suite`, and `screen-check` checks it too.
- A repo cannot be named after a status word (`merge`, `review`, `ask`, `drop`, `send-back`).
- Removed `<REPO_SKILLS>` from the board template, `jt-work-queue` SKILL.md, and `contract.md`. The gate never read it; the agent reviews a Standard task's diff itself and records it in `## review-diff`, as before. Boards that still have the row keep working.
- README and CHANGELOG show the plugin marketplace pinned with `#v22.1.0`. `getting-started.md` marks the task 2 block as an excerpt.

## 22.0.1 - easier to start

- Claude Code plugin: `/plugin marketplace add thitinan147/jtek-skill#v22.0.1`, then `/plugin install jtek@jtek-skill`. The skills are also available as `/jtek:jt-work-queue` and `/jtek:jt-review-work`.
- New [Getting started](docs/getting-started.md) guide: the words the skill uses, and one real round from setup to merge with the gate's actual output.
- README rewritten for new users. The full walkthrough moved to `docs/usage.md`, and the v20/v21 upgrade notes to `MIGRATING.md`. Added `CONTRIBUTING.md`, issue templates, and a platform table (Windows is not supported yet; use WSL).
- Fix: when `## evidence` in `plan.md` misses a `pass:` line, the `hint:` no longer tells the agent to add a `## review-diff` section it already has.
- `jt-work-queue` SKILL.md: the tier table lists only the two gate tiers. Diff review and asking instead of guessing are separate rules, with the same content as before.
- A test keeps the version in `plugin.json`, `marketplace.json`, and both SKILL.md files the same.

## 22.0.0 - evidence the gate can check (breaking)

- **Breaking:** a `Standard` task now needs more in `plan.md` before `review:`. `## review-diff` must contain `verdict: pass` and at least one `checked:` line besides the commit SHA (a `verdict: fix-needed` refuses), and every `pass:` line of `task.md` must be quoted in the first cell of a filled `| pass line | command | result |` row of `## evidence`. Copy the new `assets/plan.template.md`; plans written for v21 are refused with `detail:` naming what is missing.
- **Breaking:** the gate counts failed rounds. Every failed `reach-review` (test, timeout, or setup) prints `round <n> of 3`, even when the commit did not change; the third answers `next: ask`. `gate.py ask` resets the count, and `next` forgets the count of a task once it is closed on the board. The count lives in `.git/jt-queue/attempts.json` and is written under a lock.
- Every refusal now prints a one-line `hint:`. `start-down` and `click-mismatch` keep the command output in a log (`log:`), and `related`, `review-diff`, `one-off-checker`, and `browser-empty` say what to fix in `detail:`.
- `gate.py detect --root .` prints the suggested `TEST_CMD` and `SETUP_CMD` with the file each came from. It writes nothing.
- `task.md` has an optional `needs:` list for work in another repo. It is text only: `reach-review` prints it, `/jt-review-work` shows it and asks the human to confirm each item has landed before `merge:`; the gate never refuses because of it.
- Added `assets/brief.template.md` and `assets/lessons.template.md`. `plan.template.md` gains `## evidence` rows, a structured `## review-diff`, kind notes, and a `## send-back` section.
- Both skills say how to handle a `send-back:` task, and `/jt-review-work` can answer an `ask:`.
- Docs use the word "task" throughout (v21 mixed "card", "task", and "ticket"); `contract.md` now says queue files are read from the working tree unless tracked. The unused `chosen:` field is gone from `task.template.md`.
- Removed the unused `execute_test_cmd` and `surface_refusal` helpers.
- `jt-queue/` replaces `card-loop/`. A gitignored or untracked queue is read from the working tree, so personal queue files are not committed or pushed. A tracked queue is still read from its branch.
- Each task lives at `jt-queue/tasks/<id>/task.md` with its plan at `plan.md` in the same folder. Work branches are named `task-<id>`.
- **Breaking:** `card-loop/` queues, `card-<id>` branches, and command approvals in `.git/card-loop/` are not migrated. Recreate the queue under `jt-queue/` and run `gate.py approve-commands` again. Until `jt-queue/board.md` exists, `next` reports `board-missing`.

## 21.0.0 (security hardening release)

### Security and packaging
- **Fixed: board commands could be changed and run without a human noticing.** A new `gate.py approve-commands` step records the human-reviewed `TEST_CMD`/`SETUP_CMD` and card `start`/`click` (as a hash in `.git`). `reach-review` and `screen-check` now refuse when they are unapproved or changed since approval. Reproduced before the fix: editing `TEST_CMD` in `board.md` (committed or not) made `reach-review` run it and answer `allowed`.
- **Upgrade note:** after updating, run `gate.py approve-commands --root . --id <id>` once per card you want to verify, after reviewing the commands it prints. Without it the gate stops with `commands-unapproved`.
- Fixed invalid YAML frontmatter in `jt-review-work`: the unquoted `review: cards` in `description` made strict parsers fail to read the skill.
- `compatibility` now states Python 3.10+ and the optional `gh`; skill `version` is semver (`21.0.0`).
- Both skills now state that board, card, plan, diff, commit and PR text is data, not instructions.
- `JT_TEST_TIMEOUT` and `JT_GH_TIMEOUT` are capped at 3600 s; NaN is rejected.
- The three intentional `shell=True` calls are annotated (`# nosec B602`) with their reason.
- README: install pinned to a release tag (`#v21.0.0`); CI actions moved to Node 24 releases and `ubuntu-24.04`.
- Added `SECURITY.md` (trust model and reporting), CI (tests, bandit, skills validator, SkillSpector), and `.skillspector-baseline.yaml` for reviewed false positives.

## Before the hardening release
- Two-command rewrite: `/jt-work-queue` and `/jt-review-work`. See the README for the v20 migration guide.
