# Task Queue Contract, version 22

This contract belongs to skill `jt-work-queue`. All queue files live under `jt-queue/` in the open repository.

## 1. Files & Branch Locations

- `jt-queue/board.md`: Queue state and project command table (`<TEST_CMD>`, `<SETUP_CMD>`, `<TYPECHECK_CMD>`, `<LINT_CMD>`, `<BROWSER_TOOL>`, `<STACK_LOCK>`, `<REPO_SKILLS>`).
- `jt-queue/brief.md`: Optional round brief accepted by the human.
- `jt-queue/tasks/<id>/task.md`: Task contract (`kind:`, `layer:`, `screen:`, `do:`, `out:`, `pass:`, `files:`, `refs:`, `ask:`; the screen-check command fields are described in `task.template.md`).
- `jt-queue/tasks/<id>/plan.md`: Required for `Standard` tier, optional for `Quick` tier. Contains `## Goal`, `## Architecture`, `## Files`, `## Steps`, `## Out of scope`, `## Done when`, `## Escape`, `## evidence`, `## review-diff`, and `## decisions`.

`jt-queue/` is gitignored by default, so the gate reads these paths from the working tree and they are never part of a commit or a push. Only when a path is tracked is it read from a branch: the board, brief, and `task.md` from `<queue>`, and `plan.md` from `task-<id>`.

## 2. Board Line Format & Status Permissions

```text
- [ ] **<id>** <short name> (<kind>) [ask: | review: <link> | send-back: <note>]
- [x] **<id>** <short name> (<kind>) merge: | drop: <reason>
```

- `<id>` must match `^\d+(\.\d+)*$` with no path traversal.
- Allowed status tokens: `ask:`, `review:`, `send-back:`, `merge:`, `drop:`. Any other colon token in the status slot stops the queue with `unknown-status`.
- **Agent permissions:** May add human-approved new task lines, but must update status tokens on existing lines **only** via `gate.py ask` and `gate.py reach-review --write`. Never write `merge:` or `drop:`. Never run `gate.py approve-commands` and never change `<TEST_CMD>`, `<SETUP_CMD>`, or a task's screen-check commands to make a refusal pass; the human approves those commands (stored in `.git`, outside every branch).
- **Human permissions (`/jt-review-work`):** Writes `merge:`, `send-back:`, and `drop:`. Answers `ask:` by updating `jt-queue/tasks/<id>/task.md` until intent is closed and clearing the `ask:` heading; on the next run, `gate.py next` resumes the task (`question-cleared`) and `reach-review --write` replaces `ask:` with `review:`.
- Same-topic tasks sharing `layer:` must link each other under `refs:`. Do not split into parallel agents without a link.

## 3. Adaptive Gate Tiers (`Quick` vs `Standard`)

The gate computes the task's tier from `(<kind>)` on `jt-queue/board.md`. A tracked board uses the kind at `git merge-base <queue> task-<id>`. A different kind on the current line raises the tier to `Standard`, and that tier does not return to `Quick`. A gitignored or untracked board uses the kind in the working tree, so editing `(<kind>)` there can raise or lower the tier.

- **Quick Tier** requires all 5 conditions:
  1. Task kind is `docs` or `style`: the merge-base kind when the board is tracked, otherwise the kind in the working tree.
  2. Every commit on `task-<id>` outside `jt-queue/` has commit kind matching the task kind.
  3. Task does not set `screen: yes`.
  4. If `docs`: every changed file outside `jt-queue/` is a documentation file (`.md`, `.rst`, `.adoc`, or extensionless/doc-extension `README`, `LICENSE`, `CHANGELOG`, `NOTICE`, `AUTHORS`, `CONTRIBUTING`).
  5. If `style`: code files may change; non-whitespace changes (`git diff -w --ignore-blank-lines`) are reported in `style-changes:`.
- **Standard Tier:** All other tasks (`feat`, `fix`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`) and any `docs`/`style` task that escalates.

| Check | Quick | Standard |
|---|---|---|
| Branch `task-<id>` exists | ✓ | ✓ |
| Use existing check commands; no one-off checker script | ✓ | ✓ |
| `<TEST_CMD>` passes (or `no-suite`) | ✓ | ✓ |
| `gate.py diff-check`: `## review-diff` cites the latest code commit SHA, has `verdict: pass` and a `checked:` line | — | ✓ |
| Every `pass:` line of the task appears in `## evidence` of `plan.md` | — | ✓ |
| JTek `gate.py screen-check` when `screen: yes` | — | ✓ |
| Report `outside-files:` and `style-changes:` | ✓ (both) | ✓ (`outside-files:` only) |

## 4. Plan, Three Rounds, and `<REPO_SKILLS>` Diff Review

- **Plan (`Standard` tier):** A `Done when` line is a command to run, or an artifact to open. If `Done when` has no command and no artifact, run `gate.py ask`. If `Escape` is empty, or an `Escape` line is true, run `gate.py ask` and do not set `review:`.
- **Three rounds:** One round is one full attempt. The evidence is that the relevant tests are green, and for screen work of every kind, not only `fix`, the same steps on the same screen do not show the bug. Screen work that cannot be clicked does not count as this round. The gate counts a round each time `<TEST_CMD>` or setup fails in `reach-review` (retrying an unchanged commit counts too), and prints `round <n> of 3`. On the third it answers `next: ask`: run `gate.py ask` with what each round tried. `gate.py ask` starts the count again.
- **`<REPO_SKILLS>` diff review:** On `Standard` tier tasks touching code, open `<REPO_SKILLS>` before `review:`. `docs` does not open. If no repo skill is on this machine, review this task's diff yourself before `review:`. Do not skip that review; if you cannot review the diff, do not set `review:`. A note in the plan is not that review.
- **Draft PR handoff:** When a git remote exists, push `task-<id>` and open a draft PR with `gh pr create --draft --base <queue> --head task-<id>`. If the draft PR cannot be opened, run `gate.py ask`. The line must not be `review:`. The gate refuses.
