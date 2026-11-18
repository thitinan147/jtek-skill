---
name: jt-ship
description: Pushes a ticket's branch, opens a pull request that shows how each acceptance item was seen working, and moves the ticket to Review without merging. Use when jt-work reaches the Ship step, or when the user asks to open the pull request for a finished ticket.
---

# jt-ship

Ship only after `jtek.py check <id>` passed on the current commit and you have seen the change work. This skill never merges.

## 1. Write the evidence

Write it for a person who has not seen the session, in at most 40 lines, not counting blank ones. The script refuses a longer one. The human reviews the evidence first and the diff second:
   - What changed and why, in two or three sentences.
   - One line per `Done when` item, in the ticket's order, starting with its number and a status word: `1. seen: <command or steps> -> <what you saw>`, or `2. not run: <reason>`. The script refuses evidence that skips an item. `not run` is an honest answer. `seen` for something you did not see is not.
   - Choices you made where the ticket was open.
   - What you could not run, and anything the reviewer should look at first. If you changed a file that a check runs, CI config, a lockfile, or deleted a test, say so and say why.

## 2. Open the pull request, or not

Save the evidence to a temporary file outside the worktree. Add `--attach <file>` for each screenshot, recording, or output file that shows the change working.

- **The repository has a forge:** push the branch `jtek/<id>` and open a pull request that is ready for review, not a draft. Title: `type(scope): summary`. The evidence file is the body. Then run `jtek.py finish <id> --pr <url> --evidence-file <file>`. When `gh` is installed, the script checks that the pull request is open at your current commit. Never pass a link you did not get from the forge.
- **The repository has no forge:** do not push. Run `jtek.py finish <id> --no-pr --evidence-file <file>`.

## 3. Read the result

- **`outcome: review`:** stop. The human reviews and merges. If the ticket came from Notion, set its status to Review there and add the result as a comment.
- **`outcome: needs-review`:** the usual first result. A session that did not write the change records a verdict, and then `finish` runs again.
- **`refused: verdict is FAIL`:** the change does not ship. Read the review notes the script names.
- **`refused: CI is failing`:** the pull request is not ready for the human while its checks are red.

## 4. End

End the session with the `jtek-result` block the script printed, unchanged.
