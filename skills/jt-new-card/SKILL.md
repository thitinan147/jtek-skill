---
name: jt-new-card
description: Interview until each card has one ticket type, one path, and do, out, and pass headings that match the work. Propose several cards in one run when the work splits, then write the accepted cards and their board lines. Use when the user runs /jt-new-card or asks to add a card. Wait for them to accept the drafts before creating files.
license: MIT
metadata:
  author: Thitinan
  version: "20"
  short-description: Ask, then add the accepted cards
---

# jt-new-card

Ask until you have the cards the human wants. One call may propose several cards when the work splits. Create files only after the human accepts the draft.

Do not create `card-loop/backlog/<id>.md` and do not edit the board while asking. Do not call `/jt-do-work`.

## Before you ask

1. If `card-loop/board.md` is missing, stop and say to run `/jt-new-board` first.
2. If `card-loop/brief.md` exists, read it first. Draft cards must stay inside that file. Ask before you include work outside it. Do not put that work in the draft.
3. An id after the command is the first card's id. If there is no id, propose an id that has no file yet.
4. If `card-loop/backlog/<id>.md` already exists, do not use that id.
5. For facts in the open repo, open the file yourself. Do not ask something you can see.
6. Do not ask where the paired repo is. Read the `pair:` line on the board.

## Ask

Ask one round at a time. One round is every question you can ask now without guessing an answer you have not heard. Each question has one suggested answer. Then stop and wait for the human.

The first round asks what should happen. After the human answers, split the work into cards.

- Work that can be done separately, with different results, is a separate card.
- Work that is still one path and one result stays on one card.
- Cards that are the same bug or the same topic get the same `layer:` value, and each puts the other id under `refs`. Do not split into parallel agents.
- Each card writes `files` as the paths it will create or edit.
- A file that several cards must write together stays on the last card only. Earlier cards write only their own files.
- A card that composes something from other cards also lists those paths under `files`. That card is picked after the cards that create those paths are on the queue branch.
- Ask whether the user sees a screen. If they do, for every kind and not only `fix`, ask and record `screen: yes` plus the `start:` command, `port:` (comma-separated when there are several ports), `wait:` seconds, and the `click:` command. If they do not see a screen, write `screen: no`.

Each card has one kind, one path, the headings `do`, `out`, and `pass`, and a board section. `pass` becomes Done when on the plan. `out` becomes Out of scope. Read **Plan** in `references/loop.md` of skill `jt-card-gate`. Do not create the plan in this command.

Ask another round when any card still has one of these.

- The scope is vague.
- Two paths have different outcomes.
- You would delete something people may still use, and the card has not chosen.
- You would change a contract other callers use, and the card has not chosen.
- The kind is not yet one value from **Ticket kinds** in `references/loop.md` of skill `jt-card-gate`.
- The line does not yet know whether it belongs in **first**, **main**, or **later**.
- `pass` is not yet a command to run, or an artifact to open.
- You cannot yet name one Escape stop for the plan.

Stop asking when every card has one kind, one path, three headings that can be carried out, and a known board section.

## Draft

Show every card from `assets/card.template.md` of skill `jt-card-gate`. The `ask` heading is empty. The first card uses the id after the command. Later cards use the next id that has no file yet.

Ask which cards to accept, which to cut, and which to edit. If the human edits, show the whole draft again. Do not create files yet. Go to **Create** only when the human says they accept this set. Create only the cards the human did not cut.

## Create

1. If the `queue:` line is empty, stop. If edited files are dirty outside `card-loop/`, stop.
2. Check out the queue branch. Include an uncommitted `card-loop/board.md` in this command's commit.
3. Write `card-loop/backlog/<id>.md` for every accepted card. The file heading is `# <id> - <short name>`. A card that touches the paired repo appends `·` and the name on the `pair:` line. A card that does not touch the pair does not include that name.
4. Add the line `- [ ] **<id>** <short name> (<kind>)` for every card under the agreed section. A card that touches the paired repo puts `·` and that name before `(<kind>)`. Remove the `no items` line under that section when the first card enters it.
5. Commit the accepted card files and `card-loop/board.md` on the queue branch in one commit. One card uses `docs(<id>):` per **Commit standard** in `references/loop.md`. Several cards use `docs: add accepted cards`.

## Paired repo

Do not ask where the paired repo is. Read the `pair:` line on the board. Use only the name on that line.

If the line is `none` or empty, the card heading does not include a repo name.

A card that touches that repo is one card. The file heading and the board line contain `·` followed by the name on the `pair:` line. A card that does not touch the pair does not include that name.

Do not create `card-loop/paired.md` while creating the card. Do not create it because the board has the name.

Done when every card file and board line matches a card the human accepted, and every card's `ask` heading is still empty.
