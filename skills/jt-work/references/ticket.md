# Tickets, statuses, and the result

## Ticket format

A ticket is a page on the Notion board. `jtek.py start` copies it into this format, and that copy is the file you read. The header lines come from the page's properties, and the sections from its body.

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

- **`id`:** the page's Ticket ID. It names the branch `jtek/<id>` and the worktree.
- **`checks`:** optional. Names from `jtek.json` on the base branch. Leave it out to run every declared check. A ticket cannot add a command.
- **`after`:** optional. Tickets that must be Done first. They may belong to any repository on the board. `start` refuses while one is not Done.
- **`repo`:** optional. The repository the ticket is for, when one board serves several. It is the `name` in that repository's `jtek.json`, or its folder name. `start` refuses a ticket whose `repo` is another one.
- **`area`:** optional. The part of the codebase the ticket touches, in a word or two, for example `billing`. Whoever starts sessions uses it to decide which tickets go together, and `jtek.py list` shows it.
- **`kind`:** optional. `feature`, `bug`, or `refactor`. It picks the playbook in the `jt-work` skill.
- **`review: human`:** optional. By default a change needs a `PASS` from a session that did not write it before it reaches Review. The human adds this line to waive that for a small ticket. The waiver is ignored when the change touches a file on the `attention:` line.
- **`## Goal` and `## Done when`:** required. `start` refuses a ticket without them.
- **`## Out of scope`:** behaviour that must stay exactly as it is now. Write the behaviour, not only the topic: "titles with non-ASCII letters give the same slug as today" is clearer than "non-ASCII letters".

## Where tickets live

The page in Notion is the source of truth. The layout of the board is in [notion.md](notion.md). The copy, the claim, the logs, and the result of each ticket are in `<git-common-dir>/jtek/work/<id>/`, outside the tracked files, so parallel sessions never conflict on them. Set `JTEK_STATE` to keep that folder somewhere else.

## Statuses

| Status | Meaning | Who sets it |
|---|---|---|
| Backlog | Written down, not released. | Human |
| Todo | Released for an agent to take. | Human only |
| In Progress | A session has claimed it. | `jtek.py start` |
| Review | Checks pass, a non-author verdict is PASS, the evidence is saved, and a pull request is open (or the repository has no forge). | `jtek.py finish` |
| Done | The pull request is merged. Read from the forge. Without a forge, the human sets it after merging. | `jtek.py list --sync` |
| Cancelled | Dropped. | Human |

- **Waiting** is a property, not a status. `input` means the agent has a question. `approval` means a step needs permission. The ticket stays In Progress.
- **Rework:** the human sets a Review ticket back to Todo and adds what to fix. A new session runs `start <id>` and continues in the same worktree.
- **Answering a question:** the human writes the answer on the page and clears Waiting. A new session runs `start <id>`.
- There is no command that sets Todo, Done by hand, or Cancelled. The human edits the page.

## Claims and parallel work

After creating the worktree, `start` runs the `setup` command from `jtek.json`, when there is one. Then, before the first edit, `start` runs the ticket's checks on the base. If one fails, the worktree and the claim are removed, the ticket stays Todo on the board, and the log is kept in `<git-common-dir>/jtek/baseline/<id>/`. A green run is remembered for that base commit and set of commands, so tickets started from the same commit do not repeat it. Pass `--no-baseline` to skip this when the checks are slow.

`start` creates `<git-common-dir>/jtek/work/<id>/`. Creating a directory is atomic, so when two sessions start the same id, one is refused. Each ticket gets the worktree `<repo>.jtek/<id>` beside the repository and the branch `jtek/<id>`.

`stop` refuses while the worktree has uncommitted files. Unfinished work is committed as `wip: ...` first, so nothing is left that the next session cannot explain.

A claim is live until its session ends with a result (`finish` or `stop`). After that it is parked, and the next `start` for that id resumes it. `start` refuses a live claim. When a session died without a result, the human runs `start <id> --resume`.

Notion has no atomic claim. The directory above is the lock for sessions on one machine. `start` writes In Progress on the page as its last step, and gives the claim back when that write fails.

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
source: <page link>
note: <one line>
```

- **`ci`:** the state of the pull request's checks on the forge, read with `gh`. `finish` refuses while it is `fail`.
- **`evidence`:** the file that accounts for each `Done when` item as `seen` or `not run`, at most 40 lines not counting blank ones, with the counts and how many screenshots or outputs are attached. It is also the pull request body. Read it before the diff, and look at every `not run`.
- **`attention`:** files the human should open first, because they decide whether checks pass: `jtek.json`, `.jtek/`, CI config, lockfiles, a file whose path is written in a check or `setup` command, a deleted test file, an existing test file that lost or changed lines, and anything matching `watch` in `jtek.json`. Adding tests is not flagged. `-` means none.
- **`review`:** ready for the human to review and merge.
- **`needs-review`:** the usual result of the first `finish`. Checks pass; start a non-author session with the `jt-review` skill for this id, then run `finish` again.
- **`needs-human`:** read `waiting` and `note`.
