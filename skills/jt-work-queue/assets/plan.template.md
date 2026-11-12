# Plan <id> - <short name>

The agent's working notes. The human does not accept a plan before review opens.

- Board item `<id>` on `jt-queue/board.md`
- kind:
- round: 1
- round-status: working
- Branch: task-<id>-<slug>
- Commit:

## Goal

<one sentence from the task heading do>

## Architecture

Optional. Leave this heading empty unless two modules must change together.

## Files

| Path | Action |
|---|---|
| `<path>` | create, edit, or delete |

## Steps

1. `<step>`

## Out of scope

-

## Done when

Each line is a command to run, or an artifact to open. Do not use a line that has no command and no artifact.

- `<command>`

## Escape

Stop when a line here is true. Run `gate.py ask`. Do not set `review:`.

-

## Kind notes

Keep only the part for this task's kind and delete the rest.

- **fix** `## repro`: the command that shows the bug, and its failing output before any change. After the fix the same command passes.
- **refactor** `## behavior lock`: the tests that pin current behavior, green before the first edit and green after the last. No public behavior changes.
- **perf** `## baseline`: the measuring command, the number before, and the number after.
- **revert** `revert of:`: the commit being undone, and why.

## evidence

One row per line under `pass:` in task.md. Quote the `pass:` line, name the command or artifact, and record the real result from this round.

| pass line | command or artifact | result |
|---|---|---|
| | | |

## before review

- Every Done when line was run. The command exited 0, or the artifact is the one the line names.
- No Escape line is true.
- Every `pass:` line has an `## evidence` row.
- `<TEST_CMD>` passes when the value is not `no-suite` (the gate runs it for every tier)
- `<TYPECHECK_CMD>` and `<LINT_CMD>` run when that cell has a command and the touched files are in scope
- Work that touches code has a `## review-diff` that cites the latest code commit, and `python3 <jt-work-queue skill folder>/scripts/gate.py diff-check` exits 0
- Screen work of every kind starts the real frontend and the real backend, then clicks what `pass` names, using the JTek screen command `python3 <jt-work-queue skill folder>/scripts/gate.py screen-check` or a check command already on the board
- Use the check commands already on the board. Do not create a new check script unless `do` says to create it

## send-back

Only after the human sends this task back. Copy each point from the `send-back:` note, then fix it and say where.

| point from the reviewer | change | evidence |
|---|---|---|
| | | |

Raise `round:` by one. Add a line to `jt-queue/lessons.md` for each point.

## review-diff

Review this task's diff, not your memory of it. Report only what you confirmed by following the code from source to effect. A finding you could not confirm is not a finding.

sha: <latest code commit on task-<id>>
(Across repos: instead of sha:, write one `<repo>: <latest code commit on task-<id> in that repo>` line per repo under `repos:`.)
verdict: pass | fix-needed
checked: scope - every changed file is under `files:`
checked: out - nothing under `out:` was touched
checked: callers and blast radius - who else uses what changed
checked: removed guards - why deleted lines were there (`git log -L`, `git blame`)
checked: slop - stray comments, debug output, dead code, needless abstraction
findings:
-

## decisions

| decision | why | evidence |
|---|---|---|
