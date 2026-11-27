---
name: jt-learn
description: Turns a correction from the human into something that runs (a lint rule, a fix to the code that taught the wrong pattern, or a new check) instead of a written reminder. Use when the user corrects the agent's work, sends a ticket back from review, or says a mistake keeps happening.
---

# jt-learn

A correction that stays in the chat is lost when the session ends. Make it a mechanism.

## 1. Name the mistake

Write one sentence: what was done, and what should have been done. Use the human's words. If you are not sure you understood, ask once.

A mistake that happened once is fixed in the ticket and noted. It becomes a mechanism when it has happened twice. Look in the commit history, reverts, and review comments for the first time.

## 2. Find why it happened

- **The code taught it:** an older file does the same wrong thing, and you copied it.
- **Nothing stopped it:** no type, lint rule, or test fails when it happens.
- **It could not be seen:** no check runs the real thing where the mistake shows.
- **The ticket did not say:** the rule exists only in the human's head.

## 3. Propose the strongest fix that fits

Assume the next contributor is an agent that sees only the files it opened, copies the nearest example, and takes the shortest path that compiles. A mistake that has happened twice is not another written reminder. Try these in order, and propose the first one that works:

1. **Architecture:** change the shape so the wrong call cannot be written. Hide the internal, or split the module so the bad import does not exist.
2. **A type:** change the type or the function's shape so the wrong value does not compile.
3. **A lint rule:** when the mistake has a pattern a tool can match. Its error message names what to use instead.
4. **A test or a check:** when the mistake only shows at run time. Add it to the project, and to `~/.jtek/repos/<repo id>/jtek.json` if it is a new command.

Fix the old examples in the same change when the code taught the mistake: list the files that still have the wrong pattern, and delete the old way so nothing is left to copy.

Record it with `jtek.py lesson --mistake "<what was done, and what should have been done>" --enforced-by "<the rule>"`. The first record may say `prose`. The same mistake again is refused until `--enforced-by` is `architecture: <target>`, `type: <target>`, a lint rule whose text says what to use instead, or `test: <path>` to a test file that exists. Do not write a prose row for that second time. If a structural fix exists, use only that. Do not add a written rule beside it.

A new lint rule, check, or test must fail on the real past mistake. Run it against that commit or that code and see it fail before you propose it. The commit is the one where the mistake reached the base branch. Build the trial in a copy outside the repository, such as one made with `git archive`, never in the checkout.

## 4. Hand it over

1. Fix the ticket's own work first, in its worktree. When that work is already merged, the fix goes into the new ticket below.
2. Describe the mechanism as a new ticket: what to add, where, and how to see it catch the mistake. Do not build it inside the current ticket unless the human says so. Write the ticket out in your report, in the ticket format. Save it as a local ticket file (`jtek.py ticket <file> --save`, as Backlog) only when the human asks. A repair the mechanism needs before it can pass belongs in the same ticket. Save a working trial as a patch file, and say where it is and that the folder may be temporary.
3. A change to lint config or CI is the human's to commit on the base branch. A change to the machine config is the human's to edit on this machine.

## 5. Keep the rule table small

The row for `~/.jtek/repos/<repo id>/rules.md` (the rule, what enforces it, and the date) goes into the new ticket's `Done when`, so it lands with its enforcer. Do not add it in this change. Propose the file as text in your report when it is missing. Its form is in [references/rules-template.md](references/rules-template.md).

- A rule with no enforcer is marked `prose` only the first time that mistake is recorded. `jtek.py lesson` refuses prose for a repeat.
- Drop a rule once its mistake cannot happen any more.
- An exception to a rule needs a reason, an end date, and the human's approval.
