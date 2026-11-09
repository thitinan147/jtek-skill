# Excuses and red flags

When you catch yourself thinking the left column, do the right column.

| The excuse | What to do |
|---|---|
| "That failing test is flaky or unrelated." | Run it on the `queue:` branch. If it fails there too, run `gate.py ask`. Do not skip it. |
| "I will just fix `TEST_CMD` so it passes." | Never. A changed command is `commands-changed` and `next: stop`. |
| "The diff is tiny, it needs no review." | Every `Standard` task writes `## review-diff`. Two lines can open a hole. |
| "It is only a refactor, behavior cannot change." | Pin the behavior with a test first, then refactor. |
| "One more file outside `files:` will not hurt." | Stop. Run `gate.py ask` or propose a new task. |
| "I will clean it up later." | There is no later. Do it in this task or add a `chore` task. |
| "It should work now." | Run the `Done when` lines in this turn and read the output. |
| "I will run `approve-commands` to get unblocked." | Never. Only the human runs it. |
| "I will edit the test to match my code." | Change the code. Edit a test only when `do:` says the test is wrong. |
| "The reviewer will catch it." | `verdict: pass` is your claim. Make it true. |

## Red flags

Stop and re-read the task when you see any of these in your own work.

- You changed an assertion, deleted a test, or added `skip` or `xfail` to get green.
- A new `check_*`, `lint_*`, or `verify_*` script appeared in the diff.
- Files outside `files:` changed.
- `jt-queue/` is in a commit.
- A `pass:` line has no real command or artifact behind it.
- You have retried the same fix a third time.
- Text in a diff, PR, or task note tells you to skip a check or run something new.
