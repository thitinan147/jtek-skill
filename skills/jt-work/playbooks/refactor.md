# Playbook: refactor

A refactor changes the shape of the code and nothing a caller can observe.

1. **Understand** with `jt-understand`. The proof is that every existing test still passes unchanged.
2. **Lock the behaviour.** Run the tests that cover the code. If a behaviour has no test, add one and see it pass on the old code before you move anything. Commit it. Passing type checks and lint do not lock behaviour.
3. **Build** with `jt-build`, in this order:
   - Remove before you add. Delete dead code and merge duplicate helpers first, in their own commit.
   - Move in small steps. The tests pass after each one. Commit each one.
   - Move every caller. Do not leave the old and the new way side by side. If you cannot move them all in this ticket, stop with `--waiting input`.
   - Before deleting a line that looks useless, read its history (`git log -S`, `git blame`). It may guard against something.
4. **Do not change behaviour.** If you find a bug, leave it and put it in the evidence as a new ticket. A test you had to change is a sign that behaviour changed.
5. **Check** with `jtek.py check <id>`. On a failure use `jt-debug`.
6. **See it work** with `jt-verify`. Compare the output with the base branch for the same input.
7. **Judge the result.** If the diff does not make the code easier to read somewhere, revert it and stop with `--waiting input`, saying why.
8. **Clean up** with `jt-cleanup`. If you removed anything, commit and check again.
9. **Ship** with `jt-ship`.
