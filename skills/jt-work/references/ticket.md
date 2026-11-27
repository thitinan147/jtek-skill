# Tickets, statuses, and the result

## Intake

Work enters jtek in one of two ways:

1. **An existing ticket file** — either in `$HOME/.jtek/repos/<repo id>/tickets/<id>.md` (started with `jtek.py start <id>`) or anywhere on disk (started with `jtek.py start --from-file <file>` or `jtek.py start <file>`).
2. **A goal typed in chat** — the agent starts directly with `jtek.py start --local --goal "<goal>"`. The script assigns a `LOCAL-<n>` id and stores the goal in `work/LOCAL-<n>/goal.md`, where the second-session reviewer reads it alongside the diff. No ticket file, no `Done when`, and `broke` is skipped. The agent proceeds unless the change reaches outside the pull request (P16).

To save a follow-up or future ticket file in Backlog without starting it yet, run `jtek.py ticket <file> --save`.

## Ticket format

A ticket is a local Markdown file. The header lines sit right under the title: the first blank line after one, or the first line of other text, ends them, and `start` reads no header line below that. `jtek.py start` keeps a snapshot in the claim folder, and that snapshot is what both the author and reviewer read.

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

A ticket file written with `## Done when` and `## Out of scope` still starts. A draft checked with `jtek.py ticket` must use the five slots above and no other heading. The blank form is [ticket-template.md](ticket-template.md).

- **`id`:** the ticket id (matching the filename when stored in `tickets/`). It names the branch `jtek/<id>` and the worktree.
- **`checks`:** optional. Names from the machine config. Leave it out to run every declared check. A ticket cannot add a command.
- **`after`:** optional. Ticket ids that must be `Done` before this one can start. `start` reads each referenced ticket file and refuses while any is not `Done`.
- **`repo`:** optional. The repository the ticket is for. It is the `name` in that repository's machine config, or its folder name. `start` refuses a ticket whose `repo` is another one.
- **`area`:** optional. The part of the codebase the ticket touches, in a word or two, for example `billing`. Whoever starts sessions uses it to decide which tickets go together.
- **`kind`:** optional. `feature`, `bug`, or `refactor`. It picks the playbook in the `jt-work` skill.
- **`review: human`:** optional. By default a change needs a `PASS` from a session that did not write it before it reaches Review. The human adds this line to waive that for a small ticket file. Ignored when the change touches a file on the `attention:` line. (`--local` chat goals have no ticket header.)
- **`## Goal` and the outcomes:** required. Outcomes live under `## Done when` or `## Done check`. `start` refuses a ticket with neither.
- **`## Proof`, `## Context`, and `## Constraints`:** required on a draft checked by `jtek.py ticket`. Constraints name behaviour, not only a topic: "titles with non-ASCII letters give the same slug as today" is clearer than "non-ASCII letters".

A blank form to copy, a filled example, and what makes a ticket workable: [ticket-template.md](ticket-template.md).

## A local chat goal

Work started from a chat goal uses `jtek.py start --local --goal "<goal>"`. There is no ticket file, no header, and no `Done when`. The script gives it the next free `LOCAL-<n>`, never one a released claim had, writes `work/LOCAL-<n>/goal.md` for the reviewer to read, runs every declared check, and sets `source: local, chat goal` in the result. `broke` applies per `Done when` item only and is skipped for local work (`jtek.py broke` refuses, and `finish` does not require broke records). `finish` requires green checks on the current commit, evidence with at least one `seen:` or `not run:` line for the goal plus a `clean-up:` line, and a verdict from a different session (a one-file local change with nothing on the `attention:` line skips the second look and prints `verdict: skipped`). Resume a stopped local claim with `jtek.py start --local LOCAL-<n>` (adding `--answered` after the human answers a question in chat; without it `start` refuses, and a session never adds it on its own). Resuming does not reset failed runs or the FAIL count; only `jtek.py release` drops the claim. A regular ticket file cannot use a `LOCAL-` id.

## Where tickets live

Ticket files live on this machine under `$HOME/.jtek/repos/<repo id>/tickets/` ([files.md](files.md)). The snapshot, the claim, the logs, and the result of each ticket live in `<git-common-dir>/jtek/work/<id>/`, outside tracked files, so parallel sessions never conflict on them. Set `JTEK_STATE` to keep that folder somewhere else.

## Statuses

`jtek.py` keeps a `status:` header in local ticket files for bookkeeping (`after:` checks `Done`, `start` checks `Todo`, `sync` marks merged PRs `Done`):

| Status | Meaning | Who sets it |
|---|---|---|
| Backlog | Written down, not released. | `jtek.py ticket --save`, or human |
| Todo | Released for an agent to take. | Human only |
| In Progress | A session has claimed it. | `jtek.py start` |
| Review | Checks pass, a non-author verdict is PASS, the evidence is saved, and a pull request is open (or the repository has no forge). | `jtek.py finish` |
| Done | The pull request is merged. Read from the forge. Without a forge, the human sets it after merging. | `jtek.py sync` (or human without a forge) |
| Cancelled | Dropped. | Human |

- **Waiting** (`waiting:`) is a header field, not a status. `input` means the agent has a question; `approval` means a step needs permission outside the PR. The ticket stays `In Progress`.
- **Rework:** the human sets a Review ticket file back to `status: Todo` and adds what to fix (or submits a review on the pull request). A new session runs `start` again and continues in the same worktree.
- **Answering a question:** for a ticket file, the human writes the answer in the file and sets `status: Todo`; for a `--local` chat goal, the human answers in chat and the session resumes with `jtek.py start --local <id> --answered`.
- There is no command that sets Todo, merges a PR, or sets Cancelled.

## Claims and parallel work

Before anything else, `start` fetches the base branch from `origin` and moves the local one forward when it is only behind, so a ticket starts from what is merged. It never rewrites the branch: when both sides have moved it says so and starts from the local one, and when the branch cannot move it refuses. `--no-fetch` skips this.

After creating the worktree, `start` runs the `setup` command from the machine config, when there is one. Then, before the first edit, `start` runs the ticket's checks on the base. If one or more checks fail there, `start` keeps the worktree and claim, records `known_red` and `known_red_base` in meta (and `known-red.md` in the work dir for evidence), saves one local Backlog follow-up ticket file in `tickets/`, and keeps the logs in `<git-common-dir>/jtek/baseline/<id>/`. `check` and `finish` still run those checks and waive only them while the base stays at that commit. A green run is remembered for that base commit and set of commands, so tickets started from the same commit do not repeat it. Pass `--no-baseline` to skip this when the checks are slow.

`start` creates `<git-common-dir>/jtek/work/<id>/`. Creating a directory is atomic, so when two sessions start the same id, one is refused. Each new ticket gets the worktree `.claude/worktrees/<id>` inside the repository (with `.claude/worktrees/` added once to `.git/info/exclude`, never editing `.gitignore` or any tracked file) and the branch `jtek/<id>`. Existing claims keep the path stored in `meta.json`.

`stop` refuses while the worktree has uncommitted files. Unfinished work is committed as `wip: ...` first, so nothing is left that the next session cannot explain.

A claim is live until its session ends with a result (`finish` or `stop`). After that it is parked, and the next `start` for that id resumes it. `start` refuses a live claim. When a session died without a result, the human tells a new session to take the ticket over, and that session adds `--resume` to `start`. A session never adds it on its own.

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
source: <ticket file path | local, chat goal>
note: <one line>
```

- **`ci`:** the state of the pull request's checks on the forge, read with `gh` or `glab`, or with the project's `pr_state` command. `finish` refuses while it is `fail`. `none` right after a push usually means the forge has not started the run yet.
- **`verdict`:** only a verdict for the change and the ticket as they are now is shown. `none` means one is still needed. A verdict stops counting when the code changes, even by whitespace or by moving the same edit to another place, and when the human changes the ticket's `Goal`, `Done when`, or `Out of scope`.
- **`evidence`:** the file that accounts for each `Done when` item (or the goal as a whole for `--local`) as `seen` or `not run` plus `clean-up:`, at most 40 lines not counting blank ones (more only for a ticket with over 30 items), with the counts and how many screenshots or outputs are attached. It is also the pull request body. Read it before the diff, and look at every `not run`.
- **`attention`:** files the human should open first, because they decide whether checks pass: `jtek.json`, `.jtek/`, `.claude/*`, CI config, lockfiles and dependency manifests (`requirements*.txt`, `go.mod`, `pom.xml`, `build.gradle`, `composer.json`, `*.csproj`, and the like), migration folders, the usual files that define a check command (`Makefile`, `package.json`, `pyproject.toml`, and the like), a file whose path is written in a check or `setup` command, a deleted test or spec file, an existing test or spec file that lost or changed lines (also when it was renamed), and anything matching `watch` in `jtek.json`. Adding tests is not flagged. `-` means none. The list is a set of known names, not proof: add your project's own to `watch`.
- **`review`:** ready for the human to review and merge.
- **`needs-review`:** the usual result of the first `finish`. Checks pass; start a non-author session with the `jt-review` skill for this id, then run `finish` again.
- **`needs-human`:** read `waiting` and `note`.
