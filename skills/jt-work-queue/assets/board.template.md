# Board - `<REPO_NAME>`

The rules live in skill `jt-work-queue` version 21. The brief is `brief.md`. A task is `tasks/<id>/task.md`. A plan is `tasks/<id>/plan.md`.

queue:

`/jt-work-queue` inspects the open repo, shows this table with the source of each value, and waits for human confirmation before writing the board.

`<STACK_LOCK>` must include at least a language, a framework, the test command or the check kind, and what this repo must not use.

| Value | In this repo |
|---|---|
| `<TEST_CMD>` | |
| `<SETUP_CMD>` | |
| `<TYPECHECK_CMD>` | |
| `<LINT_CMD>` | |
| `<BROWSER_TOOL>` | |
| `<STACK_LOCK>` | |
| `<REPO_SKILLS>` | |

`<SETUP_CMD>` prepares dependencies in the card worktree before tests and before start. An empty cell means do not run it.

`<REPO_SKILLS>` names skills used to review code diffs on `Standard` tier cards before `review:`. An empty cell means the agent reviews the diff directly.

`- [ ]` is open (`ask:`, `review:`, `send-back:`). `- [x]` is closed (`merge:` or `drop:`).

Ticket kinds are `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, and `revert`.

Pick **first**, then **main**, then **later**.

## closed

no items

## first

no items

## main

no items

## later

no items
