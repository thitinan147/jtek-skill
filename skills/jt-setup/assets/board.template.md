# Board - `<REPO_NAME>`

The rules live in skills `jt-setup`, `jt-add-task`, and `jt-work`, version 24.9. The brief is `brief.md`. A task is `tasks/<id>/task.md`. A plan is `tasks/<id>/plan.md`. Commit this board, the brief, the task, and the plan. Do not commit `lessons.md` or `.git/jt-queue/`. Agent instructions live in `AGENTS.md` at the repo root.

queue:

`/jt-setup` inspects the open repo, shows this table with the source of each value, and waits for human confirmation before writing the board.

`<STACK_LOCK>` must include at least a language, a framework, the test command or the check kind, and what this repo must not use.

| Value | In this repo |
|---|---|
| `<TEST_CMD>` | |
| `<AFFECTED_TEST_CMD>` | |
| `<SETUP_CMD>` | |
| `<TYPECHECK_CMD>` | |
| `<LINT_CMD>` | |
| `<SECURITY_CMD>` | |
| `<VERIFY_CMD>` | |
| `<DENYLIST>` | |
| `<BROWSER_TOOL>` | |
| `<STACK_LOCK>` | |
| `<DIFF_LIMIT>` | |

Frontend and backend in separate repos: add a `## repos` section that names each repo and its path (see `contract.md` section 5). Without it the board covers this repo only.

`<SETUP_CMD>` prepares dependencies in the temporary worktree the gate creates for `task-<id>` (unless you are already on that branch) before tests and before start. An empty cell means do not run it.

`- [ ]` is open (`ask:`, `review:`, `send-back:`). `- [x]` is closed (`merge:` or `drop:`).

Task kinds are `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, and `revert`.

Empty `<DIFF_LIMIT>` means 400 added and deleted lines. A larger diff raises `size:`. A task line may say `size: small`, `size: medium`, or `size: large`; that overrides `size:` in the task. Empty means `medium`.

Empty `<AFFECTED_TEST_CMD>` means `small` runs the full `<TEST_CMD>`. Set it to narrow that run (`npx vitest --changed`, `npx jest --findRelatedTests {files}`, `pytest --testmon`), or put `{files}` in `<TEST_CMD>`. `{files}` is the affected test paths. When none can be named, `small` still runs the full suite.

The gate stops at the first failure: secret scan, denylist, typecheck, lint, tests, verify. Pre-commit hooks are an early warning, not a gate check. `/jt-setup` proposes `.pre-commit-config.yaml` and writes it only after you confirm. Empty `<SECURITY_CMD>`, or a program that is not installed, keeps the built-in secret check and never prints a secret value. Empty `<VERIFY_CMD>` skips that step. On a web app, `/jt-setup` proposes `<VERIFY_CMD>` `npx playwright test` and a `playwright.config.ts` with `updateSnapshots` `none` (no new snapshots in the same task). Empty `<DENYLIST>` uses `jt-queue/denylist.txt` when that file exists; if both are empty the step is skipped. A denylist line is `old -> replacement`.

Pick **first**, then **main**, then **later**.

## closed

no items

## first

no items

## main

no items

## later

no items

::: jtek:start
Agent instructions live in AGENTS.md at the repo root. CLAUDE.md imports that file. This board keeps the command table above.
::: jtek:end
