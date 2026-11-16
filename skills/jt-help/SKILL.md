---
name: jt-help
description: Lists every jt- command, what it does, the order to use them, and which are human-only. Writes nothing. Use when the user invokes /jt-help or asks which jt- command to run.
license: MIT
compatibility: Codex, Claude Code, Cursor, Grok Build, and Antigravity. Needs nothing beyond the installed skills.
metadata:
  author: Thitinan
  version: "24.8.0"
  short-description: List every jt- command and the order to use them
---

# jt-help

Show this page with the values filled in. Ask no questions and write no files.

Install one skill with `npx skills add thitinan147/jtek-skill --skill <name>` (a space before the name). As a Claude Code plugin the same commands are `/jtek:<name>`.

## Commands

| Command | Who | What it does |
|---|---|---|
| `/jt-help` | anyone | This list. Writes nothing. |
| `/jt-spec-split <flow>` | **human-only** | A flow → `<docs_root>/<flow>/map.md`, then one folder per story the PO confirms. |
| `/jt-spec-ac <work>` | **human-only** | Story, rules, acceptance criteria, and questions in `spec.md`. |
| `/jt-spec-handoff <work>` | **human-only** | Test steps for the tester, once no question blocks AC. |
| `/jt-board [<flow>]` | **human-only** | FigJam-style `board.html`. Does not edit the specs. |
| `/jt-setup` | human confirms | Write `jt-queue/board.md` after the human confirms every command. |
| `/jt-add-task` | spec approval covers derived tasks | Agree `brief.md`, then draft tasks. The gate's `brief` and `add-task` actions both use this command. |
| `/jt-work` | agent | Work ready tasks in board order, or one ticket id. No `--loop` flag. Cannot merge. |
| `/jt-review` | **human-only** | Inspect `review:` tasks. Write `merge:`, `send-back:`, or `drop:`. |

Human-only means the agent must not start that command itself. The human types it.

## Order

Spec, when a story is being agreed (optional, and not a task list):

1. `/jt-spec-split <flow>` when the input is a whole flow and there is no map yet
2. `/jt-spec-ac <work>` for each story
3. `/jt-spec-handoff <work>` once no question blocks `AC`
4. `/jt-board` any time, to look at the specs together

Queue, to implement something in git:

1. `/jt-setup` once per repo, until `jt-queue/board.md` exists
2. `/jt-add-task` to agree the brief and add tasks
3. `/jt-work` to work every ready task in board order (skipping blocked ones), or `/jt-work <ticket-id>` for one ticket, and hand each to `review:`
4. `/jt-review` for a human to close it

If you are not sure which spec step is next: no map for a flow → `/jt-spec-split`; missing story, rules, or AC → `/jt-spec-ac`; AC has no blocking question and test steps are missing → `/jt-spec-handoff`.

## Spec answers

Paste the text after the command, or give a path to a PDF or image. Leave out what you don't know; the skill asks.

- **Card:** what is needed (As a … I want … so that …), do / don't, and the ticket id the source already uses
- **Bug:** what happens now, how to reproduce, what should happen
- **Flow:** who does what on which screen, step by step, and what is in this round

In chat: pick an option, type your own, "Don't know / ask <role>", or "use the recommendations". In the file, without running the skill: write in the Answer cell. The PO approves AC by editing the line to `**approve:** ✅ <name> · <YYYY-MM-DD>`. The next run records each answer as a decision with that person's name.

Files: `<docs_root>/<work>/spec.md` (default `docs_root` is `scrum-spec`, because the checker reads that path and the marker `<!-- scrum-spec -->`). Optional `scrum-spec/config.md`: `docs_root`, `code_roots`, `roles`. Commit `spec.md` with the code. The spec commands do not break work into tasks, estimate, set priority or owners, write code, commit, push, or delete files.

## Queue files

Commit the queue files a teammate needs: `board.md`, `brief.md`, `tasks/<id>/task.md`, and `tasks/<id>/plan.md` (its `## decisions`). Leave local files uncommitted: `lessons.md` (notes for this agent), `.env` and private keys, and `.git/jt-queue/` (`approved-commands.json` must not travel in a commit; `logs/` can hold secrets; `attempts.json` is this machine's round counter). Humans approve the spec and the merge. One spec approval covers the tasks derived from it. Only `/jt-review`, run by a human, writes `merge:`. The agent never merges.

`/jt-work` is one command and has no `--loop` flag. With no id it works every ready task in board order and skips a blocked one. With one ticket id it works only that task.

A ticket id is copied from its source onto `ticket:` (`BOOK-12`, `#45`, a Notion id). The skills require one and do not check its shape. Commits and PR titles are `<type>(<scope>): <summary> (<ticket-id>)`. The task branch is `type/<ticket-id>-short-slug` (for example `feat/BOOK-12-room-search`). Legacy `task-<id>-<slug>` still works.

## Size

`small`, `medium`, and `large` scale the process. The agent sets `size:` when it creates the task or the spec. A human can change it on the task or with `size:` on the board line. `small` skips the spec and uses `/jt-add-task`. It runs affected tests only when the board sets `<AFFECTED_TEST_CMD>` or `<TEST_CMD>` contains `{files}`; otherwise it runs the full suite. `medium` is a short spec and the full gate. `large` is a full spec. The gate may raise the size (`escalate:`). It never lowers it. Standard `medium` and `large` need `## ai-review` before a human review. `small` and Quick skip it.

## Install before use

Show [references/install-before-use.md](references/install-before-use.md): official install links, jtek steps, and board slots. Copy-paste commands are in the repo README. Required method skills (superpowers, grill-me) have one-line fallbacks in each jt- `SKILL.md` when missing. Confirm at `/jt-setup`. After the gate passes, `/jt-work` invokes one fresh-context reviewer (`/interrogate`, else `/pr`, else `/ponytail-review` on high-risk). Do not stack reviewers. The AI does not approve or merge.
