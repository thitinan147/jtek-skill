---
name: jt-debug
description: Finds the cause of a failing check, test, or bug before any code changes, and stops after three failed attempts. Use when jtek.py check fails, when a test or build fails during a ticket, or when the user asks to debug an error or unexpected behaviour.
---

# jt-debug

Do not change code until you can say what the cause is.

The base branch is the one `jtek.py start` printed as `base:`.

When you start from a bug you reproduced, and no check has failed, your reproduction is the failure. Skip to step 2, and compare with a nearby case that works.

## 1. Read the failure

1. Read the whole log, not only the last line. `jtek.py check` prints the log path.
2. Write down the first error. Later errors are often caused by it.
3. Run the failing command yourself and confirm you see the same failure.

## 2. Find the cause

1. If it worked before your change, ask what changed: `git diff <base>...HEAD`. If the bug is already on the base branch, skip this.
2. Find a nearby case that works, and list what differs from the failing one.
3. Follow the wrong value back to where it first becomes wrong.
4. When the first error does not name the cause, list two or three candidate causes and the one observation that tells them apart, and make the cheapest one that rules out the most. Then state one cause as a sentence that could be shown false: "X fails because Y" (P8).

## 3. Test the cause

1. Make one small change or add one print that would prove the sentence wrong. A test written for that cause, failing with the error the sentence names, is such a proof.
2. If it is wrong, go back to step 2, and revert what that guess added. Do not stack a second guess on top of the first.
3. After two failed fixes that share an assumption, test the assumption itself. It is probably what is wrong. (P8)

## 4. Fix

1. Fix the cause, not the place where the symptom shows. Before you add a guard, a retry, a default, or a caught error where the symptom shows, ask whether the state that reached it should exist; if not, the guard hides the bug (P9).
2. Never weaken a check, skip or delete a test, loosen an assertion, or edit `jtek.json` to get a pass. The script reads checks from the base branch, so that would not work.
3. Remove the prints you added. Commit, and run `jtek.py check <id>` again.

## 5. Stop at three

After three failed `check` runs the script tells you to stop. The project may set another number. One more guess usually means the design is wrong, not the line. Run `jtek.py stop <id> --waiting input --note "<the cause you suspect and what you tried>"`.

A declared check that fails on the base branch too, for a reason outside your ticket, is not yours to fix here. Stop: `jtek.py stop <id> --waiting input --note "<check> fails on the base too"`.
