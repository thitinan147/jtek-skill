# jtek-skill

**Let your coding agent draft a spec, work a task queue, and stop at review until a script, not the agent, says the work is ready.**

`jtek-skill` is a set of [Agent Skills](https://agentskills.io/). One group drafts a story into `spec.md` (acceptance criteria and test steps) and leaves every decision with a person. The other runs a task queue in `jt-queue/`: the agent commits on a branch, and a deterministic Python gate ([`gate.py`](skills/jt-work/scripts/gate.py)) checks the diff, tests, and lint and typecheck when the board sets them. Only then does the task move to `review:`. You hold the merge key.

*Constrain the outcome, not the agent. The AI proposes. People decide.*

## Why

- Agents say "done" when they are not. Here "done" is something a script checks.
- You do not script every step. The agent chooses how; the gate checks what came out.
- Spec text is a fact with a source, a proposal, or a question. An approval or a decision signed by an AI fails `check.py`.
- Queue files are plain text under `jt-queue/`. Spec files are plain Markdown. No service and no account. Dependencies are `git` and Python.

## Install

Pick **one** method. Installing both the plugin and the skills CLI gives you every skill twice.

**Any agent (Claude Code, Codex, Cursor, ...)** with [skills.sh](https://skills.sh/thitinan147/jtek-skill):

```bash
# Everything, pinned (recommended)
npx skills add thitinan147/jtek-skill#v24.0.0

# Or follow the default branch
npx skills add thitinan147/jtek-skill
```

Add `-g` to install for all your projects instead of the current one.

**Claude Code plugin** (installs the whole set; commands are also `/jtek:<name>`):

```text
/plugin marketplace add thitinan147/jtek-skill#v24.0.0
/plugin install jtek@jtek-skill
```

Without `#v24.0.0` the marketplace follows the default branch.

### Install what you need

Each skill is a folder of its own. The name is a separate argument, with a space: `--skill jt-help`. (`--skill=jt-help` is ignored by current installers and installs every skill.)

| Skill | Command | Who | Install just this |
|---|---|---|---|
| [`jt-help`](skills/jt-help/SKILL.md) | `/jt-help` | anyone | `npx skills add thitinan147/jtek-skill --skill jt-help` |
| [`jt-spec-split`](skills/jt-spec-split/SKILL.md) | `/jt-spec-split` | **human-only** | `npx skills add thitinan147/jtek-skill --skill jt-spec-split` |
| [`jt-spec-ac`](skills/jt-spec-ac/SKILL.md) | `/jt-spec-ac` | **human-only** | `npx skills add thitinan147/jtek-skill --skill jt-spec-ac` |
| [`jt-spec-handoff`](skills/jt-spec-handoff/SKILL.md) | `/jt-spec-handoff` | **human-only** | `npx skills add thitinan147/jtek-skill --skill jt-spec-handoff` |
| [`jt-board`](skills/jt-board/SKILL.md) | `/jt-board` | **human-only** | `npx skills add thitinan147/jtek-skill --skill jt-board` |
| [`jt-setup`](skills/jt-setup/SKILL.md) | `/jt-setup` | human confirms the commands | `npx skills add thitinan147/jtek-skill --skill jt-setup` |
| [`jt-add-task`](skills/jt-add-task/SKILL.md) | `/jt-add-task` | human approves each task | `npx skills add thitinan147/jtek-skill --skill jt-add-task` |
| [`jt-work`](skills/jt-work/SKILL.md) | `/jt-work` | agent | `npx skills add thitinan147/jtek-skill --skill jt-work` |
| [`jt-review`](skills/jt-review/SKILL.md) | `/jt-review` | **human-only** | `npx skills add thitinan147/jtek-skill --skill jt-review` |

Pin the same way: `npx skills add thitinan147/jtek-skill#v24.0.0 --skill jt-work`.

In Codex the commands are `$jt-help`, `$jt-setup`, and so on.

Then read [SECURITY.md](SECURITY.md). The gate runs your test command, so a human must approve it first. **New here? Read [Getting started](docs/getting-started.md).** Spec drafts: [Spec documents](docs/spec.md).

## Quick start

```text
/jt-help
/jt-setup
/jt-add-task Add rate limiting to POST /api/login
/jt-work
/jt-review
```

A story, before or beside the queue:

```text
/jt-spec-split room-booking
/jt-spec-ac BOOK-12-book-room
/jt-spec-handoff BOOK-12-book-room
/jt-board room-booking
```

## How it works

```text
Spec (human types the command)          Queue
/jt-spec-split   flow → story map        /jt-setup      board.md, human confirms commands
/jt-spec-ac      story, rules, AC        /jt-add-task   brief, then tasks
/jt-spec-handoff test steps              /jt-work       ready tasks, in order
/jt-board        board.html              /jt-review     human: merge / send-back / drop
```

1. **Queue files stay local; code lives on a branch.** `jt-queue/` is gitignored. `/jt-work` is one command and has no `--loop` flag. With no id it works every ready task in board order and skips a blocked one. `/jt-work BOOK-12` works only that ticket. Spec files live under `scrum-spec/` (or `docs_root`) and are meant to be committed. The folder name and the marker `<!-- scrum-spec -->` stay, because `check.py` reads them. The commands do not use that word.
2. **The gate checks before review.** The agent cannot mark a task `review:` itself. `Quick` tasks need the test command to pass. `Standard` tasks need a diff outside `jt-queue/`, a `plan.md` whose evidence covers every `pass:` line, and a review that cites the latest commit. When the board sets `<LINT_CMD>` or `<TYPECHECK_CMD>`, those must pass too.
3. **You hold the merge key.** Only `/jt-review`, run by a human, can close or send back a task. The spec commands never commit.

| Command | Who | What it does |
|---|---|---|
| [`/jt-help`](skills/jt-help/SKILL.md) | anyone | Lists every command, the order, and which are human-only. |
| [`/jt-spec-split`](skills/jt-spec-split/SKILL.md) | **human-only** | Split a flow into a story map and one folder per confirmed story. |
| [`/jt-spec-ac`](skills/jt-spec-ac/SKILL.md) | **human-only** | Draft story, rules, acceptance criteria, and questions. |
| [`/jt-spec-handoff`](skills/jt-spec-handoff/SKILL.md) | **human-only** | Write test steps once nothing blocks the AC. |
| [`/jt-board`](skills/jt-board/SKILL.md) | **human-only** | Write a FigJam-style `board.html`. |
| [`/jt-setup`](skills/jt-setup/SKILL.md) | human confirms | Write `jt-queue/board.md`. |
| [`/jt-add-task`](skills/jt-add-task/SKILL.md) | human approves | Agree the brief, then add tasks. |
| [`/jt-work`](skills/jt-work/SKILL.md) | agent | Work ready tasks in order, or one ticket id. Cannot merge. |
| [`/jt-review`](skills/jt-review/SKILL.md) | **human-only** | Inspect `review:` and write `merge:`, `send-back:`, or `drop:`. |

## Names

A ticket keeps the id it already has. Jira `BOOK-12`, GitHub `#45`, and a Notion id are all fine. The skills require an id and do not check its shape.

- Commit and pull request title: `type(scope): summary (<ticket-id>)`, for example `feat(booking): add room search API (BOOK-12)`. The type is the task kind (`feat`, `fix`, `refactor`, `test`, `docs`, `chore`, and the other kinds the board already uses). Scope is optional.
- Branch to aim for: `type/<ticket-id>-short-slug`, for example `feat/BOOK-12-room-search` (type and slug are lowercase, with hyphens; the ticket id is copied as written). `gate.py` still only finds `task-<id>` or `task-<id>-<slug>`, so `/jt-work` still creates that branch. Teaching the gate the conventional branch name is a later change.

## Use together with

These are optional. This repo does not install them, and none of them replaces the gate or the human merge.

- **[superpowers](https://github.com/obra/superpowers)** (brainstorm, TDD, debug, verify). Use it while `/jt-work` implements. `reach-review` still decides whether the task can move to `review:`.
- **poteto's pstack** (`/poteto-mode` and the skills around it). Use it when you want that workflow to do the engineering. `/jt-work` still runs the gate before review, and `/jt-review` is still the only command that records `merge:`.
- **[ponytail](https://github.com/DietrichGebert/ponytail)** (write only the code the task needs). It can shape how `/jt-work` implements. The gate still requires the tests, the evidence, and the diff.
- **Semgrep and Dependabot, through the board.** Put the project's Semgrep command in `<LINT_CMD>` (and a dependency audit in `<TEST_CMD>` or `<LINT_CMD>` if you want the gate to run it). On a Standard task, `reach-review` runs a non-empty `<LINT_CMD>` and requires exit 0. A human approves that exact command with `gate.py approve-commands` first. Dependabot itself is a GitHub app: its pull requests are not merged by these skills.

## Migration from `/scrum-spec` and the old queue names

v24 is breaking for command names. Queue files and spec files do not need a rewrite. The marker `<!-- scrum-spec -->`, `scrum-spec/config.md`, and every `check.py` rule are unchanged. `gate.py` still checks the same things; `next` prints the new command for each action.

| Old | New |
|---|---|
| `/scrum-spec` or `/scrum-spec help` | `/jt-help` |
| `/scrum-spec split` | `/jt-spec-split` |
| `/scrum-spec ac` | `/jt-spec-ac` |
| `/scrum-spec handoff` | `/jt-spec-handoff` |
| `/scrum-spec board` | `/jt-board` |
| `/jt-work-queue` when there is no board | `/jt-setup` |
| `/jt-work-queue` to agree the brief or add a task | `/jt-add-task` |
| `/jt-work-queue` to implement | `/jt-work` |
| `/jt-review-work` | `/jt-review` |
| `/jtek:jt-work-queue`, `/jtek:jt-review-work` | `/jtek:jt-setup`, `/jtek:jt-add-task`, `/jtek:jt-work`, `/jtek:jt-review` |

The gate's `brief` and `add-task` actions both name `/jt-add-task`. There is no separate brief command. Details: [MIGRATING.md](MIGRATING.md).

## Documentation

- [Getting started](docs/getting-started.md): one queue round, with the gate's output
- [Spec documents](docs/spec.md): story map, acceptance criteria, test steps, the checker
- [Usage guide](docs/usage.md): priorities, task kinds, two repos
- [File and gate contract](skills/jt-work/references/contract.md)
- [Security and trust model](SECURITY.md)
- [Changelog](CHANGELOG.md) and [migrating](MIGRATING.md)

## Platform support

| | Status |
|---|---|
| macOS, Linux | Supported. CI runs the tests on Ubuntu with Python 3.10 and 3.13. |
| Windows | **Not supported yet.** The gate uses POSIX process groups (`os.killpg`) and `fcntl`. Use WSL. |
| Claude Code | Install from a release tag with skills.sh, or load the plugin. |
| Codex, Cursor, Grok Build, Antigravity | Follows the Agent Skills format. Reports are welcome. |

Needs `git` and Python 3.10 or later (standard library only). The GitHub CLI (`gh`) is optional. Large PDFs need poppler (`poppler-utils`).

## Security

`jtek-skill` runs shell commands on your machine (your test, lint, and typecheck commands, and any task `start`/`click`). It is not a sandbox. A human must approve those exact commands with `gate.py approve-commands` first. `check.py` only reads files. `board.py` writes `board.html`, and that page loads Google Fonts when opened. See [SECURITY.md](SECURITY.md).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Run the tests with:

```bash
python3 -m unittest discover -s tests
```

## License

[MIT](LICENSE)
