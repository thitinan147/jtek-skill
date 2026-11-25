---
name: jt-verify
description: Runs the changed feature the way a user would and looks at the real result, so that passing checks are not mistaken for working software. Use when jt-work reaches the See-it-work step, or when the user asks to confirm that a change actually works in the running app, API, or command-line tool.
---

# jt-verify

Passing checks do not replace this step. Do it after `jtek.py check` passes.

Run each command through `jtek.py run <id> -- <command>`, or `jtek.py run <id> --sh "<pipeline>"` for a pipe, with `--cwd <folder>` to run somewhere else, such as the base. It records exactly what ran, where, at which commit, the exit code, and what came back, and prints a run number. Let it record the exit code: do not end the line with `; echo $?`, which makes the run's own exit code 0, and remember that a pipe's exit code is its last command's. To run the base, give `--cwd` the main checkout, so the run names the commit it ran at. A screen you drive by hand cannot be recorded this way: attach a screenshot instead. A service that keeps running is not started through `run`, which waits for it to end: start it as the verify guide says, or in a session of its own, and record the calls you make to it.

## 1. Run the real thing

If the repository names a slower way to check the change that is not a declared check, such as a script its README describes, run it when it covers what you changed, and say so in the evidence. The verify guide is `verify.md` in `~/.jtek/repos/<repo id>/` (the same id `jtek.py init` prints: host, non-default port, and path of the origin, or the checkout path when there is no origin). Follow it, and read `features/<name>.md` beside it for the feature you changed. When that folder is missing, do not stop and do not build one: read the README and the code, use the list below, and say in the evidence that no verify guide was found.

For each `Done when` item, do what you named before you built it:

- **Command-line tool or library:** run it on real input, including the exact example in the ticket.
- **API:** start the service and call the endpoint. Read the response body and the status.
- **Screen:** open it in a browser and do the steps. Read the console and the failed network requests.

## 2. Look at the result

1. Compare what you see with the `Done when` item, word for word.
2. Try the edges the ticket implies: empty input, very long input, the same action twice, the wrong order. (P6, P12)
3. For a screen, look at each state: empty, loading, error, and text that is too long.
4. Check that behaviour under `Out of scope` is the same as on the base branch. In the bug playbook, your reproduction before any edit is the base run. Otherwise, to run the base, use the main checkout when it is on the base branch, and change nothing there, not even a cache: run it so that it writes none, such as `python3 -B`. Otherwise add a worktree of the base in a temporary folder, and remove it afterwards.
5. For a change to a database schema or to a response other code reads: apply the migration to a database of this worktree, never a shared one (P16), undo it, and apply it again. Then run the base branch's code against the new schema or response. When the code that reads it is in another repository, do not go and change it: write in the evidence that it was not run, and which repository it is.

## 3. What does not count

- The code compiles, or the checks pass.
- A file exists or changed.
- Output you saved earlier, before the last commit. One exception: when the commits since then changed only test files or documents that no program reads (a script that a check runs is not one), the earlier run still stands, and the evidence says which commit it is from. After a rebase that brought changes to files your change touches, run every line again.
- Your own summary of what the code does.
- A different path than the one the ticket names. A skipped entry point is not verified through another one.
- An unclear result. Inconclusive is not a pass. Say it is inconclusive.
- A result that came too easily: no output, no time taken, every case right on the first try. First check that the run reached the code you changed (P15).
- A number (a time, a size, a count) from one run. Give it from several recorded runs, with how many and how far apart they were, and rule out that it counted cached, skipped, or failed work (P13).

Use the real user path, not an internal function or a test-only endpoint. Capture the action and the state it produced, not only the last screen. When the change writes data, look at the stored value a second way.

## 4. Clean up after yourself

Remove only what you made, by the exact path you created, and stop only a process you started, by its id. Never delete by a pattern, and never in a folder other sessions share: several sessions work on one machine at the same time.

## 5. Say only what you saw

- Never edit a saved output. When one is wrong or incomplete, run it again, or say in the evidence what it lacks.

- End each `seen:` line with the runs it rests on, as `(run 3)` or `(runs 3 and 4)`. `finish` refuses a number that was never recorded. The run file holds the exact command, so the line may name it briefly; what the line says came back must be what the run shows. Make the input files with a recorded run too, or show them with one, so the run says what went in. Keep inputs and drafts in your session's temporary folder, not in the repository or beside its worktrees.
- Write down the command or steps and the result for each item. Keep the screenshot, recording, or output file that shows it, in a folder outside the worktree. This is the evidence. It goes into the pull request, or into the evidence file when there is no pull request.
- Never write "should work" or "probably fixed". Either you saw it, or you did not.
- If you could not run it, say that in the evidence, and say why.

## 6. When it does not work

First rule out the way you looked: a stale build or cache, the wrong worktree, port, or commit, an earlier run (P15). Then the change is not done. Find the cause, fix it, commit, and run `jtek.py check <id>` again. Then repeat this skill.

If the project has no way to run the real thing, say so in the evidence and say that the repository needs a verification harness.

If you found a new way to drive a feature, or a gotcha, add it to that feature's file in `~/.jtek/repos/<repo id>/features/`. That edit is not in the pull request. Say in the evidence which file you changed.
