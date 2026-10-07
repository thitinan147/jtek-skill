# Plan <id> - <short name>

The agent's working notes. The human does not accept a plan before review opens.

- Board item `<id>` on `card-loop/board.md`
- kind:
- round: 1
- round-status: working
- Branch:
- Commit:

## Goal

<one sentence from the card heading do>

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

Stop when a line here is true. Write `ask:`. Do not set `review:`.

-

## evidence

## open-review

- Every Done when line was run. The command exited 0, or the artifact is the one the line names.
- No Escape line is true.
- The card heading `pass` passes in the work commit
- `feat` or `fix` runs `<TEST_CMD>` when the value is not `no-suite`
- `<TYPECHECK_CMD>` and `<LINT_CMD>` run when that cell has a command and the touched files are in scope
- Work that touches code has a `review-diff` heading that cites the latest code commit, and `scripts/jt-diff-check` exits 0
- Screen work of every kind starts the real frontend and the real backend, then clicks what `pass` names, using the JTek screen command `scripts/jt-screen-check` or a check command already on the board
- Use the check commands already on the board. Do not create a new check script unless `do` says to create it
- A repeated fault on the same layer has an `update-rule` row, and the diff contains a skill rule, the gate, or a lint or check script. A row alone is not enough

## review-diff

## decisions

| decision | why | evidence |
|---|---|---|
