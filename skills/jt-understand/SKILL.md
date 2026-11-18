---
name: jt-understand
description: Reads a ticket and the code it touches before any edit, and names how each acceptance item will be seen working for real. Use when jt-work reaches the Understand step, or when the user asks what a ticket needs or how a change should be verified before coding starts.
---

# jt-understand

Do this before the first edit. The output is a short list, not a document. Keep it in the session. Do not write a plan file.

## 1. Read

1. Read the ticket file whose path `jtek.py start` printed. Note `Goal`, each `Done when` item, `Out of scope`, and `kind` when it is set.
2. Read the code the ticket touches, the tests beside it, and one caller of each function you expect to change.
3. If a question can be answered by reading the code or its history, read. Do not ask the human.

## 2. Find the pattern

1. Find how this codebase already solves the same kind of problem, and plan to follow it.
2. If the nearest example is a workaround, do not copy it. Note it for the evidence.
3. Look for a function, a helper, or an installed package that already does what you need. Plan to use it.

## 3. Name the proof

For each `Done when` item, write one line: how you will see it work for real. A declared check counts. So does running the feature and looking at the output. "The code looks right" does not count.

If an item has no way to be seen working, stop: `jtek.py stop <id> --waiting input --note "<which item cannot be verified>"`.

## 4. Settle what the ticket leaves open

- **Small and easy to change later:** choose the reading that changes less. Write the choice down for the evidence.
- **Costly to undo, or it changes what the ticket is for:** stop with `--waiting input` and ask one question.

## Done when

You can say, in a few lines: what will change, which existing pattern you follow, and how each `Done when` item will be seen working.
