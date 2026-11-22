---
name: jt-cleanup
description: Removes leftover debug output, unused code, and comments that repeat the code from a change before it ships, without touching anything outside the change. Use when jt-work reaches the Clean-up step, or when the user asks to tidy a diff before a pull request.
---

# jt-cleanup

Read your own diff once as a stranger would: `git diff <base>...HEAD`, where the base is the branch `jtek.py start` printed. Work only on lines the diff added or changed.

## Remove

- Debug prints, temporary logging, and commented-out code.
- Code the change added and nothing uses.
- Comments that say what the next line does.
- A "do not remove" or "must stay in sync" comment. Turn the claim into a type, a test, or a lint rule, then delete the comment. If you cannot, keep it and say so in the evidence.
- A helper used once that hides nothing. Inline it.
- A wrapper, option, or setting added "for later". Nothing in `Done when` asks for it.
- Files the change created and does not need: scratch scripts, logs, screenshots.

## Keep

- These comments: licence headers, documentation of a public API, links to an issue, and a constraint forced by something outside the code.
- Security checks, input validation, and error handling.
- Tests. Never delete or loosen a test here.
- Everything outside the diff. Do not tidy code the ticket did not touch.

## Then

If you removed anything, commit and run `jtek.py check <id>` again. Then add one line under Notes in the evidence: `- clean-up: <what you removed or changed>`, or `- clean-up: nothing to remove`. `finish` refuses evidence without it.
