# Tickets, statuses, and the result

## Ticket format

A ticket is a page on the board (a Notion page or a FLO item), or a local file when there is no board. Only the outer loop reads the board with its tool and saves a ticket file in this format, as [starting-sessions.md](starting-sessions.md), [notion.md](notion.md), and [flo.md](flo.md) say, then hands the file and page link to the inner-loop session. The header lines come from the page's properties, and the sections from its body. The header lines sit right under the title: the first blank line after one, or the first line of other text, ends them, and `start` reads no header line below that. `jtek.py start` keeps a copy, and that copy is the file to work from.

```markdown
# Short title
id: T-12
status: Todo
kind: feature
area: billing
checks: lint, test
after: T-10

## Goal
What should be true when this is done, and why. No guessed cause, and no fix.

## Done check
- One observable outcome per line. Not a step the skills already run.

## Proof
- The command output, a stored value, or a before and after number.

## Context
- What is already known, or `none`.

## Constraints
- Behaviour that must stay as it is now.
```

A page that was written with `## Done when` and `## Out of scope` still starts. A draft checked with `jtek.py ticket` does not: it has to be the five slots above, and no other heading. The blank form is [ticket-template.md](ticket-template.md).

- **`id`:** the page's Ticket ID. It names the branch `jtek/<id>` and the worktree.
- **`checks`:** optional. Names from the machine config. Leave it out to run every declared check. A ticket cannot add a command.
- **`after`:** optional. The tickets in After that are not Done yet. They may belong to any repository on the board. `start` refuses a new ticket that has this line.
- **`repo`:** optional. The repository the ticket is for, when one board serves several. It is the `name` in that repository's machine config, or its folder name. `start` refuses a ticket whose `repo` is another one.
- **`area`:** optional. The part of the codebase the ticket touches, in a word or two, for example `billing`. Whoever starts sessions uses it to decide which tickets go together.
- **`kind`:** optional. `feature`, `bug`, or `refactor`. It picks the playbook in the `jt-work` skill.
- **`review: human`:** optional. By default a change needs a `PASS` from a session that did not write it before it reaches Review. The human adds this line to waive that for a small ticket. The waiver is ignored when the change touches a file on the `attention:` line.
- **`## Goal` and the outcomes:** required. The outcomes are `## Done check` on a draft, and `start` also reads `## Done when` on a page already written that way. `start` refuses a ticket with neither.
- **`## Proof`, `## Context`, and `## Constraints`:** required on a draft. `jtek.py ticket` refuses a missing slot, any other heading, a skill step under Done check, and a line that states the cause or the fix. Constraints name behaviour, not only a topic: "titles with non-ASCII letters give the same slug as today" is clearer than "non-ASCII letters".

A blank form to copy, a filled example, and what makes a ticket workable: [ticket-template.md](ticket-template.md).

## A local ticket

Work without a ticket is started with `jtek.py start --local --from-file <file>`. The file has a title, `kind:`, and the three sections, and no `id:` or `status:`. The script gives it the next free `LOCAL-<n>`, never one a released ticket had, and writes `source: local, written by the session` in the result. The session wrote the header, so it grants nothing: every declared check runs, `review:`, `checks:`, and `after:` are ignored, and picking it up again with its `LOCAL-<n>` id does not reset the failed runs or the FAIL count. Only the human gives new tries, with `jtek.py release`. A local ticket that stopped with a question is picked up again with `start --local --answered`, once the human has answered in the chat; without it `start` refuses, and a session never adds it on its own. A board ticket cannot use a `LOCAL-` id. There is no board line. When the change is one file and nothing is on the `attention:` line, `finish` needs no verdict, and the result says `verdict: skipped`.

## Where tickets live

The page on the board is the source of truth. The layout of the board (for the outer loop) is in [notion.md](notion.md), or [flo.md](flo.md) for FLO. A repository with no board keeps each ticket as a file, and that file is the page: [files.md](files.md). The copy, the claim, the logs, and the result of each ticket are in `<git-common-dir>/jtek/work/<id>/`, outside the tracked files, so parallel sessions never conflict on them. Set `JTEK_STATE` to keep that folder somewhere else.

## Statuses

| Status | Meaning | Who sets it |
|---|---|---|
| Backlog | Written down, not released. | Human |
| Todo | Released for an agent to take. | Human only |
| In Progress | A session has claimed it. | the outer loop, after `jtek.py start` allows it (or the session, in the local file when there is no board) |
| Review | Checks pass, a non-author verdict is PASS, the evidence is saved, and a pull request is open (or the repository has no forge). | the outer loop, from `jtek-result` after `jtek.py finish` prints `outcome: review` (or the session, in the local file when there is no board) |
| Done | The pull request is merged. Read from the forge. Without a forge, the human sets it after merging. | the outer loop, when `jtek.py sync` prints `board: Status=Done` |
| Cancelled | Dropped. | Human |

- **Waiting** is a property, not a status. `input` means the agent has a question. `approval` means a step needs permission. The ticket stays In Progress.
- **Rework:** the human sets a Review ticket back to Todo and adds what to fix. With a board, the outer loop reads the updated page into a ticket file and starts a new session, which runs `start` again and continues in the same worktree.
- **Answering a question:** the human writes the answer on the page and sets Status to Todo. With a board, the outer loop reads the updated page into a ticket file and starts a new session, which runs `start` again.
- There is no command that sets Todo, Done by hand, or Cancelled. The human edits the page.

## Claims and parallel work

Before anything else, `start` fetches the base branch from `origin` and moves the local one forward when it is only behind, so a ticket starts from what is merged. It never rewrites the branch: when both sides have moved it says so and starts from the local one, and when the branch cannot move it refuses. `--no-fetch` skips this.

After creating the worktree, `start` runs the `setup` command from the machine config, when there is one. Then, before the first edit, `start` runs the ticket's checks on the base. If one or more checks fail there, `start` keeps the worktree and claim, records `known_red` and `known_red_base` in meta (and `known-red.md` in the work dir for evidence), saves one Backlog follow-up ticket (or writes a draft file for the outer loop when a board is configured), and keeps the logs in `<git-common-dir>/jtek/baseline/<id>/`. `check` and `finish` still run those checks and waive only them while the base stays at that commit. A green run is remembered for that base commit and set of commands, so tickets started from the same commit do not repeat it. Pass `--no-baseline` to skip this when the checks are slow.

`start` creates `<git-common-dir>/jtek/work/<id>/`. Creating a directory is atomic, so when two sessions start the same id, one is refused. Each new ticket gets the worktree `.claude/worktrees/<id>` inside the repository (with `.claude/worktrees/` added once to `.git/info/exclude`, never editing `.gitignore` or any tracked file) and the branch `jtek/<id>`. Existing claims keep the path stored in `meta.json`.

`stop` refuses while the worktree has uncommitted files. Unfinished work is committed as `wip: ...` first, so nothing is left that the next session cannot explain.

A claim is live until its session ends with a result (`finish` or `stop`). After that it is parked, and the next `start` for that id resumes it. `start` refuses a live claim. When a session died without a result, the human tells a new session to take the ticket over, and that session adds `--resume` to `start`. A session never adds it on its own.

The board has no atomic claim. The directory above is the lock for sessions on one machine. The outer loop writes In Progress on the page only after `start` allows it (with no board, the session updates the local ticket file).

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
evidence: <path> (3 seen, 0 not run, 3 of the seen cite a recorded run) (+2 attached in <folder>) | -
attention: jtek.json, scripts/verify.sh (run by `verify`) | -
branch: jtek/T-12
source: <page link>
note: <one line>
comment file: <path> (when the board line asks for a comment)
board: Status=Review; Waiting=; PR=<url>; comment=result+evidence | Waiting=input; comment=result | PR=<url> | -
```

- **`board`:** what the outer loop must write on the ticket's page (or what the session writes to the local ticket file when there is no board). The meaning of each part is in [notion.md](notion.md), and where each lives in FLO in [flo.md](flo.md). `-` means nothing.
- **`ci`:** the state of the pull request's checks on the forge, read with `gh` or `glab`, or with the project's `pr_state` command. `finish` refuses while it is `fail`. `none` right after a push usually means the forge has not started the run yet.
- **`verdict`:** only a verdict for the change and the ticket as they are now is shown. `none` means one is still needed. A verdict stops counting when the code changes, even by whitespace or by moving the same edit to another place, and when the human changes the ticket's `Goal`, `Done when`, or `Out of scope`.
- **`evidence`:** the file that accounts for each `Done when` item as `seen` or `not run`, at most 40 lines not counting blank ones (more only for a ticket with over 30 items), with the counts and how many screenshots or outputs are attached. It is also the pull request body. Read it before the diff, and look at every `not run`.
- **`attention`:** files the human should open first, because they decide whether checks pass: `jtek.json`, `.jtek/`, `.claude/*`, CI config, lockfiles and dependency manifests (`requirements*.txt`, `go.mod`, `pom.xml`, `build.gradle`, `composer.json`, `*.csproj`, and the like), migration folders, the usual files that define a check command (`Makefile`, `package.json`, `pyproject.toml`, and the like), a file whose path is written in a check or `setup` command, a deleted test or spec file, an existing test or spec file that lost or changed lines (also when it was renamed), and anything matching `watch` in `jtek.json`. Adding tests is not flagged. `-` means none. The list is a set of known names, not proof: add your project's own to `watch`.
- **`review`:** ready for the human to review and merge.
- **`needs-review`:** the usual result of the first `finish`. Checks pass; start a non-author session with the `jt-review` skill for this id, then run `finish` again.
- **`needs-human`:** read `waiting` and `note`.
