---
name: jt-open-work
description: Show the card marked review against its pass heading, the decision table, the diff, test results, and screen evidence. Use when the user runs /jt-open-work. Do not change the board line.
license: MIT
metadata:
  author: Thitinan
  version: "20"
  short-description: Show the card waiting for review
---

# jt-open-work

The id after the command is the card to open. If there is no id and exactly one line is `review:`, open that card. If several lines match, ask for the id and stop without changing the line.

Read the board from the branch the `queue:` line names. Read the card, the plan, and the diff from branch `card-<id>` against the queue branch. You may stay on another branch. Do not check out.

Lay out these five things for the human to compare.

1. The card heading `pass`.
2. The `decisions` table in the plan on branch `card-<id>`. If it is empty, say the table is empty.
3. The `review-diff` heading in the plan on branch `card-<id>`.
4. The diff from the queue branch to `card-<id>`, and whether it stays inside `do` and does not cross `out`.
5. The test result, and screen evidence when the card needs it.

Do not change the line on the board. Do not check `merge:` or `drop:`.

Done when the human has seen those five things and the queue-branch line is still `review:`.
