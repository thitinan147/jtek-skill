# Changelog

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
