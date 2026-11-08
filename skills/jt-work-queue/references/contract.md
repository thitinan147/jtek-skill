# Card Queue Contract, version 21

This contract belongs to skill `jt-work-queue`. All queue files live under `card-loop/` in the open repository.

## 1. Files & Branch Locations

- `card-loop/board.md` (on `<queue>` branch): Queue state and project command table (`<TEST_CMD>`, `<SETUP_CMD>`, `<TYPECHECK_CMD>`, `<LINT_CMD>`, `<BROWSER_TOOL>`, `<STACK_LOCK>`, `<REPO_SKILLS>`).
- `card-loop/brief.md` (on `<queue>` branch): Optional round brief accepted by the human.
- `card-loop/backlog/<id>.md` (on `<queue>` branch): Card contract (`kind:`, `do:`, `out:`, `pass:`, `files:`, `refs:`, `ask:`).
- `card-loop/plan/<id>.md` (on `card-<id>` branch): Required for `Standard` tier, optional for `Quick` tier. Contains `## Goal`, `## Architecture`, `## Files`, `## Steps`, `## Out of scope`, `## Done when`, `## Escape`, `## review-diff`, and `## decisions`.

## 2. Board Line Format & Status Permissions

```text
- [ ] **<id>** <short name> (<kind>) [ask: | review: <link> | send-back: <note>]
- [x] **<id>** <short name> (<kind>) merge: | drop: <reason>
```

- `<id>` must match `^\d+(\.\d+)*$` with no path traversal.
- Allowed status tokens: `ask:`, `review:`, `send-back:`, `merge:`, `drop:`. Any other colon token in the status slot stops the queue with `unknown-status`.
- **Agent permissions:** May add human-approved new card lines, but must update status tokens on existing lines **only** via `gate.py ask` and `gate.py reach-review --write`. Never write `merge:` or `drop:`.
- **Human permissions (`/jt-review-work`):** Writes `merge:`, `send-back:`, and `drop:`. Answers `ask:` by updating `card-loop/backlog/<id>.md` until intent is closed and clearing the `ask:` heading; on the next run, `gate.py next` resumes the card (`question-cleared`) and `reach-review --write` replaces `ask:` with `review:`.
- Same-topic cards sharing `layer:` must link each other under `refs:`. Do not split into parallel agents without a link.

## 3. Adaptive Gate Tiers (`Quick` vs `Standard`)

The gate computes the card's tier from `(<kind>)` on `card-loop/board.md` at `git merge-base <queue> card-<id>`. Tier can only escalate to `Standard`, never downgrade.

- **Quick Tier** requires all 5 conditions:
  1. Card kind at `merge-base` is `docs` or `style`.
  2. Every commit on `card-<id>` outside `card-loop/` has commit kind matching the card kind.
  3. Card does not set `screen: yes`.
  4. If `docs`: every changed file outside `card-loop/` is a documentation file (`.md`, `.rst`, `.adoc`, or extensionless/doc-extension `README`, `LICENSE`, `CHANGELOG`, `NOTICE`, `AUTHORS`, `CONTRIBUTING`).
  5. If `style`: code files may change; non-whitespace changes (`git diff -w --ignore-blank-lines`) are reported in `style-changes:`.
- **Standard Tier:** All other cards (`feat`, `fix`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`) and any `docs`/`style` card that escalates.

| Check | Quick | Standard |
|---|---|---|
| Branch `card-<id>` exists | ✓ | ✓ |
| Use existing check commands; no one-off checker script | ✓ | ✓ |
| `<TEST_CMD>` passes (or `no-suite`) | ✓ | ✓ |
| `gate.py diff-check` (`## review-diff` cites latest code commit SHA) | — | ✓ |
| JTek `gate.py screen-check` when `screen: yes` | — | ✓ |
| Report `outside-files:` and `style-changes:` | ✓ (both) | ✓ (`outside-files:` only) |

## 4. Plan, Three Rounds, and `<REPO_SKILLS>` Diff Review

- **Plan (`Standard` tier):** A `Done when` line is a command to run, or an artifact to open. If `Done when` has no command and no artifact, run `gate.py ask`. If `Escape` is empty, or an `Escape` line is true, run `gate.py ask` and do not set `review:`.
- **Three rounds:** One round is one full attempt. The evidence is that the relevant tests are green, and for screen work of every kind, not only `fix`, the same steps on the same screen do not show the bug. Screen work that cannot be clicked does not count as this round. After 3 failed rounds, run `gate.py ask`.
- **`<REPO_SKILLS>` diff review:** On `Standard` tier cards touching code, open `<REPO_SKILLS>` before `review:`. `docs` does not open. If no repo skill is on this machine, review this card's diff yourself before `review:`. Do not skip that review; if you cannot review the diff, do not set `review:`. A note in the plan is not that review.
- **Draft PR handoff:** When a git remote exists, push `card-<id>` and open a draft PR with `gh pr create --draft --base <queue> --head card-<id>`. If the draft PR cannot be opened, run `gate.py ask`. The line must not be `review:`. The gate refuses.
