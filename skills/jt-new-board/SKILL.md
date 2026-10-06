---
name: jt-new-board
description: Create card-loop/board.md, fill the command table from this repo, and write scanned skill names into the two rows. Use when the user runs /jt-new-board or asks to set up the card loop board. Do not ask the user to fill the table.
license: MIT
metadata:
  author: Thitinan
  version: "20"
  short-description: Create the board and fill it
---

# jt-new-board

1. If the open repo is not a git repo, stop and say to run `git init` first.
2. If HEAD is not on a branch, stop and say to check out the branch that will hold the queue.
3. If `card-loop/board.md` already exists, stop and say it is already there.
4. Copy `assets/board.template.md` from skill `jt-card-gate` to `card-loop/board.md`.
5. Write the current branch name after the `queue:` line, and replace `<REPO_NAME>` in the file heading with this repo's folder name.
6. Fill the table from the open repo. The human does not fill this table.

Use the package manager from the lockfile that exists. `pnpm-lock.yaml` means `pnpm`. If that file is absent and `yarn.lock` exists, use `yarn`. If both are absent and `bun.lock` or `bun.lockb` exists, use `bun`. Otherwise use `npm`.

| Cell | Write the first value you find |
|---|---|
| `<SETUP_CMD>` | The command that prepares the environment or installs dependencies. `pnpm install --frozen-lockfile` when `pnpm-lock.yaml` exists, `yarn install --frozen-lockfile` when `yarn.lock` exists, `bun install --frozen-lockfile` when `bun.lock` or `bun.lockb` exists, `npm ci` when `package-lock.json` exists, `npm install` when `package.json` exists, `cargo build` when `Cargo.toml` exists, `go mod download` when `go.mod` exists, and `uv sync --frozen` or `poetry install` for the Python tool in use. Otherwise leave the cell empty. |
| `<TEST_CMD>` | `scripts.test` in `package.json` becomes `<manager> test`. If that is absent, use `cargo test` when `Cargo.toml` exists. If that is absent, use `go test ./...` when `go.mod` exists. If that is absent, use `pytest` when `pyproject.toml` has pytest. If none of the four exist, write `no-suite`. |
| `<TYPECHECK_CMD>` | `scripts.typecheck` becomes `<manager> run typecheck`. If that is absent and `tsconfig.json` exists, write `<manager> exec tsc --noEmit`. If that is absent and `go.mod` exists, write `go vet ./...`. Otherwise leave the cell empty. |
| `<LINT_CMD>` | `scripts.lint` becomes `<manager> run lint`. Otherwise leave the cell empty. |
| `<BROWSER_TOOL>` | Write the first name that can run as a command. If `playwright` is in `package.json` or a `playwright` command is on PATH, write `playwright`. If not, check `cypress` the same way. If neither is found, leave the cell empty. Do not put a session or MCP browser name, because the gate only checks that this cell is non-empty and then runs the `click:` heading as a shell command. |
| `<STACK_LOCK>` | One line, `language · framework or no framework · the command in <TEST_CMD> · banned: not declared in the project files`. Read the language and framework from `package.json`, `go.mod`, `pyproject.toml`, or `Cargo.toml`. |

7. Find skill names under **Search** in `skills/jt-find-skills/SKILL.md`. Write the names that heading produces into the cells, at most three names per group. Write `<TEK_SKILLS>` and `<REPO_SKILLS>` separated by `, `. If a group has no names, leave that cell empty.
8. Show the status table from **Search** in the reply. The install command appears only on an `install this` row. Do not run that command.
9. Ask once what the paired repo is named. Write the answer on the `pair:` line that already exists on this repo's board. That line is the name the human answered, or the word `none`. Use only the words the human answered. Do not invent a repo name. Do not ask again when a later card opens. Do not create `card-loop/paired.md` because of this line, and do not create a board in another repo.

Do not call `/jt-do-work`.

Done when `queue:` is a real branch name, the `pair:` line is the name the human answered or the word `none`, the `<TEST_CMD>` and `<STACK_LOCK>` cells are non-empty, and both skill cells have names from **Search**.
