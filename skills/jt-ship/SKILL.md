---
name: jt-ship
description: Pushes a ticket's branch, opens a pull request that shows how each acceptance item was seen working, and moves the ticket to Review without merging. Use when jt-work reaches the Ship step, or when the user asks to open the pull request for a finished ticket.
---

# jt-ship

Ship only after `jtek.py check <id>` passed on the current commit and you have seen the change work. This skill never merges.

Use the owner's language and style from `~/.jtek/me.md` for the evidence and the pull request, as [worker.md](../jt-work/worker.md) says. It changes no rule, and the prefixes the script reads (`seen:`, `not run:`, `clean-up:`, `choice:`) stay in English.

## 1. Write the evidence

Write it for a person who has not seen the session, in at most 40 lines, not counting blank ones. The script refuses a longer one. The human reviews the evidence first and the diff second:
   The form, with a filled example, is in [references/evidence.md](references/evidence.md).
   - What changed and why, in two or three sentences.
   - One line per `Done when` item, in the ticket's order, starting with its number and a status word: `1. seen: <command or steps> -> <what you saw> (run <n>)`, or `2. not run: <reason>`. The script refuses evidence that skips an item, or that has no `clean-up:` line from the Clean-up step. `not run` is an honest answer. `seen` for something you did not see is not.
   - Choices you made where the ticket was open, each as `choice: <question> → <picked> (other options: …)` with its principle id.
   - What you could not run, and anything the reviewer should look at first. If you changed a file that a check runs, CI config, a lockfile, or deleted a test, say so and say why.

## 2. Open the pull request, or not

Save the evidence to a file in your session's temporary folder, or anywhere outside the repository and its worktrees, then run `jtek.py evidence <id> --file <file>`. It checks the form and saves nothing, so a refused file never becomes a pull request body.

Add `--attach <file>` to `finish` for each screenshot, recording, or output file that shows the change working. A file attached again under the same name replaces the earlier one. Attached files stay on this machine. A reader of the pull request cannot open them, so the evidence itself must hold what that reader needs, and a file worth reading goes on the pull request as a comment.

- **An item can only be seen once the pull request exists,** such as its CI run: open it with the evidence you have, then make the full evidence its body before `finish`.
- **The ticket already has a pull request:** push the branch, make the new evidence its body again (on GitHub: `gh pr edit <url> --body-file <file>`; on GitLab: `glab mr update <id> --description "<evidence>"`), and pass the same link to `finish`.
- **The repository has a forge:** push the branch `jtek/<id>` and open a **draft** pull request into the branch `start` printed as `base:` (`gh pr create --draft` on GitHub, `glab mr create --draft` on GitLab). Title: `type(scope): summary`, or the form the repository's merged pull requests use, with the ticket id where they put it. When the merged titles carry no ticket id, or disagree, end yours with `(<ticket id>)`. The evidence file is the body. Then run `jtek.py finish <id> --pr <url> --evidence-file <file>`. The script reads the pull request with `gh` or `glab` (or the project's `pr_state` override) and checks that it is at your current commit. Right after a push it waits a moment for the forge to show the new commit. Never pass a link you did not get from the forge.
- **The repository has no forge:** do not push. Run `jtek.py finish <id> --no-pr --evidence-file <file>`. The human then reads the evidence and reviews the local branch `jtek/<id>`. The script refuses `--no-pr` when the repository has a remote, unless this machine's config for this repository has `"forge": false`. A commit cannot set that flag. A local `origin/HEAD`, a replace ref, and a rewritten origin do not count. If the sealed origin cannot be read, `--no-pr` is refused.

Pass `--evidence-file` again whenever the code changed since the last `finish`. The script refuses evidence that was saved for an older change.

## 3. Read the result

- **`outcome: review`:** stop. When the pull request was a draft and both a passing verdict and green CI hold, `finish` has marked it ready, and updated the ticket file's header to `status: Review` (with the PR link) when the ticket came from a file. The human reviews and merges.
- **`outcome: needs-review`:** the usual first result. The pull request stays a draft while a session that did not write the change records a verdict, and then `finish` runs again to mark it ready. When the ticket came from a file, `finish` records the pull request link in its header.
- **`refused: cannot read`:** `gh` or `glab` could not read the pull request, so nothing was sent for review. The message says what to fix, including the token scope or CLI login. An unknown state and an unknown CI result both refuse.
- **`refused: CI is still pending`**, or **`no checks have appeared`:** pending includes SKIPPED, NEUTRAL, and a mix of those with SUCCESS. An empty, null, or missing rollup is not `none`. `finish` waits `JTEK_CI_APPEAR_TRIES` looks (3) and `JTEK_CI_APPEAR_WAIT` seconds (2) for the first check, then refuses. It waits `JTEK_CI_TRIES` (40) and `JTEK_CI_WAIT` (15) while a check is still running. Only every required check at SUCCESS ships, or `none` when GitLab has no pipeline or the project's `pr_state` command says this repository has no checks.
- **`refused:` a broke proof:** for each `Done when` item, break that behaviour, run `jtek.py broke <id> --item <n>` while the edit is uncommitted, then restore the file. Every declared check runs. A lint, syntax, format, or import failure does not count: the behaviour check has to fail. Rewriting the Done when line invalidates the record. `finish` refuses until every item has a record on this commit.
- **`refused: verdict is FAIL`:** the change does not ship. Read the review notes the script names.
- **`refused: CI is failing`:** you may fix the cause once, commit, push, and run `finish` again. If CI is still red after that fix, run `jtek.py stop <id> --waiting input --note "<what fails in CI>"` and do not keep looping.
- **`refused: ... conflicts with`** the base: the pull request is not ready for the human. The refusal says what to do next.

## 4. End

End the session with the `jtek-result` block the script printed, unchanged.
