# jtek-skill

**The inner loop for a coding agent: take one ticket, build it in its own worktree, pass the project's real checks, get a verdict from a session that did not write it, and stop at a pull request with the evidence for you to merge.**

`jtek-skill` is eleven small [Agent Skills](https://agentskills.io/) and one Python script. `jt-work` runs the steps in order, and each step has its own skill. It uses no other skill set. Choosing the next ticket, starting sessions, and merging are the outer loop. You do those yourself, or a bot does them for you.

## What it does

- **One ticket, one worktree.** Start as many sessions as you want, each on a different ticket. A second session that takes the same ticket is refused.
- **A session may take several tickets in a row, when it fits.** Give `/jt-work` several ids. The session goes on to the next one only if the last ended cleanly, the next is in code it already read, and the session is still short. Otherwise it stops and lists the ids it did not start.
- **The board is a Notion database.** The agent reads each ticket's page with its Notion tool, such as the Notion MCP connector, and writes back exactly what the script's `board:` line says.
- **The project declares the checks.** `jtek.json` on the base branch lists them. A ticket can name a check. It cannot add a command.
- **"Done" is not the agent's word.** A ticket reaches Review only when the checks pass on the current commit, a session that did not write the change records `PASS`, the evidence is saved, and a pull request link is given. Add `review: human` to a small ticket to waive the verdict. When `gh` can read the link, the script also requires the pull request to be open at that commit.
- **A stopped ticket can be picked up.** A session that needs an answer ends with a question. Run `/jt-work <id>` again after you answer, and it continues in the same worktree.
- **You review the evidence first.** Every result points to at most 40 lines that account for each `Done when` item as `seen` or `not run`, with screenshots or output attached. Evidence that skips an item is refused.
- **Red CI never reaches you.** `finish` refuses while the pull request's checks are failing.
- **You merge.** There is no merge command.
- **A red base is caught first.** `start` runs the checks on the base before any edit, and refuses when one already fails.
- **The result says where to look first.** Its `attention:` line names a changed check script, CI config, lockfile, deleted test, or existing test that lost lines. A ticket that touches one cannot waive the review.
- **One result format.** Every session ends with the same short block, whether you ran it by hand or a bot launched it.

## Install

Pick one method.

**Any agent (Claude Code, Cursor, Antigravity, Codex, ...)** with [skills.sh](https://skills.sh/thitinan147/jtek-skill):

```bash
npx skills add thitinan147/jtek-skill
```

**Claude Code plugin:**

```text
/plugin marketplace add thitinan147/jtek-skill
/plugin install jtek@jtek-skill
```

Requirements: `git` 2.31 or later, Python 3.10 or later, and an agent with a Notion tool for the board. `gh` is optional. It is used only to read a pull request's state, head commit, and CI result.

## Set up the board

The board is one Notion database. Connect the Notion tool in your agent (in Claude Code: `/mcp`, then Notion), and create the database with the properties in [notion.md](skills/jt-work/references/notion.md). An agent with the tool can create it for you.

## Set up a repository

```bash
python3 <skill-dir>/scripts/jtek.py init
```

This writes `jtek.json`. Fill in one command per check, delete the ones the project does not have, and commit the file on the base branch:

```json
{"setup": "npm ci", "checks": {"lint": "npm run lint", "types": "npx tsc --noEmit", "test": "npm test", "verify": "npx playwright test"}}
```

Then run the `jt-harness` skill once. It writes `.jtek/` (how to run and drive the app, and a feature map) and proposes the `verify` check. Do this before agents work tickets: without it, a passing check only means the code compiles.

`jtek.json` and `.jtek/` are all jtek adds to the repository. Tickets live in Notion. Claims, logs, and results live under the git directory and are never committed. Details: [setup.md](skills/jt-work/references/setup.md).

## Use it

| You want to | Do this |
|---|---|
| Add a ticket | Write a page on the board with `Goal` and `Done when`, and set Status to Todo |
| Work a ticket | `/jt-work T-12`, or `/jt-work <Notion page link>` |
| Work a few small, related tickets | `/jt-work T-12 T-13 T-14` |
| Give the verdict a ticket needs | `/jt-review T-12` in a fresh session |
| Fix a pull request after CI or review comments | set the page back to Todo, then `/jt-work T-12` |
| Ask what each open ticket needs, or which are merged | see [starting-sessions.md](skills/jt-work/references/starting-sessions.md) |
| Give a ticket back | `jtek.py release T-12` |

A program that starts sessions runs the same commands. It reads the `jtek-result` block at the end of the session to decide what to do next.

## Skills

| Step | Skill | What it does |
|---|---|---|
| Start, check, stop | `jt-work` | Claims the ticket, creates the worktree, runs the declared checks, and keeps the order of the steps in a playbook for a feature, a bug, or a refactor |
| Understand | `jt-understand` | Reads the ticket and the code, and names how each `Done when` item will be seen working |
| Build | `jt-build` | Makes the smallest change with tests, reusing what the codebase already has |
| A check fails | `jt-debug` | Finds the cause before changing code, and stops after three failed runs |
| See it work | `jt-verify` | Runs the real thing and reports only what was seen |
| Clean up | `jt-cleanup` | Removes debug output, unused code, and comments that repeat the code |
| Ship | `jt-ship` | Opens the pull request with the proof for each item, and moves the ticket to Review |
| Second look | `jt-review` | A session that did not write the change tries to break it, and records the verdict |
| The pull request needs work | `jt-babysit` | Clears conflicts, failing CI, and review comments, and never merges |
| After a correction | `jt-learn` | Turns a repeated mistake into a type, a lint rule, a fix to old examples, or a new check, and keeps a small rule table |
| Once per repository | `jt-harness` | Builds the way to run and observe the real app: a verify guide, a feature map, and the `verify` check |

Each skill also works on its own, for example `/jt-verify` on any change. Install the whole set: the script lives in `jt-work` and `jt-review`, so a step skill installed alone cannot run `jtek.py`.

## Statuses

| Status | Meaning | Who sets it |
|---|---|---|
| Backlog | Written down, not released | You |
| Todo | Released for an agent | You only |
| In Progress | A session has claimed it | The session, after `jtek.py start` |
| Review | Checks pass, verdict is PASS, evidence saved, pull request open | The session, after `jtek.py finish` |
| Done | Pull request merged | Read from the forge by `jtek.py sync` |
| Cancelled | Dropped | You |

Waiting, with `input` or `approval`, is a property of an In Progress ticket. It is not a status. The ticket format and the result block are in [ticket.md](skills/jt-work/references/ticket.md).

## Limits

- **Nothing here has been run against a real Notion workspace.** Reading the page and writing the `board:` line are steps the agent does with its Notion tool, and no agent has done them yet.
- **The script cannot check the board.** It cannot tell whether the page was copied faithfully or whether the `board:` line was written.
- **The script cannot tell who ran a command.** Nothing in code stops an agent from setting a page to Todo with its Notion tool, or from recording a verdict on its own change. The skills forbid both.
- **Claims are per machine.** Two machines can both read a page as Todo before either writes In Progress.
- Tested on macOS with Python 3.14. CI runs Python 3.10 and 3.13 on Linux.

See [SECURITY.md](SECURITY.md) for what the script runs on your machine.

## Coming from v25

Version 26 is a rewrite, not an upgrade.

- **Gone:** `jt-board`, `jt-add-task`, `jt-setup`, `jt-help`, the three `jt-spec-*` skills, `gate.py`, and `/jt-work --loop`. Choosing the next ticket and writing specs are no longer part of this set.
- **Not read any more:** `jt-queue/` and `.git/jt-queue/`. Open tasks there do not carry over. Rewrite the ones you still want as tickets.
- **New in the repository:** `jtek.json` and `.jtek/`. You can delete `jt-queue/` when nothing in it is needed.
- **The old set** is at commit `4c9d0f1` in the git history.

## License

MIT
