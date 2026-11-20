---
name: jt-verify
description: Runs the changed feature the way a user would and looks at the real result, so that passing checks are not mistaken for working software. Use when jt-work reaches the See-it-work step, or when the user asks to confirm that a change actually works in the running app, API, or command-line tool.
---

# jt-verify

Passing checks do not replace this step. Do it after `jtek.py check` passes.

## 1. Run the real thing

If the repository has `.jtek/verify.md`, follow it to launch and drive the app, and read the file in `.jtek/features/` for the feature you changed. If it has none, do not stop and do not build one: use the list below, and say in the evidence that the repository has no verify guide.

For each `Done when` item, do what you named before you built it:

- **Command-line tool or library:** run it on real input, including the exact example in the ticket.
- **API:** start the service and call the endpoint. Read the response body and the status.
- **Screen:** open it in a browser and do the steps. Read the console and the failed network requests.

## 2. Look at the result

1. Compare what you see with the `Done when` item, word for word.
2. Try the edges the ticket implies: empty input, very long input, the same action twice, the wrong order.
3. For a screen, look at each state: empty, loading, error, and text that is too long.
4. Check that behaviour under `Out of scope` is the same as on the base branch. To run the base, use the main checkout when it is on the base branch, and change nothing there. Otherwise add a worktree of the base in a temporary folder, and remove it afterwards.
5. For a change to a database schema or to a response other code reads: apply the migration, undo it, and apply it again. Then run the base branch's code against the new schema or response. When the code that reads it is in another repository, do not go and change it: write in the evidence that it was not run, and which repository it is.

## 3. What does not count

- The code compiles, or the checks pass.
- A file exists or changed.
- Output you saved earlier, before the last commit.
- Your own summary of what the code does.
- A different path than the one the ticket names. A skipped entry point is not verified through another one.
- An unclear result. Inconclusive is not a pass. Say it is inconclusive.

Use the real user path, not an internal function or a test-only endpoint. Capture the action and the state it produced, not only the last screen. When the change writes data, look at the stored value a second way.

## 4. Say only what you saw

- Write down the command or steps and the result for each item. Keep the screenshot, recording, or output file that shows it, in a folder outside the worktree. This is the evidence. It goes into the pull request, or into the evidence file when there is no pull request.
- Never write "should work" or "probably fixed". Either you saw it, or you did not.
- If you could not run it, say that in the evidence, and say why.

## 5. When it does not work

The change is not done. Find the cause, fix it, commit, and run `jtek.py check <id>` again. Then repeat this skill.

If the project has no way to run the real thing, say so in the evidence and say that the repository needs a verification harness.

If you found a new way to drive a feature, or a gotcha, add it to that feature's file in `.jtek/features/` in the same change. The result will name the file on its `attention:` line. That line asks the human to look. It does not forbid the edit.
