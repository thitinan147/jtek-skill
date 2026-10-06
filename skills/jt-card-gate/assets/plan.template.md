# Plan <id> - <short name>

The agent's working notes. The human does not accept a plan before review opens.

- Board item `<id>` on `card-loop/board.md`
- kind:
- round: 1
- round-status: working
- Branch:
- Commit:

## do

## out

## files

## evidence

## steps

## open-review

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

## risks
