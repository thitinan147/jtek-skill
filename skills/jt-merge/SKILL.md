---
name: jt-merge
description: Change the merge mark on the board line after the card commit is already on the queue branch. Use when the user runs /jt-merge. Do not run git merge, do not open a pull request, and do not merge one. The human invokes this.
disable-model-invocation: true
license: MIT
metadata:
  author: Thitinan
  version: "20"
  short-description: Change the merge mark on the board line
---

# jt-merge

The id after the command is the card to accept. If there is no id and exactly one line is `review:`, use that card. If several lines match, ask for the id and stop without changing the line.

The human calls this command only after looking at `/jt-open-work` for that card.

If the working tree is dirty, stop without changing the line.

That card's line must have status `review:`. If it is not `review:`, stop without changing the line.

Read the plan from branch `card-<id>`. If the `decisions` table is empty, or the diff from the queue branch to `card-<id>` does not match the `pass` heading, stop and say the evidence is incomplete. Do not change the mark.

Check that the human has already landed `card-<id>` on the queue branch with this command. This command does not run git merge, does not open a PR, and does not merge a PR.

```bash
python3 <jt-next-step skill folder>/gate.py landed --root . --id <id>
```

`landed: ancestor` means `git merge-base --is-ancestor card-<id> <queue>` passed, including a merge through a pull request that put that commit on the queue branch. `landed: squash` means `gh pr view card-<id>` returned `state` `MERGED`, even when a squash makes `git merge-base --is-ancestor` fail. If view cannot find the card, `gh pr list --head card-<id>` is enough when that item is `MERGED`. On `refused: not-landed`, tell the human to merge on GitHub first.

When the evidence is complete and the commit is on the queue branch, stay on the queue branch. This command changes only the mark on that line, to `- [x]` followed by `merge:`, then commits only `card-loop/board.md` on the queue branch.

This command changes only the mark on the line. It does not run git merge, does not open a PR, does not merge a PR, does not move the line, and does not touch code. The human merges on GitHub. The human merges both repos when the card heading names the paired repo. This command still changes only the mark on the primary board line.

Done when the queue-branch line is `merge:`, and this command did not run git merge and did not open or merge a PR.
