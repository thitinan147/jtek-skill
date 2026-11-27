# Playbook: refactor

A refactor changes the shape of the code and nothing a caller can observe.

1. **Understand** with `jt-understand`. The proof is that every existing test still passes unchanged.
2. **Lock the behaviour.** Run the tests that cover the code. If a behaviour has no test, add one and see it pass on the old code before you move anything. Commit it. Passing type checks and lint do not lock behaviour.
3. **Build** with `jt-build`, in this order:
   - Remove before you add. Delete dead code and merge duplicate helpers first, in their own commit.
   - Move in small steps. The tests pass after each one. Commit each one.
   - Move every caller. Do not leave the old and the new way side by side. If you cannot move them all in this ticket, move what fits and draft a new card for the rest (with a board, write a draft ticket file outside the repository and worktree and name its path in the evidence for the outer loop — never touch the board yourself; with no board, save it with `jtek.py ticket <file> --save`), or write a `choice:` line that says which callers stay and why. Do not stop and wait.
   - Before deleting a line that looks useless, read its history (`git log -S`, `git blame`). It may guard against something.
4. **Do not change behaviour.** If you find a bug, leave it and put it in the evidence as a new ticket (a draft ticket file for the outer loop, or `jtek.py ticket --save` with no board). A test you had to change is a sign that behaviour changed.
5. **Check** with `jtek.py check <id>`. On a failure use `jt-debug`.
6. **See it work** with `jt-verify`. Compare the output with the base branch for the same input.
7. **Judge the result.** If the diff does not make the code easier to read somewhere, revert it, write why in the evidence (a `choice:` line or a note), and go on. Do not wait for input. When nothing of the ticket is left, say so in the evidence, and ship that or draft a new card for the outer loop (or `jtek.py ticket --save` with no board).
8. **Clean up** with `jt-cleanup`. If you removed anything, commit and check again.
9. **Ship** with `jt-ship`.
