# Playbook: bug

1. **Understand** with `jt-understand`. The proof for the ticket is the reproduction below giving the right result.
2. **Reproduce it.** Run the steps from the ticket and see the wrong result yourself. When you must break the code to show the fault, edit it in the worktree and restore it with `git checkout -- <file>`; keep no copy. If you cannot, stop with `--waiting input` and say what you tried.
3. **Find the cause** with `jt-debug`. Your reproduction is the failure it starts from.
4. **Build** with `jt-build`. In this playbook the test comes first: write a test that fails for that cause, see it fail by running the test yourself, and commit it before the fix. When the fault is in a check's own script, that check failing on the old code is the failing test. A test for a `Done when` item that already holds on the base is a pin: commit it with the failing test, see it fail once by breaking the fix after the fix is in, and say in the evidence that it is a pin. Do not run `jtek.py check` on that commit: it is red on purpose, and it would count as a failed run. Then fix the cause with the smallest change. Do not tidy nearby code in the same commit.
5. **Check** with `jtek.py check <id>`.
6. **See it work** with `jt-verify`. Run the original steps again. The wrong result must be gone.
7. **Look for the same mistake elsewhere.** List other call sites in the evidence. Fix them only when the ticket covers them.
8. **Clean up** with `jt-cleanup`. If you removed anything, commit and check again.
9. **Ship** with `jt-ship`.
