# Start a queue

1. Run `/jt-setup` and confirm the command table before anything is written.
2. Run `/jt-add-task` and approve the brief, then the tasks. An approved spec covers the tasks that come from it.
3. Run `/jt-work`. It claims one ready task, works in one worktree, and stops at `review:`.
4. You run `/jt-review` and merge. The agent does not.

A task with `blocked-by:` waits until those ids are `merge:` or `drop:`.
