# Ticket files

Saved tickets in jtek are local files on this machine. Work starts either from an existing ticket file, or directly from a goal typed in chat (`jtek.py start --local --goal "<goal>"`, which assigns a `LOCAL-<n>` id with no ticket file or `Done when`).

## Where ticket files live

`$HOME/.jtek/repos/<repo id>/tickets/<id>.md`, on this machine. The repository id is the origin URL's host, non-default port, and path, or `path` plus the checkout path when there is no origin. See [setup.md](setup.md). `jtek.py ticket <file> --save` writes there and says so. `jtek.py doctor` prints the folder, and `jtek.py start` prints the file as `ticket file:`. A second checkout of the same origin on this machine reads the same file. A new machine, such as a cloud agent, does not have the folder until you copy it or run `jtek.py migrate` there.

An older checkout may still have tickets beside the repository, at `<repository>.jtek/_tickets/<id>.md`. Those files are still read. A new ticket is not written there. When both places have the same id, the file under `$HOME/.jtek` wins, and an id used in either place is not given out again.

Nothing is set up. The folder appears with the first ticket. It is not committed. `jtek.py migrate` moves a repository that still has `jtek.json` or `.jtek/` into this folder and tells you to commit the removal.

## Where each part of a ticket lives

The file is in the ticket format of [ticket.md](ticket.md): the title, the header lines right under it, and the sections (`Goal` and `Done when`, or the five card slots `Goal`, `Done check`, `Proof`, `Context`, `Constraints` on a draft checked by `jtek.py ticket`).

| Ticket | In the file | Who writes it |
|---|---|---|
| id | `id:`, the same as the file's name. `jtek.py ticket <file> --save` gives the next free `T-<n>` | the script |
| `status:` | the `status:` line | see below |
| `kind:`, `repo:`, `area:`, `after:`, `review: human`, `checks:` | header lines | human |
| `waiting:` | a header line: `input` or `approval` | `jtek.py stop` sets it; `jtek.py start` and `finish` clear it |
| `pr:` | a header line with the pull request's link | `jtek.py finish` sets it |
| the body | `## Goal`, `## Done when` / `## Done check`, `## Proof`, `## Context`, `## Constraints` | human |
| notes | `## Log`, the last section of the file | human, for an answer or rework note |

`after:` lists ticket ids. The script reads each one's file and counts an id only while that file is not Done.

## Status

| Status | Who writes it |
|---|---|
| Backlog | `jtek.py ticket --save` writes it. A session never changes it |
| Todo | the human only. It releases the ticket, and it is how the human says "I answered" or "fix this" |
| In Progress, Review | `jtek.py start` sets `In Progress` (clearing `waiting:`); `jtek.py finish` sets `Review` (and `pr:`) once checks, evidence, and verdict pass |
| Done, Cancelled | `jtek.py sync` sets `Done` when the forge reports the pull request merged; the human sets `Done` (without a forge) or `Cancelled` |

A session never writes `status: Todo`, and never writes `review: human` or `checks:`. Keep the header lines together right under the title, with no blank line between them. Never change the title or the ticket sections during a run: they are what the evidence and the verdict were made for.

## The human

- **Release a ticket:** write `status: Todo` in its file.
- **Answer a question:** write the answer in the file, under `## Log` or in the section it changes, remove nothing, and write `status: Todo`.
- **Ask for a fix after review:** write what to fix, and `status: Todo` (or leave a submitted review on the pull request).

## For whoever starts the sessions

`jtek.py next`, `jtek.py sync`, and `jtek.py status` read the ticket files and local claims on this machine directly.
