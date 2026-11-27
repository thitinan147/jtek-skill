# Playbook: feature

1. **Understand** with `jt-understand`. Exit: you can say what will change, which existing pattern you follow, and how each `Done when` item (or the goal) will be seen working.
2. **Build** with `jt-build`. Exit: the change is committed and each new behaviour has a test.
3. **Check** with `jtek.py check <id>`. On a failure use `jt-debug`. Exit: every check passes on the current commit.
4. **See it work** with `jt-verify`. Exit: you saw each `Done when` item (or the goal) work, or the evidence says which you could not run.
5. **Clean up** with `jt-cleanup`. If you removed anything, commit and check again.
6. **Ship** with `jt-ship`. Exit: the script printed a `jtek-result` block.
