# Setup for a repository

The short path is `/jt-init`: one confirmation for the guessed checks, then the harness, then `jtek.py doctor`. `/jt` and `/jt-work` do that themselves when this repository has no machine config yet. The steps below are the same work, by hand.

Nothing of jtek is written into the repository. Config is `$HOME/.jtek/repos/<repo id>/jtek.json`. The verify guide, feature map, rule table, and ticket files live beside that file ([files.md](files.md)). `$HOME/.jtek/config`, when it exists, is the default for a repository that has no file of its own. Claims, logs, and results stay under the git directory and are never committed.

The repository id is the origin URL's host, a non-default port, and its path. `https://github.com/acme/widget.git`, `ssh://git@github.com/acme/widget.git`, and `git@github.com:acme/widget.git` are `github.com/acme/widget`. `ssh://git@gitlab.example:2222/acme/widget.git` is `gitlab.example:2222/acme/widget`. Userinfo, a trailing `.git`, and the default ports 443, 80, 22, and 9418 are left out. With no origin, the id is `path` plus the main checkout's absolute path, such as `path/tmp/app`. `JTEK_HOME` overrides `$HOME/.jtek`.

1. Run `jtek.py init`. It writes a template on this machine, not in the repository:

   ```json
   {"setup": "", "checks": {"secrets": "", "lint": "", "types": "", "test": "", "audit": "", "verify": ""}}
   ```

   **`setup`** installs dependencies in a new worktree, for example `npm ci` or `uv sync`. A new worktree has none, so without it the checks fail before any edit. Leave it empty when nothing is needed.

2. Fill in one command per check, using commands the project already has. Delete a check the project does not have. **`secrets`** is a secret scanner such as `gitleaks`, first because it is the fastest and the costliest to miss. **`audit`** is the dependency audit of your package manager. Order matters: checks run top to bottom and stop at the first failure, so put the fast ones first.
   Examples to start from. Use the commands your project already runs in CI, not these, when they differ:

   ```json
   {"name": "web", "setup": "npm ci", "checks": {"lint": "npm run lint", "types": "npm run typecheck", "test": "npm test", "verify": "node scripts/verify.mjs"}}
   ```

   ```json
   {"name": "api", "setup": "uv sync", "checks": {"lint": "uv run ruff check .", "types": "uv run mypy .", "test": "uv run pytest -q", "verify": "uv run python scripts/verify.py"}}
   ```

   ```json
   {"name": "svc", "setup": "go mod download", "checks": {"lint": "go vet ./...", "test": "go test ./...", "verify": "go run ./cmd/verify"}}
   ```

3. A command is one program with arguments. It runs in the ticket's worktree with `JTEK_TICKET` and `JTEK_WORKTREE` set, so a command can pick its own port or data folder when several tickets run at once; `check`, `broke`, and `run` also set `JTEK_VERIFY_DIR` when `~/.jtek/repos/<repo id>/verify.d/<ticket id>/` exists (whole-file overrides for `verify.md`, `features/`, or `rules.md`, promoted to the main folder by `jtek.py sync` after merge). Shell operators such as `&&` and `|` do not work. Put a pipeline in a script and call the script.
4. **`verify`** should run the real thing: start the app and drive it, call the running API, or run the command-line tool on real input. If the project has no such command, build it with the `jt-harness` skill first. This check is the one that matters most. A check named `eslint`, `ruff`, `ruff-format`, `prettier`, `tsc`, `mypy`, or another lint, format, or type tool does not prove a Done when item. Name the behaviour check `test` or `verify`. Prefix `behaviour-` when the command is a linter but the check is the behaviour (`behaviour-eslint`).
5. Run `jtek.py doctor`. It reads only, prints where ticket files live, and lists what is set up and what is missing, in the order to fix it. When `setup` creates a virtualenv, including when that call is inside a script the command names and doctor can read, doctor checks that `ensurepip` imports, and says so when the venv package is missing.
6. The human reviews the file `init` wrote. `check` reads that file, never a `jtek.json` in the worktree, so a ticket cannot weaken a check by committing one.

The base branch is `origin/HEAD` when it is set, otherwise `main` or `master`. Set `JTEK_BASE` to override it.

**`name`** is how tickets refer to this repository in their `repo:` line. Set it in the machine config. Without it, the folder name is used, and a clone under another folder name refuses its own tickets.

**`max_failed_runs`** is optional, and 3 when it is left out. After that many failed `check` runs in a row, the script refuses another and the session stops to ask. A passing run starts the count again, and so does the human setting the ticket file to `status: Todo`. A session that takes a ticket over does not. Raise it when your agent finds the cause on a later try more often than it wastes the run.

**`pr_state`** is optional. For GitHub (`github.com`), the script uses built-in `gh`. For GitLab (any other origin host when `glab` is on PATH), it uses built-in `glab` when no `pr_state` is set. Set `pr_state` as an override for another forge (such as Bitbucket) or a custom state reader. It gets the pull request's link as its last argument and prints three words: the state (`OPEN`, `DRAFT`, `MERGED`, or `CLOSED`), the full head commit, and the CI state (`pass`, `fail`, `pending`, or `none`). For example `"pr_state": "python3 scripts/pr-state.py"`. It runs without a shell, like a check, but in the main checkout and not in a ticket's worktree: a relative path starts at the repository root, and a ticket's branch cannot change the program that runs. When the command fails or prints anything else, `finish` refuses.

**`headings`** is optional. Tickets may use your own words for the headings: `{"Goal": "เป้าหมาย", "Done when": "เสร็จเมื่อ", "Out of scope": "นอกขอบเขต"}`. The copy the session works from has the English ones.

**`forge`** is optional. By default, `github.com` uses `gh` and any other origin host with `glab` on PATH uses `glab`. Set it to `"gh"` or `"glab"` to override the auto-detected forge, or set it to `false` in this machine's config for this repository when the remote is not a forge, so that tickets may end with `finish --no-pr`. A commit cannot set it. `$HOME/.jtek/config` can set it as the default for every repository that has no file of its own.

**`watch`** is an optional list of file patterns, for example `["migrations/*", "infra/*"]`. When a ticket changes a matching file, the result names it on the `attention:` line.

Every `start` runs the checks once on the base before any edit, so keep the base green. If a check is already red on the base, `start` records `known-red` for that base commit, saves one local Backlog follow-up ticket file, and continues so the ticket is not blocked; `check` and `finish` waive only that check while the base commit stays the same. A slow `verify` makes every ticket start slowly. `start --no-baseline` skips that run.

## Commands that are not part of working a ticket

- **Tickets** are local files in `$HOME/.jtek/repos/<repo id>/tickets/` (or drafted on the spot from a chat goal via `start --local --from-file`). Set `status: Todo` in a ticket file to release it.
- **`jtek.py doctor`:** what is set up in this repository and what is missing. Anyone may run it. It only reads.
- **`jtek.py status`, `jtek.py next`, and `jtek.py sync`:** inspect readiness and claims, see what each open ticket file needs, and mark merged Review tickets Done while tidying finished worktrees. See [starting-sessions.md](starting-sessions.md).
- **Take over a claim whose session died without a result:** tell a new session to work the ticket and that the earlier session died. It adds `--resume` to `start`. A session adds `--resume` only when the human said so.
- **`jtek.py release <id>`:** drop a claim and its worktree. Only the human decides this, and an agent runs it only when the human asks. It refuses while the worktree has uncommitted files or commits that are not on the ticket's branch, and while a `start` for that ticket is still running. Files that git ignores, such as `.env`, go with the worktree. A worktree with submodules is never removed by the script: remove it by hand when its submodule commits are pushed. The branch is kept, and the next `start` for that ticket goes on from it. The one exception is a `start` that was interrupted before any work: its empty branch is removed. The ticket file is not changed.

`init`, `migrate`, `guess`, `status`, `doctor`, `next`, `sync`, `release`, and `reviewer` run only from the `jt-work` skill's copy of the script.
