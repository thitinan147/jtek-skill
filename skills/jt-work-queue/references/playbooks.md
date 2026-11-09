# Playbooks for `do-task`

The gate checks evidence, not method. These are the habits that make the evidence true. Pick the part that fits the task's `<kind>`.

## Before you write any new code

Climb this ladder and stop at the first rung that solves it.

1. **Do we need it?** If the task passes without this code, do not write it.
2. **Is it already in the repo?** Search for a helper that does the same job and use it. Do not write a second one.
3. **Does the standard library or an installed package do it?** Use that. Do not write your own utility.
4. **Write the smallest thing that works.** Short and direct.

Never save effort on security, input validation at a trust boundary, or error handling. Those stay.

Subtract before you add: inside `files:`, delete dead code and merge duplicates before adding new code. Do not touch files outside `files:` to tidy them.

## By kind

- **fix**: Run the command that shows the bug and keep its failing output (`## repro`). Write a test that fails for the same reason. Fix the cause, not the symptom. The same test and command now pass. If two rounds fail, stop guessing: write down what the evidence says, form a new hypothesis from it, and only then change code.
- **feat**: Build the thinnest path through every layer the task touches first, prove it with `pass:`, then widen it. Test through the public interface, not private helpers.
- **refactor**: Pin current behavior with tests first (`## behavior lock`) and run them green before the first edit. Change structure only. Move every caller. Public behavior stays the same.
- **perf**: Measure first (`## baseline`). Change one thing. Measure again with the same command. A guess without a number is not a result.
- **test**: Assert behavior a caller can see. A test that breaks on a harmless refactor is a bad test.
- **build, ci, chore**: Run the changed pipeline step for real. A config that parses but never ran is not evidence.
- **revert**: Name the commit and why. Check nothing else depends on it.
- **docs, style**: Change nothing but docs or formatting. If a code change is needed, split it into its own task.
- **security** concerns inside any kind: follow the data from where it enters to where it is used, and name the guard on the way.

## Many tasks in a row

Long sessions forget early constraints. For each task, start from `gate.py next`, re-read `task.md`, `jt-queue/lessons.md`, and the template for `plan.md`, and do not rely on what you remember of the last task. When you can, run each task in a fresh agent session or subagent.

## Reading the diff before `review:`

Review the diff, not your memory of it. Compare the changed files with `files:`, check `out:` was not crossed, find who calls what changed, and ask why each deleted line was there (`git log -L`, `git blame`). Small diffs hide big failures. Remove stray comments, debug output, and boilerplate you added. Write down only what you confirmed.
