# Setup for a repository

The board is set up once, as [notion.md](notion.md) says. Then two things go into each repository: `jtek.json`, and the `.jtek/` folder (how to run and drive the app and a feature map, written by the `jt-harness` skill, and a rule table kept by the `jt-learn` skill). Tickets, claims, logs, and results stay under the git directory and are never committed.

1. Run `jtek.py init`. It writes a template:

   ```json
   {"notion": "", "setup": "", "checks": {"secrets": "", "lint": "", "types": "", "test": "", "audit": "", "verify": ""}}
   ```

   **`notion`** is the id or the link of the board database. The token is not kept here: it is `NOTION_TOKEN` in the environment.

   **`setup`** installs dependencies in a new worktree, for example `npm ci` or `uv sync`. A new worktree has none, so without it the checks fail before any edit. Leave it empty when nothing is needed.

2. Fill in one command per check, using commands the project already has. Delete a check the project does not have. **`secrets`** is a secret scanner such as `gitleaks`, first because it is the fastest and the costliest to miss. **`audit`** is the dependency audit of your package manager. Order matters: checks run top to bottom and stop at the first failure, so put the fast ones first.
3. A command is one program with arguments. It runs in the ticket's worktree with `JTEK_TICKET` and `JTEK_WORKTREE` set, so a command can pick its own port or data folder when several tickets run at once. It does not receive `NOTION_TOKEN`. Shell operators such as `&&` and `|` do not work. Put a pipeline in a script and call the script.
4. **`verify`** should run the real thing: start the app and drive it, call the running API, or run the command-line tool on real input. If the project has no such command, build it with the `jt-harness` skill first. This check is the one that matters most.
5. The human reviews `jtek.json` and commits it on the base branch. `check` reads the file from the base branch, so an edit in a ticket's worktree changes nothing until the human merges it.

The base branch is `origin/HEAD` when it is set, otherwise `main` or `master`. Set `JTEK_BASE` to override it.

**`name`** is optional. It is how tickets refer to this repository in their `repo:` line. Without it, the folder name is used.

**`watch`** is an optional list of file patterns, for example `["migrations/*", "infra/*"]`. When a ticket changes a matching file, the result names it on the `attention:` line.

Every `start` runs the checks once on the base before any edit, so keep the base green. A slow `verify` makes every ticket start slowly. `start --no-baseline` skips that run.

## Human commands

These are for the human. An agent does not run them.

- Tickets are written in Notion. Set Status to Todo to release one.
- `jtek.py list`: print the open tickets of the board, for every repository.
- `jtek.py list --sync`: also set this repository's Review tickets to Done when `gh` reports the pull request as merged, and remove the worktree of each ticket that is Done or Cancelled. A worktree with uncommitted files is kept.
- `jtek.py start <id> --resume`: take over a claim whose session died without a result.
- `jtek.py release <id>`: drop a claim and its worktree. Git refuses when the worktree has uncommitted changes. The branch is kept, and the page is not changed.
- `jtek.py push <id>`: put a saved result on the page again, after Notion could not be reached.
