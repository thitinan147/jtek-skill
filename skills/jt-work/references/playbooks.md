# Playbooks for `do-task`

The gate checks evidence, not method. See SKILL.md for when to invoke **executing-plans** and **test-driven-development**. Those skills are not bundled here.

## If superpowers skills are missing

Write `plan.md` from the template, keep changes inside `files:` and `do:`, run `<TEST_CMD>` green, and fill `## evidence` for every `pass:` before `reach-review`.

## Gate habits (always)

- Start each task from `gate.py next`; re-read `task.md` and `jt-queue/lessons.md`. Prefer a fresh session per task when you can.
- Inside `files:`, remove dead code before adding; do not tidy files outside `files:`.
- Review the diff against `files:` and `out:` before `review:`; write what you checked in `## review-diff` (not your memory of the change).