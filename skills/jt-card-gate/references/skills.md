# Two skill rows on the board

The steps live in [loop.md](loop.md). Open only a name the human wrote. An empty row opens nothing for that card. Do not install during an item. Do not open a name that is not in the row.

## `<TEK_SKILLS>` makes the work sharper

`/jt-do-work` may open one name from this row per moment, and only when that skill's `description` matches the moment.

| Moment | Words in that skill's description |
|---|---|
| The card still has two outcomes before you write `ask:` | grill, interview |
| A `fix` whose cause is still unclear, before a red test | diagnose, debug |
| Editing production code | YAGNI, stdlib, delete |

If no name in the row matches the moment, continue without opening a skill. Do not open this group during the repo diff review.

## `<REPO_SKILLS>` for this repo

`/jt-do-work` opens every name in this row after a commit whose kind is `feat`, `fix`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, or `revert`, and before it sets `review:`, to review this repo's diff. `docs` does not open.

If a name in this row is not on this machine, review this card's diff yourself before `review:`, even when another name in the row did open. Write the review under the plan heading `review-diff`, with the commit, the reviewer, and what you found. A note in the plan is not that review. Do not skip that review. On a card that touches code, `scripts/jt-diff-check` must exit 0 before `review:`. If you cannot review the diff, stop. Do not set `review:`. A name from `<TEK_SKILLS>` does not do this review.

Do not open a repo skill while picking a card, while writing `ask:`, or when the human calls `/jt-open-work`, `/jt-send-back`, `/jt-merge`, or `/jt-drop-card`.

If those skills pass but the evidence in loop.md is incomplete, do not open review.

A name from `<TEK_SKILLS>` does not replace the check commands on the board, and it does not replace an `update-rule` row when the same layer fails again. A row with no rule-file change is not enough. This row may be empty.
