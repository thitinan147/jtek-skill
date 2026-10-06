---
name: jt-card-gate
description: Rulebook for the jt-card-gate loop in card-loop/. Read it when carrying out jt-new-board, jt-ask-brief, jt-new-card, jt-read-board, jt-find-skills, jt-do-work, jt-next-step, jt-open-work, jt-send-back, jt-merge, jt-drop-card, or jt-move-card. Do not pick or implement a card from this skill alone.
license: MIT
compatibility: Codex, Claude Code, Cursor, Grok Build, and Antigravity. Needs a git repo. The loop stays in the open repo.
metadata:
  author: Thitinan
  version: "20"
  short-description: Rulebook for the jt-card-gate loop
---

# jt-card-gate

The whole rule set is [references/loop.md](references/loop.md). The points that open another skill are [references/skills.md](references/skills.md). Templates are in `assets/` next to this file.

The human calls these commands. The human does not call `/jt-card-gate` to start work.

| Command | Work |
|---|---|
| `/jt-new-board` | Create the board, fill the table and the skill names, and ask once for the paired repo. |
| `/jt-ask-brief` | Ask what to do, then write `card-loop/brief.md`. |
| `/jt-new-card` | Ask until the human accepts the draft. One call can create several cards. |
| `/jt-read-board` | Read the queue. |
| `/jt-find-skills` | Offer names for the human to choose. Do not write the board until they accept. |
| `/jt-do-work` | Do every card the line allows. Skip a card that is `review:`. |
| `/jt-open-work` | Open work that is `review:`. |
| `/jt-send-back` | The human changes the line to `send-back:`. |
| `/jt-merge` | The human changes the mark to `merge:` after the card commit is on the queue branch. Do not run git merge, open a PR, or merge a PR. |
| `/jt-drop-card` | The human changes the words to `drop`. Do not delete other lines. |
| `/jt-move-card` | Move a line on the board. Do not change its status. |
| `/jt-next-step` | Read the line and do the next step the rules allow. Do not merge. |

Screen work, before `review:`, uses the JTek screen command at `scripts/jt-screen-check` or a check command already on the board. Do not create a new check script. On a card that touches code, `scripts/jt-diff-check` must exit 0 before `review:`. A review heading in the plan is not enough. The detail is in [references/loop.md](references/loop.md). Use the existing check commands on the board.

If the human calls this skill directly, name the command and stop. Do not pick a card.
