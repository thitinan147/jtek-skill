# Changelog

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
