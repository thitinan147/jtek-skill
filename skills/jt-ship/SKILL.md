---
name: jt-ship
description: Pushes a ticket's branch, opens a pull request that shows how each acceptance item was seen working, and moves the ticket to Review without merging. Use when jt-work reaches the Ship step, or when the user asks to open the pull request for a finished ticket.
---

# jt-ship

Ship only after `jtek.py check <id>` passed on the current commit and you have seen the change work. This skill never merges.

## 1. Write the evidence

Write it for a person who has not seen the session, in at most 40 lines, not counting blank ones. The script refuses a longer one. The human reviews the evidence first and the diff second:
   The form, with a filled example, is in [references/evidence.md](references/evidence.md).
   - What changed and why, in two or three sentences.
   - One line per `Done when` item, in the ticket's order, starting with its number and a status word: `1. seen: <command or steps> -> <what you saw>`, or `2. not run: <reason>`. The script refuses evidence that skips an item. `not run` is an honest answer. `seen` for something you did not see is not.
   - Choices you made where the ticket was open.
   - What you could not run, and anything the reviewer should look at first. If you changed a file that a check runs, CI config, a lockfile, or deleted a test, say so and say why.

## 2. Open the pull request, or not

Save the evidence to a file outside the worktree, then run `jtek.py evidence <id> --file <file>`. It checks the form and saves nothing, so a refused file never becomes a pull request body.

Add `--attach <file>` to `finish` for each screenshot, recording, or output file that shows the change working. A file attached again under the same name replaces the earlier one. Attached files stay on this machine. A reader of the pull request cannot open them, so the evidence itself must hold what that reader needs, and a file worth reading goes on the pull request as a comment.

- **The repository has a forge:** push the branch `jtek/<id>` and open a pull request that is ready for review, not a draft. Title: `type(scope): summary`, or the form the repository's merged pull requests use, with the ticket id where they put it. The evidence file is the body. Then run `jtek.py finish <id> --pr <url> --evidence-file <file>`. The script reads the pull request with `gh`, or with the project's `pr_state` command, and checks that it is open at your current commit. Right after a push it waits a moment for the forge to show the new commit. Never pass a link you did not get from the forge.
- **The repository has no forge:** do not push. Run `jtek.py finish <id> --no-pr --evidence-file <file>`. The human then reads the evidence and reviews the local branch `jtek/<id>`. The script refuses `--no-pr` when the repository has a remote, unless `jtek.json` says `"forge": false`.

Pass `--evidence-file` again whenever the code changed since the last `finish`. The script refuses evidence that was saved for an older change.

## 3. Read the result

- **`outcome: review`:** stop. The human reviews and merges. Write on the ticket's page exactly what the `board:` line of the result says.
- **`outcome: needs-review`:** the usual first result. A session that did not write the change records a verdict, and then `finish` runs again. When the `board:` line holds the pull request's link, write it on the page.
- **`ci: pending`:** nothing to do. The next `finish` reads the forge again.
- **`refused: verdict is FAIL`:** the change does not ship. Read the review notes the script names.
- **`refused: CI is failing`:** the pull request is not ready for the human while its checks are red.

## 4. End

End the session with the `jtek-result` block the script printed, unchanged.
