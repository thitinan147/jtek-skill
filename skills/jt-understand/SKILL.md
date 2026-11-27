---
name: jt-understand
description: Reads a ticket and the code it touches before any edit, and names how each acceptance item will be seen working for real. Use when jt-work reaches the Understand step, or when the user asks what a ticket needs or how a change should be verified before coding starts.
---

# jt-understand

Do this before the first edit. The output is a short list, not a document. Write it as text in the session, where the human can see it. A plan, if you want one, stays outside the repository and its worktrees.

## 1. Read

1. Read the ticket file whose path `jtek.py start` printed. Note `Goal`, each `Done when` item, `Out of scope`, and `kind` when it is set.
2. Read the code the ticket touches, the tests beside it, and one caller of each function you expect to change.
3. If a question can be answered by reading the code or its history, or by running it, read or run. Do not ask the human. (P19)
4. Search the history and the open pull requests for the same fix: `git log --all --grep <the symptom or the ticket id>`, and `gh pr list --search` on a forge. An open fix or a commit that already claims it: do not write a competing one; stop with `--waiting input` and name it. A fix that was reverted: read why before you plan.

## 2. Find the pattern

1. Find how this codebase already solves the same kind of problem, and plan to follow it.
2. If the nearest example is a workaround, do not copy it. Note it for the evidence. (P3)
3. Look for a function, a helper, or an installed package that already does what you need. Plan to use it.
4. If the codebase has no precedent for this kind of change, sketch two different shapes in a few lines each, and choose one. Say in the evidence which you chose and why.

## 3. Name the proof

For each `Done when` item, write one line: how you will see it work for real. A declared check counts. So does running the feature and looking at the output. "The code looks right" does not count.

An item that asks for a quality with no number or named standard ("fast", "secure", "accessible") cannot be seen working either.

If an item has no way to be seen working, do not stop. Propose a measurable reading of it, such as a number or a named standard, write it for the evidence as `choice: <question> → <picked> (other options: …) (P19)`, and go on. When no reading makes it measurable, draft a new card that names the gap (with a board, write a checked draft ticket file outside the repository and worktree and name its path on that item's `not run:` line for the outer loop — never touch the board yourself; with no board, save it with `jtek.py ticket <file> --save`), and go on with the items that can be seen.

## 4. Settle what the ticket leaves open

- **Small and easy to change later:** choose the reading that changes less of what users see today, even when it takes more code. (P17) Write the choice down for the evidence.
- **Costly to undo, it changes what the ticket is for, or two `Done when` items cannot both hold:** do not stop, and do not pick silently. Follow the reading that still makes a coherent ticket and changes less of what users see, and write it as a `choice:` line (P19). When the conflict is real, draft a new card for the reading you did not take (with a board, write a draft ticket file for the outer loop and name its path in the evidence; with no board, save it with `jtek.py ticket <file> --save`), and go on.
- **The human's answer has an effect it says it does not want:** do what it asks for in so many words, and put the effect under `Notes` in the evidence for the human to weigh.
- **The base already does what an item asks:** see it for real, and say so in the evidence. Build only what the ticket still asks for. When nothing is left to build, stop with `--waiting input` and say what you saw.

## Done when

You can say, in a few lines: what will change, which existing pattern you follow, and how each `Done when` item will be seen working.
