# Tickets, statuses, and the result

## Ticket format

The same format is used for a local file and for text fetched from Notion or another system.

```markdown
# Short title
id: T-12
status: Todo
kind: feature
area: billing
checks: lint, test
after: T-10

## Goal
What should be true when this is done, and why.

## Done when
- One observable outcome per line.

## Out of scope
- What this ticket must not change.
```

- **`id`:** letters, digits, `.`, `_`, `-`. It names the branch `jtek/<id>` and the worktree.
- **`checks`:** optional. Names from `jtek.json` on the base branch. Leave it out to run every declared check. A ticket cannot add a command.
- **`after`:** optional. Ids that must be Done first. Checked for local tickets only.
- **`area`:** optional. The part of the codebase the ticket touches, in a word or two, for example `billing`. Whoever starts sessions uses it to decide which tickets go together, and `jtek.py list` shows it.
- **`kind`:** optional. `feature`, `bug`, or `refactor`. It picks the playbook in the `jt-work` skill.
- **`review: human`:** optional. By default a change needs a `PASS` from a session that did not write it before it reaches Review. The human adds this line to waive that for a small ticket. The waiver is ignored when the change touches a file on the `attention:` line.
- **`## Goal` and `## Done when`:** required. `start` refuses a ticket without them.
- **`## Out of scope`:** behaviour that must stay exactly as it is now. Write the behaviour, not only the topic: "titles with non-ASCII letters give the same slug as today" is clearer than "non-ASCII letters".

## Where tickets live

- **Local:** one file per ticket in `<git-common-dir>/jtek/tickets/<id>.md`. This folder is outside the tracked files, so parallel sessions never conflict on it. `jtek.py add --title "..."` creates one in Backlog. Set `JTEK_STATE` to keep the folder somewhere else.
- **Notion or another system:** the page is the source of truth. The session reads it, passes the text with `--from-file`, and writes the status back. A ticket lives in one place. Do not keep a local copy in sync.

## Statuses

| Status | Meaning | Who sets it |
|---|---|---|
| Backlog | Written down, not released. | Human or bot |
| Todo | Released for an agent to take. | Human only |
| In Progress | A session has claimed it. | `jtek.py start` |
| Review | Checks pass, a non-author verdict is PASS, the evidence is saved, and a pull request is open (or the repository has no forge). | `jtek.py finish` |
| Done | The pull request is merged. Read from the forge. Without a forge, the human sets it after merging. | `jtek.py list --sync`, or the bot |
| Cancelled | Dropped. | Human |

- **`waiting`** is a field, not a status. `input` means the agent has a question. `approval` means a step needs permission. The ticket stays In Progress.
- **Rework:** the human sets a Review ticket back to Todo and adds what to fix. A new session runs `start <id>` and continues in the same worktree.
- **Answering a question:** the human writes the answer in the ticket. A new session runs `start <id>`.
- There is no command that sets Todo, Done by hand, or Cancelled. The human edits the ticket.

## Claims and parallel work

After creating the worktree, `start` runs the `setup` command from `jtek.json`, when there is one. Then, before the first edit, `start` runs the ticket's checks on the base. If one fails, the worktree and the claim are removed, the ticket stays Todo, and the log is kept in `<git-common-dir>/jtek/baseline/<id>/`. A green run is remembered for that base commit and set of commands, so tickets started from the same commit do not repeat it. Pass `--no-baseline` to skip this when the checks are slow.

`start` creates `<git-common-dir>/jtek/work/<id>/`. Creating a directory is atomic, so when two sessions start the same id, one is refused. Each ticket gets the worktree `<repo>.jtek/<id>` beside the repository and the branch `jtek/<id>`.

`stop` refuses while the worktree has uncommitted files. Unfinished work is committed as `wip: ...` first, so nothing is left that the next session cannot explain.

A claim is live until its session ends with a result (`finish` or `stop`). After that it is parked, and the next `start` for that id resumes it. `start` refuses a live claim. When a session died without a result, the human runs `start <id> --resume`.

Notion has no atomic claim. The directory above is the lock for sessions on one machine. If sessions run on several machines, the launcher must set In Progress in Notion before it starts a session. For that reason `start --from-file` accepts a ticket that is already In Progress, and a local ticket must be Todo.

A relaunch for a Notion ticket may pass only the id. `start` then reuses the saved snapshot. Pass `--from-file` again when the page changed.

## Result

Every session ends with this block. `finish` and `stop` print it and save it in `work/<id>/result.md`.

```
jtek-result
id: T-12
status: In Progress | Review
outcome: review | needs-review | needs-human
waiting: input | approval | -
checks: lint=pass test=pass @1a2b3c4
verdict: none | PASS by reviewer @1a2b3c4 | waived by the ticket
pr: <url>
ci: pass | fail | pending | none | unknown | -
evidence: <path> (3 seen, 0 not run) (+2 attached in <folder>) | -
attention: jtek.json, scripts/verify.sh (run by `verify`) | -
branch: jtek/T-12
source: local:<path> | <url>
note: <one line>
```

- **`ci`:** the state of the pull request's checks on the forge, read with `gh`. `finish` refuses while it is `fail`.
- **`evidence`:** the file that accounts for each `Done when` item as `seen` or `not run`, at most 40 lines not counting blank ones, with the counts and how many screenshots or outputs are attached. It is also the pull request body. Read it before the diff, and look at every `not run`.
- **`attention`:** files the human should open first, because they decide whether checks pass: `jtek.json`, `.jtek/`, CI config, lockfiles, a file whose path is written in a check or `setup` command, a deleted test file, an existing test file that lost or changed lines, and anything matching `watch` in `jtek.json`. Adding tests is not flagged. `-` means none.
- **`review`:** ready for the human to review and merge.
- **`needs-review`:** the usual result of the first `finish`. Checks pass; start a non-author session with the `jt-review` skill for this id, then run `finish` again.
- **`needs-human`:** read `waiting` and `note`.
