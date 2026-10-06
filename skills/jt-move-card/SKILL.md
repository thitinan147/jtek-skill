---
name: jt-move-card
description: Move one line on card-loop/board.md. Use when the user runs /jt-move-card. Do not change that line's status, do not touch code, and do not merge.
license: MIT
metadata:
  author: Thitinan
  version: "20"
  short-description: Move a line on the board
---

# jt-move-card

The id after the command is the line to move. The remaining words are the destination heading, which is **first**, **main**, **later**, or **closed**. If there is no id or no heading, ask and stop without moving.

You may move only a line on `card-loop/board.md`.

Do not change the status on that line. Do not touch code. Do not merge.

If the working tree is dirty outside `card-loop/`, stop without moving.

Check out the branch the `queue:` line names. Move that line to the named heading and keep the status text on the line. Commit only `card-loop/board.md` on the queue branch.

Done when the line is under the new heading and the status on the line is unchanged.
