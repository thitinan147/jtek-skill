---
name: jt
description: Use when given a coding brief with an agreed plan — work on the work branch, verify for real, and report back in 5 lines. Does not plan on its own or open PRs/MRs; stops when blocked instead of asking mid-way.
---

# jt — Finish the coding task and report back

1. Restate the task: goal in 1 sentence + what done looks like + work on the work branch, not main (brief names none -> create one)
2. Read related code + check commands from AGENTS.md / README / Makefile (none found -> use the repo's test/lint and say so on the `Saw:` line)
   - If it's a bug, reproduce the failure first (can't reproduce -> stop)
   - If the brief's plan is unworkable -> stop
3. Make the smallest change, one topic only + test real behavior
4. Check for real:
   - First time only: commit work first, then git fetch origin + merge origin/main (not again on retry rounds; non-trivial conflict -> git merge --abort and stop)
   - Run all checks + see it for real locally/in dev (call the API / open the page / run the program and look at the output — "tests pass" alone does not count; if impossible -> put it on the `Not run:` line with the reason)
   - Red -> find cause -> back to step 3
   - 3 red rounds or same failure 2 rounds in a row -> stop
5. Read your own diff (git diff origin/main): on goal? inside the brief? real tests? — any "no" -> back to step 3 (counts as a red round)
6. Commit on the work branch and report

## Never

- Loosen tests or checks
- Change an existing test's expected values without the reason on the `Did:` line
- Touch .env / secrets / production data or systems
- Merge into main, push to main, force-push
- Open a PR/MR or deploy
- Change anything outside the brief (note it instead)

## Stop

On stop: if mid-merge, git merge --abort first (not a reset) -> commit any uncommitted work as WIP on the work branch (never delete or reset) -> send the 5-line report with the blocker on the `Blocked & out-of-brief:` line.

## Report

Write the report in the language of the brief (Thai brief -> Thai report, English brief -> English report). Keep the 5 labels in English exactly as below; commands, paths and output stay as-is. Use exactly these 5 lines, in order, one topic each (also when stopped):

- Goal: one sentence
- Did: files + commit (+ any existing test expectation changed, with reason)
- Saw: checks run + results + what you saw in the running program
- Not run: what, and why
- Blocked & out-of-brief: what blocked + out-of-brief items noted
