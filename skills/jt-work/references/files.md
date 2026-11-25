# The board as files

A repository needs no board. When `board` in `jtek.json` is empty, each ticket is a file, and the folder of those files is the board. Everything [notion.md](notion.md) says about the `board:` line, the Todo signal, and the limits holds here too. This file says only where each part lives in a ticket file.

## Where the files are

`.jtek/tickets/<id>.md`, inside the repository. A fresh clone has the tickets, because the folder is committed on the base branch. `ticket --save` writes there and says so. `jtek.py doctor` prints the folder, and `start` prints the file as `page:`. Every command reads the main checkout's copy, so a ticket worktree and a second machine see the same file once it is committed.

An older checkout may still have tickets beside the repository, at `<repository>.jtek/_tickets/<id>.md`. Those files are still read. A new ticket is not written there. When both folders have the same id, the file inside the repository wins, and an id used in either folder is not given out again.

Nothing is set up. The folder appears with the first ticket. Commit it on the base branch. The script does not commit it.

## Where each part of a ticket lives

The file is in the ticket format of [ticket.md](ticket.md): the title, the header lines right under it, and the five card slots (`Goal`, `Done check`, `Proof`, `Context`, `Constraints`).

| Ticket | In the file | Who writes it |
|---|---|---|
| id | `id:`, the same as the file's name. `jtek.py ticket <file> --save` gives the next free `T-<n>` | the script |
| `status:` | the `status:` line | see below |
| `kind:`, `repo:`, `area:`, `after:`, `review: human`, `checks:` | header lines | human |
| `waiting:` | a header line: `input` or `approval` | the session sets it, and clears it at the next start |
| `pr:` | a header line with the pull request's link | the session |
| the body | `## Goal`, `## Done check`, `## Proof`, `## Context`, `## Constraints` | human |
| comments | `## Log`, the last section of the file | the session, and the human for an answer |

`after:` lists ticket ids. The script reads each one's file and counts an id only while that file is not Done.

## Status

| Status | Who writes it |
|---|---|
| Backlog | `ticket --save` writes it. A session never changes it |
| Todo | the human only. It releases the ticket, and it is how the human says "I answered" or "fix this" |
| In Progress, Review | the session, from a `board:` line |
| Done, Cancelled | the human, or whoever runs `sync`, from its `board: Status=Done` line |

A session never writes `status: Todo`, and never writes `review: human` or `checks:`. A file keeps no history of who changed it, so nothing but this rule stands between a session and those lines. A team that needs a record uses Notion or FLO.

## Writing a `board:` line

Change the file `start` printed as `page:`, and nothing else in it:

- `Status=<value>`: the `status:` line.
- `Waiting=<value>`: the `waiting:` line. `Waiting=` with no value removes the line.
- `PR=<link>`: the `pr:` line.
- `comment=result` or `comment=result+evidence`: add the text of the `comment file:` the result names to the end of the file, under `## Log`, inside a code block. Add the `## Log` heading once, when the file has none. The code block matters: a heading in the result must not read as a heading of the ticket.
- `-`: write nothing.

Keep the header lines together right under the title, with no blank line between them. Never change the title or the three sections: they are what the evidence and the verdict were made for.

## The human

- **Release a ticket:** write `status: Todo` in its file.
- **Answer a question:** write the answer in the file, under `## Log` or in the section it changes, remove nothing, and write `status: Todo`.
- **Ask for a fix after review:** write what to fix, and `status: Todo`.

## For whoever starts the sessions

`jtek.py next` and `jtek.py sync` take no `--board-file` here: they read the ticket files themselves.
