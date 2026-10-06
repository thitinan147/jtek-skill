---
name: jt-read-board
description: Read card-loop/board.md and report the next card and lines marked review, send-back, and ask. Use when the user runs /jt-read-board or asks what is on the board. Do not implement.
license: MIT
metadata:
  author: Thitinan
  version: "20"
  short-description: Read the card-loop board
---

# jt-read-board

If `card-loop/board.md` is missing, say to run `/jt-new-board` first, then stop. If the file exists, read it from the branch the `queue:` line names, then report in the pick order from skill `jt-card-gate`.

- The next item to work is `send-back:` first, then `ask:` whose `ask` heading in the card is empty, then an item that has no `ask:`, `review:`, or `send-back:` yet. Walk **first**, then **main**. Walk **later** only when every card under **first** and **main** has no unfinished `- [ ]`.
- Every item still waiting as `review:`, `send-back:`, or `ask:`. The queue does not stop because a line is `review:`.
- If the `queue:` line is empty, say the board is not ready.
- Cards that share `layer:` but whose `refs` heading does not point at the other card are still unlinked. Do not report them as parallel work.

Do not edit files. Do not start work. Do not check out.

Done when that report has been sent.
