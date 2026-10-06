---
name: jt-ask-brief
description: Interview until the user's desired work is clear, then write card-loop/brief.md. Use when the user runs /jt-ask-brief or asks what they want to do before adding cards. Wait for them to accept the draft. Do not create cards or change the board.
license: MIT
metadata:
  author: Thitinan
  version: "20"
  short-description: Ask what to do, then write the brief
---

# jt-ask-brief

Ask what the human wants to do. Keep asking until the wanted work is clear. Write `card-loop/brief.md` only after the human accepts the draft.

Do not create a card. Do not edit a line on the board. Do not call `/jt-new-card` or `/jt-do-work`.

## Before you ask

1. If `card-loop/board.md` is missing, stop and say to run `/jt-new-board` first.
2. For facts in the open repo, open the file yourself. Do not ask something you can see.
3. If `card-loop/brief.md` already exists, read that file, then ask whether to write a new brief or stop. Do not overwrite it until the human accepts a new draft.

## Ask

Ask one round at a time. One round is every question you can ask now without guessing an answer you have not heard. Each question has one suggested answer. Then stop and wait for the human.

The first round asks what they want to do.

Ask another round while any of these is still true.

- You cannot yet say what exists when the work is done.
- Two paths have different outcomes and neither is chosen.
- The scope is too vague to split into cards.

Stop asking when you can say what they want, what this round will not do, and which work can be split into separate cards.

## Draft

Show the whole brief and ask whether this is the work they want.

```markdown
# Brief

want:
-

out:
-

split:
-
```

If the human edits, show the draft again. Do not create the file yet. Go to **Create** only when the human says they accept this draft.

## Create

1. If the `queue:` line is empty, stop. If edited files are dirty outside `card-loop/`, stop.
2. Check out the queue branch.
3. Write `card-loop/brief.md` from the accepted draft.
4. Commit only that file on the queue branch with `docs: add the brief`.

Done when the file matches the draft the human accepted, and no new card exists yet.
