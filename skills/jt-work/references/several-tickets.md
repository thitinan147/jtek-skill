# Several tickets in one session

A fresh session per ticket is the safe default: nothing from one ticket leaks into the next. But a session that just read a module has paid for that reading, and a second small ticket in the same module can use it. Take more than one ticket in a session only when that is true.

## When the human or the launcher gives several ids

Work them one at a time, in the order given. This skill still never picks a ticket: it only works ids it was given.

## Before each further ticket, check all four

Go on in this session only if every line holds. Otherwise end the session.

1. **The last ticket ended cleanly.** Its result is `review` or `needs-review`, and it did not take more than one failed `check` run. A ticket that fought you leaves wrong assumptions behind.
2. **The next ticket is in the code you already read.** It has the same `area:` as the last one. When `area:` is not set, judge by module, feature, or kind of change. If you would have to read a different part of the codebase, a fresh session reads it just as fast and carries nothing over.
3. **The session is still short.** You have not had your earlier context summarised or dropped, and you are not re-reading files you read before because you forgot them.
4. **The next ticket does not wait on this one.** If it has `after:` with a ticket that is not Done, `start` refuses it. Do not work around that.

## For each ticket, start over

- Run `jtek.py start <id>`, pick its playbook, and write a new todo list. Do not reuse the last one.
- Its worktree is cut from the base branch. **The last ticket's changes are not in it.** Do not assume a helper, a fix, or a rename from the last ticket exists here.
- Read its ticket file in full, and name the proof for each of its `Done when` items again. You may skip re-reading code you read this session, but re-check anything the ticket depends on.
- It gets its own evidence, its own pull request, and its own result. Never put two tickets in one branch or one pull request.
- Never keep two tickets open. Reach `finish` or `stop` on one before you `start` the next.

## Reviewing

A session never gives the verdict on a ticket it wrote, however many tickets it worked. Every one of them needs a different session for `jt-review`.

## For whoever starts the sessions

Grouping is decided before a session starts, by the human or the launcher. The four checks above are only the session's brake.

- **Put together:** up to three small tickets with the same `area:` that do not depend on each other.
- **Give its own session:** a ticket in another area, a large ticket, a `refactor`, a bug you expect to be hard, and any ticket with `after:`.
- **Run in parallel sessions instead:** tickets you want done sooner. One session works one ticket at a time.
- `jtek.py list` shows each Todo ticket's `area`, `kind`, and `after`.

## How the session ends

Print the `jtek-result` block of every ticket you worked, in order. Then, when ids are left, one more line:

```
not started: T-4, T-5 (reason: <which of the four checks failed>)
```

The human or the launcher starts a fresh session for those.
