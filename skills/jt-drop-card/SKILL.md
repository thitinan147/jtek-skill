---
name: jt-drop-card
description: Change the board line to mark a dropped card with drop. Use when the user runs /jt-drop-card. Do not delete extra lines. The human invokes this.
disable-model-invocation: true
license: MIT
metadata:
  author: Thitinan
  version: "20"
  short-description: Mark a card dropped with drop on the board line
---

# jt-drop-card

The item id is the leading number. If it is present, use that card. The remaining words are the reason. If there is no number and exactly one line is still open, use that card and treat the whole typed text as the reason. If several cards match, ask for the id and stop without changing the line.

If there is no reason, ask for one line. Do not change the words until there is a reason.

If the working tree is dirty, stop without changing the line.

Check out the branch the `queue:` line names. Change `- [ ]` on that line to `- [x]` and append `drop: <reason>`. Do not delete other lines. Do not move the line. Commit only `card-loop/board.md` on the queue branch.

If a pull request for `card-<id>` is still open, close it without merging.

Done when the queue-branch line is `drop:`, it has a reason, and the other lines are still there.
