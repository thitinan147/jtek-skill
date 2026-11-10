# Changelog

## Unreleased

- Removed `<REPO_SKILLS>` from the board template, `jt-work-queue` SKILL.md, and `contract.md`. The gate never read it; the agent reviews a Standard task's diff itself and records it in `## review-diff`, as before. Boards that still have the row keep working.
- README and CHANGELOG show the plugin marketplace pinned with `#v22.0.1`. `getting-started.md` marks the task 2 block as an excerpt.

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
