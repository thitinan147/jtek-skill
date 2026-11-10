# jtek-skill

**Let your coding agent work through a task queue, and let a script, not the agent, decide when work is ready for you to review.**

`jtek-skill` is a pair of [Agent Skills](https://agentskills.io/) for one Git repository, or for a frontend and a backend in two repos driven from one board. The agent takes tasks from a board, commits its work on a branch, and asks a deterministic Python gate ([`gate.py`](skills/jt-work-queue/scripts/gate.py)) to check the result: the diff, a passing test run, and review notes. Only when the gate agrees does the task move to `review:`. You hold the merge key: the agent can never merge.

*Constrain the outcome, not the agent.*

## Why

- Agents say "done" when they are not. Here "done" is something a script checks: tests ran and passed, every acceptance line has evidence, the diff stays inside the files the task named.
- You do not script every step. The agent chooses how; the gate checks what came out.
- Everything is plain text under `jt-queue/` in your repo: a board, a brief, and one folder per task. No service, no account, no dependencies beyond `git` and Python.

## Install

Pick **one** method. Installing both gives you every skill twice.

**Any agent (Claude Code, Codex, Cursor, ...)** with [skills.sh](https://skills.sh/thitinan147/jtek-skill):

```bash
# Pin a release so later changes cannot reach you unreviewed (recommended)
npx skills add thitinan147/jtek-skill#v22.1.0

# Or follow the default branch
npx skills add thitinan147/jtek-skill
```

Add `-g` to install for all your projects instead of the current one.

**Claude Code plugin:**

```text
# Pinned to a release (recommended)
/plugin marketplace add thitinan147/jtek-skill#v22.1.0
/plugin install jtek@jtek-skill
```

Without `#v22.1.0` the marketplace follows the default branch, and `/plugin update jtek@jtek-skill` pulls the latest.

As a plugin, the commands are also available as `/jtek:jt-work-queue` and `/jtek:jt-review-work`. Use those names if another skill has the same short name.

Then read [SECURITY.md](SECURITY.md): the gate runs your test command, so a human must approve it first. **New here? Read [Getting started](docs/getting-started.md)**, a walkthrough of one real round with the gate's actual output.

## Quick start

In a Git repository, ask your agent:

```text
/jt-work-queue
```

The agent looks at your repo, proposes a test command, and writes `jt-queue/board.md` once you approve. Then add work:

```text
/jt-work-queue Add rate limiting to POST /api/login
```

Run it again to work the next ready task. When a task reaches `review:`, you decide:

```text
/jt-review-work
```

(In Codex, use `$jt-work-queue` and `$jt-review-work`.)

## How it works

```text
Human + Agent (/jt-work-queue)                          Human only (/jt-review-work)
+----------------------------------------------------+  +------------------------------+
| 1. setup     Write board.md and gitignore jt-queue |  | Inspect diff, test evidence, |
| 2. brief     Agree this round in brief.md          |  | scope warnings, and UI shots |
| 3. add-task  Draft tasks/<id>/task.md              |  |                              |
| 4. do-task   Commit code on task-<id>              -->  merge:     (after landed)    |
|              Quick / Standard evidence             |  | send-back:  (fix & redo)     |
|              reach-review -> mark review:          <--  drop:       (cancel)         |
+----------------------------------------------------+  +------------------------------+
```

1. **Queue files stay local; code lives on `task-<id>`.** `jt-queue/` is gitignored, so your board is not committed or pushed.
2. **The gate checks before review.** The agent cannot mark a task `review:` itself. `Quick` tasks need the test command to pass. `Standard` tasks also need a `plan.md` whose evidence covers every `pass:` line and whose review cites the latest commit. After three failed rounds the gate tells the agent to ask you.
3. **You hold the merge key.** Only `/jt-review-work`, run by a human, can close or send back a task, and `merge:` is written only after the branch has landed.

| Command | Who | What it does |
|---|---|---|
| [`/jt-work-queue`](skills/jt-work-queue/SKILL.md) | Human or agent | Set up the board, capture a brief, add tasks, work the next ready task, hand off to `review:`. Cannot merge. |
| [`/jt-review-work`](skills/jt-review-work/SKILL.md) | **Human only** | Inspect `review:` tasks and their evidence, then `merge:`, `send-back:`, or `drop:`. |

## Documentation

- [Getting started](docs/getting-started.md): the words jtek-skill uses, and one real round from setup to merge
- [Usage guide](docs/usage.md): priorities, splitting work into tasks, task kinds, the `jt-queue/` layout, and [frontend and backend in two repos](docs/usage.md#5-frontend-and-backend-in-two-repos)
- [File and gate contract](skills/jt-work-queue/references/contract.md): every field the gate reads
- [Security and trust model](SECURITY.md)
- [Changelog](CHANGELOG.md) and [migrating from v20 or v21](MIGRATING.md)

## Platform support

| | Status |
|---|---|
| macOS, Linux | Supported. CI runs the tests on Ubuntu with Python 3.10 and 3.13. |
| Windows | **Not supported yet.** The gate uses POSIX process groups (`os.killpg`) and `fcntl`. Use WSL. |
| Claude Code | Tested: install from a release tag with skills.sh, and loading as a plugin. |
| Codex, Cursor, Grok Build, Antigravity | Follows the Agent Skills format and should work, but is not tested by the author. Reports are welcome. |

Needs `git` and Python 3.10 or later (standard library only). The GitHub CLI (`gh`) is optional.

## Security

`jtek-skill` runs shell commands on your machine (your test command and any task `start`/`click`). It is not a sandbox. A human must approve those exact commands with `gate.py approve-commands` first, and the gate refuses if they change. See [SECURITY.md](SECURITY.md) for the trust model, what leaves your machine, and how to report a vulnerability.

## Contributing

Issues and pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md). Run the tests with:

```bash
python3 -m unittest discover -s tests
```

## License

[MIT](LICENSE)
