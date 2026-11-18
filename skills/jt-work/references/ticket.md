# Tickets, statuses, and the result

## Ticket format

The same format is used for a local file and for text fetched from Notion or another system.

```markdown
# Short title
id: T-12
status: Todo
kind: feature
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
- **`kind`:** optional. `feature`, `bug`, or `refactor`. It picks the playbook in the `jt-work` skill.
- **`review: agent`:** optional. The human adds it to a risky ticket. The change then needs a `PASS` from a session that did not write it before it reaches Review. Without it, the human's own review of the pull request is the review.
- **`## Goal` and `## Done when`:** required. `start` refuses a ticket without them.
- **`## Out of scope`:** behaviour that must stay exactly as it is now.

## Where tickets live

- **Local:** one file per ticket in `<git-common-dir>/jtek/tickets/<id>.md`. This folder is outside the tracked files, so parallel sessions never conflict on it. `jtek.py add --title "..."` creates one in Backlog. Set `JTEK_STATE` to keep the folder somewhere else.
- **Notion or another system:** the page is the source of truth. The session reads it, passes the text with `--from-file`, and writes the status back. A ticket lives in one place. Do not keep a local copy in sync.

## Statuses

| Status | Meaning | Who sets it |
|---|---|---|
| Backlog | Written down, not released. | Human or bot |
| Todo | Released for an agent to take. | Human only |
| In Progress | A session has claimed it. | `jtek.py start` |
| Review | Checks pass and a pull request is open (or the repository has no forge). With `review: agent`, a non-author verdict is PASS too. | `jtek.py finish` |
| Done | The pull request is merged. Read from the forge. Without a forge, the human sets it after merging. | `jtek.py list --sync`, or the bot |
| Cancelled | Dropped. | Human |

- **`waiting`** is a field, not a status. `input` means the agent has a question. `approval` means a step needs permission. The ticket stays In Progress.
- **Rework:** the human sets a Review ticket back to Todo and adds what to fix. A new session runs `start <id>` and continues in the same worktree.
- **Answering a question:** the human writes the answer in the ticket. A new session runs `start <id>`.
- There is no command that sets Todo, Done by hand, or Cancelled. The human edits the ticket.

## Claims and parallel work

`start` creates `<git-common-dir>/jtek/work/<id>/`. Creating a directory is atomic, so when two sessions start the same id, one is refused. Each ticket gets the worktree `<repo>.jtek/<id>` beside the repository and the branch `jtek/<id>`.

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
verdict: not requested | none | PASS by reviewer @1a2b3c4
pr: <url>
branch: jtek/T-12
source: local:<path> | <url>
note: <one line>
```

- **`review`:** ready for the human to review and merge.
- **`needs-review`:** only for a ticket with `review: agent`. Checks pass; start a non-author session with the `jt-review` skill for this id, then run `finish` again.
- **`needs-human`:** read `waiting` and `note`.
