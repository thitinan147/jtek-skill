# Security

## Reporting a vulnerability

Please report suspected vulnerabilities privately through GitHub: **Security tab → Report a vulnerability** on this repository. Do not open a public issue for an unfixed vulnerability.

## Trust model (read before installing)

`jt-skill` is a work queue for coding agents. It is **not a sandbox**. Its Python gate (`skills/jt-work-queue/scripts/gate.py`) runs shell commands on your machine, so these commands are code that you are trusting:

| Command | Where it is declared | Run by |
|---|---|---|
| `TEST_CMD`, `SETUP_CMD` | `jt-queue/board.md` | `gate.py reach-review` (in the task worktree) |
| `start`, `click`, `port`, `wait` | `jt-queue/tasks/<id>/task.md` | `gate.py reach-review` and `gate.py screen-check`, for tasks that declare `screen: yes` |

How this is kept in check:

- On first setup, the skill shows each detected command with its source (for example `TEST_CMD = npm test` from `package.json`) and **waits for a human to confirm** before writing `jt-queue/board.md`.
- **Approval is enforced by the gate.** `gate.py reach-review` and `gate.py screen-check` refuse (`commands-unapproved`, `commands-changed`, `next: stop`) unless the current `TEST_CMD`/`SETUP_CMD` and the task's `start`/`click` match what a human approved with `gate.py approve-commands --id <id>`. Edits to those commands after approval, committed or not, are refused and nothing is run. The approval is a hash stored in `.git/jt-queue/approved-commands.json`, so it never travels in a branch, commit, or pull request: a checked-out PR from someone else starts out unapproved.
- **Limit of that control:** `approve-commands` is a command like any other. An agent that disobeys its instructions and runs it itself defeats the check, because the gate cannot tell who typed it. Do not add `approve-commands` to any "always allow" list in your agent, so each use shows up as a prompt you must accept.
- Still treat `jt-queue/board.md` and `jt-queue/tasks/<id>/task.md` like a `Makefile` or CI config: review changes to them, including in pull requests from others, before you approve.
- Commands run with your full environment (including any tokens in it) and with `node_modules/.bin` prepended to `PATH`. Run the gate in a container or throwaway environment for repositories you do not trust.
- Test and setup commands have time limits (`JT_TEST_TIMEOUT`, capped at 3600 s). `JT_GH_TIMEOUT` is capped the same way.
- The gate refuses task IDs that are not `^\d+(\.\d+)*$`, so task IDs cannot traverse paths.

## What the skills do outside the repository

- `gh` is called read-only (`gh pr view`, `gh pr list`) to find out whether a task branch has landed.
- On handoff, `/jt-work-queue` **pushes `task-<id>` and opens a draft PR** (`gh pr create --draft`) when a git remote exists. With no remote it stays local. This sends your code to that remote on purpose; do not use the skill with a remote you do not want branches pushed to. A gitignored `jt-queue/` is not part of that push.
- The skills never merge. `merge:` and `drop:` are written only by the human through `/jt-review-work`.
- No network calls are made by the scripts apart from `gh` and a connection check against `127.0.0.1` for screen checks. Setup commands you configure (for example `npm install`) can of course use the network.

## Treating repository text as data

Both skills tell the agent to treat board, task, plan, diff, commit and PR text as data and never as instructions. This is an instruction to the model, not a technical control: a model can still be fooled. The human review in `/jt-review-work` is the real control.

## Human-only command

`/jt-review-work` is marked human-only with `disable-model-invocation: true` (Claude Code) and `allow_implicit_invocation: false` (Codex, `agents/openai.yaml`). Other agents do not read those fields; there the rule rests on the skill text alone. That field is outside the Agent Skills specification, so `skills-ref validate` reports it for this skill.

## Scanning

CI runs the unit tests, `bandit`, the Agent Skills validator, and SkillSpector. SkillSpector findings that were reviewed and judged false positives are listed with reasons in [`.skillspector-baseline.yaml`](.skillspector-baseline.yaml). The three `shell=True` calls are the behavior documented above. They carry a `# nosec B602` marker and an intent comment; note that SkillSpector lowers its own `shell=True` finding when such a comment is present, so a `CAUTION` score does **not** mean the skill runs no shell commands. Use this file, not the score, to judge that.

## Releases

Install a tagged release rather than the default branch, so that a later change cannot reach you unreviewed. See [CHANGELOG.md](CHANGELOG.md).
