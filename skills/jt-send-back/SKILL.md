---
name: jt-send-back
description: Change the review line on card-loop/board.md to send-back. Use when the user runs /jt-send-back after looking at the review. The human invokes this.
disable-model-invocation: true
license: MIT
metadata:
  author: Thitinan
  version: "20"
  short-description: Mark the reviewed card send-back
---

# jt-send-back

The id after the command is the card to send back. If there is no id and exactly one line is `review:`, use that card. If several lines match, ask for the id and stop without changing the line.

If the working tree is dirty, stop without changing the line.

Check out the branch the `queue:` line names. On that same line, change `- [ ]` from `review:` to `send-back:`. The item stays `- [ ]`. Commit only `card-loop/board.md` on the queue branch.

Then check out `card-<id>` when that branch exists. If `round-status` is not `send-back`, set it to `send-back` and set `round` to 1. If it is already `send-back`, keep the current round. Commit only `card-loop/plan/<id>.md` on that branch, then check out the queue branch. If branch `card-<id>` does not exist, stop after the line commit and say the branch was not found.

Done when the queue-branch line is `send-back:` and this command has not edited the item's code.
