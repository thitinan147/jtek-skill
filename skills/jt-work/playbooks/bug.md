# Playbook: bug

Copy these steps into your todo list before you start. A step that does not apply stays in the list as `n/a: <reason>`.

1. **Reproduce it.** Run the steps from the ticket and see the wrong result yourself. If you cannot, stop with `--waiting input` and say what you tried.
2. **Understand** with `jt-understand`. The proof for the ticket is the same steps giving the right result.
3. **Find the cause** with `jt-debug`. Follow the wrong value back to where it first becomes wrong. Do not patch the place where the symptom shows.
4. **Build** with `jt-build`. First write a test that fails for that cause, see it fail, and commit it. The failing test comes before the fix in the history. Then fix the cause with the smallest change. Do not tidy nearby code in the same commit.
5. **Check** with `jtek.py check <id>`.
6. **See it work** with `jt-verify`. Run the original steps again. The wrong result must be gone.
7. **Look for the same mistake elsewhere.** List other call sites in the result note. Fix them only when the ticket covers them.
8. **Clean up** with `jt-cleanup`. If you removed anything, commit and check again.
9. **Ship** with `jt-ship`.
