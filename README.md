<h1 align="center">jtek</h1>

<p align="center">
  <em>One ticket in. One pull request out. You merge.</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-26.2.0-111111?style=flat-square" alt="Version 26.2.0">
  <img src="https://img.shields.io/badge/skills-11-111111?style=flat-square" alt="11 skills">
  <img src="https://img.shields.io/badge/script-Python%20stdlib-111111?style=flat-square" alt="One script, Python standard library only">
  <img src="https://img.shields.io/badge/board-Notion-111111?style=flat-square" alt="The board is a Notion database">
  <img src="https://img.shields.io/badge/license-MIT-111111?style=flat-square" alt="MIT license">
</p>

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/flow-dark.svg">
    <img src="assets/flow.svg" width="880" alt="jtek flow: you set a ticket to Todo in Notion, one session builds it in its own worktree and passes the checks, a second session that did not write it gives a verdict, a pull request opens with evidence, and you merge.">
  </picture>
</p>

---

You know the pull request. Forty files. "All tests pass." The feature does not start.

An agent will tell you the work is done. jtek does not take its word. A ticket reaches Review only when the project's own checks pass on the current commit, a session that did not write the change has tried to break it, and every `Done when` item has a line that says what was run and seen, or why it was not run.

Then it stops. You read the evidence. You merge.

## What you get back

Every session ends with the same block, whether you started it by hand or a bot did.

```text
jtek-result
id: T-12
status: Review
outcome: review
waiting: -
checks: lint=pass types=pass test=pass verify=pass @1a2b3c4
verdict: PASS by reviewer @1a2b3c4
pr: https://github.com/you/app/pull/41
ci: pass
evidence: .git/jtek/work/T-12/evidence.md (3 seen, 0 not run)
attention: -
branch: jtek/T-12
source: https://www.notion.so/...
note: the human reviews and merges; jtek never merges.
board: Status=Review; Waiting=; PR=https://github.com/you/app/pull/41; comment=result+evidence
```

Read `evidence` first, then `attention`, then the diff. `attention` names files that decide whether checks pass: a changed check script, CI config, a lockfile, `Makefile` or `package.json`, a deleted test, or an existing test that lost lines. It works from a list of known names. Add your project's own with `watch` in `jtek.json`.

## How it works

1. **You write a ticket** as a page on a Notion board, with `Goal` and `Done when`, and set it to Todo.
2. **A session takes it.** The agent reads the page with its Notion tool and runs `jtek.py start`. The script claims the ticket, creates a worktree, and runs the checks on the base first. A base that is already red is refused.
3. **It works in steps.** Understand, build, check, see it work, clean up, ship. Each step is one small skill, and `jt-work` keeps the order.
4. **The project's checks run.** They come from `jtek.json` on the base branch. An edit in the worktree cannot weaken them.
5. **A second session gives the verdict.** It did not write the change, and it reads only the ticket and the diff. A verdict belongs to the content of the change, so any edit, even of whitespace, needs a new one.
6. **A pull request opens** with the evidence as its body. The script prints a `board:` line, and the agent writes exactly that on the Notion page.
7. **You merge.** There is no merge command.

If the agent is stuck or has a question, it stops and puts the question on the page. You answer and set the ticket back to Todo.

`jtek.py` never talks to Notion. The agent reads and writes the board with its own Notion tool, and the script says what to write.

## The prompt

The whole set is eleven skills and one Python script. Start with [`skills/jt-work/SKILL.md`](skills/jt-work/SKILL.md): it is the router, and the only skill that knows the order. The script is [`skills/jt-work/scripts/jtek.py`](skills/jt-work/scripts/jtek.py), standard library only. Two small files beside it, `launcher.py` and `doctor.py`, hold the commands that are not part of working a ticket.

It uses no other skill set.

## Install

**Any agent** (Claude Code, Cursor, Antigravity, Codex, ...) with [skills.sh](https://skills.sh/thitinan147/jtek-skill):

```bash
npx skills add thitinan147/jtek-skill
```

**Claude Code**, as two separate prompts:

```
/plugin marketplace add thitinan147/jtek-skill
```
```
/plugin install jtek@jtek-skill
```

Install the whole set. The script lives in `jt-work` and `jt-review`, so a step skill installed alone cannot run it.

Needs `git` 2.31 or later, Python 3.10 or later, and an agent with a Notion tool. With GitHub, you also need `gh`, signed in: the agent opens the pull request with it, and the script reads the pull request's state and CI result with it.

## Set up

Three things, once. For every step with what you should see, from connecting Notion to the first merged ticket, follow **[GETTING-STARTED.md](GETTING-STARTED.md)**.

**1. The board.** Create one Notion database with the properties in [notion.md](skills/jt-work/references/notion.md): eleven of them, and the names and types must match. Then connect the Notion tool in your agent and give it access to that database. In Claude Code: `/mcp`, then Notion.

Keep the database's link: it goes into `jtek.json` in the next step.

**2. The checks.** In each repository, ask the agent:

```text
Run jtek.py init in this repository.
```

The script is inside the installed `jt-work` skill, and the agent knows where that is. This writes `jtek.json`. Set `board` to the database's link and `name` to the name tickets use for this repository, fill in one command per check, delete the ones the project does not have, and commit the file on the base branch:

```json
{"board": "https://www.notion.so/...", "name": "web", "setup": "npm ci", "checks": {"lint": "npm run lint", "types": "npx tsc --noEmit", "test": "npm test", "verify": "npx playwright test"}}
```

A command is one program with arguments. Put a pipeline in a script. Ask the agent to run `jtek.py doctor`: it says what is still missing.

**3. The harness.** Run the `jt-harness` skill once per repository. It writes `.jtek/` (how to run and drive the real app, and a feature map) and proposes the `verify` check. Without it, a passing check only means the code compiles.

`jtek.json` and `.jtek/` are all jtek adds to a repository. Claims, logs, and results live under the git directory and are never committed. Details: [setup.md](skills/jt-work/references/setup.md).

## Commands

| You want to | Do this |
|---|---|
| Add a ticket | Write a page on the board with `Goal` and `Done when`, and set Status to Todo |
| Work a ticket | `/jt-work T-12`, or `/jt-work <Notion page link>` |
| Work a few small, related tickets | `/jt-work T-12 T-13 T-14` |
| Give the verdict a ticket needs | `/jt-review T-12` in a fresh session |
| Answer a question, or ask for a fix | Write on the page, set Status to Todo, then `/jt-work T-12` |
| Give a ticket back, or clean up a start that was interrupted | Ask the agent to run `jtek.py release T-12`. The branch is kept, and the next start goes on from it |
| Let something else start the sessions | [starting-sessions.md](skills/jt-work/references/starting-sessions.md) |

Something has to choose the next ticket and start the session. That is you, a Claude Code session, or a bot. All three ask the same question, `jtek.py next`, and do what it answers: `work`, `review`, or nothing.

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


Each skill also works on its own, for example `/jt-verify` on any change.

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

## Not proven yet

No numbers here. There are none to show yet.

- **Proven:** the script, by 96 tests, and one outside review whose findings are fixed and tested. The main path, by three fresh-agent runs on toy repositories, before the board moved to Notion.
- **Not proven:** anything with a real Notion workspace, a real repository, or a real pull request. Reading the page and writing the `board:` line are steps no agent has done yet.
- **Never run:** `jt-harness`, `jt-babysit`, `jt-learn`, and the refactor playbook.

Use it by hand, one ticket at a time, before you let anything start sessions for you.

## FAQ

**Does it merge?**
No. There is no command for it.

**Can the agent mark its own work as done?**
It can say so. The script wants the checks, the evidence, and a verdict for the current content of the change.

**Can the agent weaken a check to pass?**
Not by editing `jtek.json`: the script reads it from the base branch. What a check runs is read from the worktree, so a ticket can change it. The result names such a file on the `attention:` line when it is a known name or on your `watch` list, and that ticket cannot waive the review. A file the list does not know is not named.

**Can it give the verdict on its own change?**
The script cannot tell who ran a command. The skills forbid it, and nothing in code stops an agent that ignores them. See [SECURITY.md](SECURITY.md).

**Why does the script not talk to Notion?**
Your agent already has a Notion tool, and the script would need a token of its own. So the agent reads the page, and the script prints what to write back. The cost: the script cannot check that the page was copied faithfully or that the line was written.

**Do I need the second session for a one-line fix?**
Set Review to `human` on that ticket. The waiver is ignored when the change touches a file on the `attention:` line.

**Two repositories, one feature?**
Two tickets, joined by a contract file and a check on each side. [two-repos.md](skills/jt-work/references/two-repos.md).

**Is this a software factory?**
It is the part inside one session. What picks the next ticket is up to you.

## Coming from v25

Version 26 is a rewrite, not an upgrade.

- **Gone:** `jt-board`, `jt-add-task`, `jt-setup`, `jt-help`, the three `jt-spec-*` skills, `gate.py`, and `/jt-work --loop`. Choosing the next ticket and writing specs are no longer part of this set.
- **Not read any more:** `jt-queue/` and `.git/jt-queue/`. Open tasks there do not carry over. Rewrite the ones you still want as tickets on the board.
- **New in the repository:** `jtek.json` and `.jtek/`. You can delete `jt-queue/` when nothing in it is needed.
- **The old set** is at commit `4c9d0f1` in the git history.

## License

[MIT](LICENSE).
