---
name: jt-ship
description: Pushes a ticket's branch, opens a pull request that shows how each acceptance item was seen working, and moves the ticket to Review without merging. Use when jt-work reaches the Ship step, or when the user asks to open the pull request for a finished ticket.
---

# jt-ship

Ship only after `jtek.py check <id>` passed on the current commit and you have seen the change work. This skill never merges.

## 1. Write the evidence

Write it for a person who has not seen the session, in under 40 lines. The human reviews the evidence first and the diff second:
   - What changed and why, in two or three sentences.
   - Each `Done when` item, with the command or steps you ran and what you saw. Attach the screenshot or output when there is one.
   - Choices you made where the ticket was open.
   - What you could not run, and anything the reviewer should look at first. If you changed a file that a check runs, CI config, a lockfile, or deleted a test, say so and say why.

## 2. Open the pull request, or not

- **The repository has a forge:** push the branch `jtek/<id>` and open a pull request that is ready for review, not a draft. Title: `type(scope): summary`. The evidence is the body. Then run `jtek.py finish <id> --pr <url>`. When `gh` is installed, the script checks that the pull request is open at your current commit. Never pass a link you did not get from the forge.
- **The repository has no forge:** do not push. Save the evidence to a temporary file and run `jtek.py finish <id> --no-pr --evidence-file <file>`.

## 3. Read the result

- **`outcome: review`:** stop. The human reviews and merges. If the ticket came from Notion, set its status to Review there and add the result as a comment.
- **`outcome: needs-review`:** the ticket asks for a second look from a session that did not write the change. That session records a verdict, and then `finish` runs again.
- **`refused: verdict is FAIL`:** the change does not ship. Read the review notes the script names.

## 4. End

End the session with the `jtek-result` block the script printed, unchanged.
