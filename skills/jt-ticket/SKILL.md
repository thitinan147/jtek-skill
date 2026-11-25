---
name: jt-ticket
description: Turns what the owner wants into tickets a session can work, one per pull request, with Done when items that can be seen working and the facts taken from the code. Splits large work into ordered tickets, and creates each approved one as Backlog, on the board or as a ticket file when the repository has no board. Use when the user types /jt-ticket, and only then.
disable-model-invocation: true
argument-hint: "<what you want built or fixed>"
---

# jt-ticket

The owner says what they want. You turn it into tickets that `jt-work` can work without guessing. The owner decides what is built; you find the facts and write it down. A ticket is created on the board only after the owner approves it, and only as Backlog: moving it to Todo releases it, and that stays the owner's.

The rules a good ticket follows are in `jt-work`'s `references/ticket-template.md`. Read them first.

## 1. Restate

Say in two or three lines what the owner wants and why, in their words. Name the repository it belongs to, from `jtek.json` (`name`), and the board, from its `board` link. An empty `board` means the tickets are files. When it spans two repositories, say which part goes where.

## 2. Find the facts yourself

Read the code the work touches: the entry point a user reaches, the function behind it, its tests, and one caller. Run what a run can answer. Search the history and the open pull requests for the same change, and for one that was reverted. Write down what the code does today, with the file and line.

Ask the owner only what the code cannot tell you: what the product should do. A fact you can read is never a question.

## 3. Ask for the decisions

Ask at most four questions at a time, the one that changes the most first. Each one stands alone, says what it changes, offers your recommended answer with its reason, and is numbered so the owner can answer "1 yes, 2 no". Two wishes that cannot both hold are always a question. Go on with the next round until nothing that changes a `Done when` item is open.

## 4. Draft

Write each ticket in the ticket format of `jt-work`'s `references/ticket.md`: a title, `kind:`, `repo:`, `area:`, and the three sections.

- **Goal:** who wants what, and why. For a bug: the steps, the wrong result, and the right one.
- **Done when:** one outcome per top-level item, each one seen from outside (a command, a request, a screen) with a concrete input and result. No "fast", "works", "secure", or "quicker" unless the item has a measurable comparison (under 200 ms) or the quality word itself sits inside a backtick or a quote (`the label reads `faster``). A backtick elsewhere does not help: `feels faster `x`` is refused, and so is a line that only says the command prints something. A digit anywhere, including `v2`, a Thai digit, or a fullwidth digit, does not make a quality checkable. Format characters (zero-width, word joiner, direction marks, soft hyphen) are stripped before the check. Ordinary Thai such as ไม่ง่าย is allowed. รู้สึกเร็วขึ้น and ใช้งานดีขึ้น are not. ความเร็ว is the noun for speed and is refused on its own; the short word เร็ว does not also match inside it. `jtek.py ticket` refuses the quality. Fix that before `start`. Put in the edge cases the owner decided.
- **Out of scope:** behaviour that must stay exactly as it is now, named as behaviour, with the code's facts you found.

## 5. Size and order

One ticket is one pull request a session can finish, and a reviewer can break item by item: as a rule, at most six `Done when` items. When there are more, when the items fall into groups that could ship apart, or when the work crosses repositories, split it:

- Each ticket ships something a user or another program can see.
- A ticket that needs another one done first names it under `after:`. The provider of an interface comes before its consumer, as `jt-work`'s `references/two-repos.md` says.
- Number the tickets in the order they can be worked, and say which ones can run at the same time.

## 6. Check

Save each draft in your session's temporary folder and run `jtek.py ticket <file>` from its repository (the script of `jt-work`). It reads the file the way `start` will. Fix every refusal.

## 7. Approve, then create

Show every draft in full, numbered, with what you found in the code under each. The owner answers per ticket: create it, change it, or drop it. Never create one the owner did not approve.

Create each approved ticket on the board with the board's tool, as `jt-work`'s `references/notion.md` or `references/flo.md` says where each field lives:

- **Status Backlog.** In FLO, the item stays off the board; in Notion, Status is `Backlog`. Never Todo.
- The title, the kind, the repo and area, and the three sections as the body.
- Each `after:` as the board's own link: After in Notion, `blocked by` in FLO.

**The repository has no board** (`board` is empty in `jtek.json`): run `jtek.py ticket <file> --save` for each approved draft, in the order they must be worked. The script gives the id, writes Backlog, and prints where the file is. A blank line in the draft does not drop `kind`, `area`, or `repo`. An id already used by a commit message or by `refs/remotes/*/jtek/<id>` is not given out again. Write an `after:` line with the id the script gave the earlier ticket before you save the later one. Tell the owner each file: they release a ticket by writing `status: Todo` in it.

Every agent you start for this work, to read code in parallel for example, gets as the first line of its prompt `Read <absolute path of jt-work>/worker.md before anything else.`

## The report

End with a table of the tickets created: number, id, title, link, and what each waits for. Then say which ones the owner can release first, by moving them to Todo.
