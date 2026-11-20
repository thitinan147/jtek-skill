# Templates for `.jtek/`

Starting points for the two kinds of file this skill writes. Replace every line with what is true for the repository. A line you could not confirm by running it does not go in.

## `.jtek/verify.md`

```markdown
# How to run and check this app

## Launch
- Install: `npm ci`
- Port: 3000 plus the ticket's number, so two worktrees never share one. Ticket `T-12` uses 3012.
- Start: `npm run dev -- --port <port>`
- Ready when: `node scripts/ready.mjs <port>` exits 0. It waits until GET /health answers `{"ok":true}`. A listening port is not ready yet.

## Doctor
1. Port in use: another worktree is running. Take the port from the ticket's number as above.
2. `ECONNREFUSED :5432`: the database is not up. Run `docker compose up -d db`.
3. Blank page: the build failed. Read the terminal that runs `npm run dev`.

## Drive
- API: `node scripts/api.mjs <port> GET /me` prints the status and the body. It logs in as the test account first.
- Screen: open `/profile`, find the field by its label "Phone", type, and press the button named "Save".
- Test account: `test@example.invalid` / `test`, created by `npm run seed`.

## Evidence
- A command: the command, its output, and the exit code.
- A screen: the text of the page after the action, and a screenshot.
- A write: read the stored value back with a second, read-only call.

## Cleanup
- Stop the server you started.
- `npm run db:reset` removes the rows the run created.
```

## `.jtek/features/<name>.md`

```markdown
# Profile

## How a user gets to it
Log in, then the avatar menu, then "Profile". Direct link: `/profile`.

## How to drive it
1. Log in as the test account.
2. `node scripts/api.mjs <port> GET /me` shows the current values.
3. `node scripts/api.mjs <port> PATCH /me name=New` changes one.

## What to observe
- PATCH returns 200 and the changed field.
- A second GET returns the new value.

## Gotchas
- The page caches `/me` for 30 seconds. Reload with the cache off.
- `email` cannot be changed here. It returns 403.
```

## Rules

- **Exact commands only.** "Start the server" is not a step. The command is. Confirm a line by pasting it as it is written, not through a wrapper.
- **A command stands alone.** An agent's shell keeps no variables from one command to the next, and it may wait for a process left in the background. Write a start as one command that sends output to files, takes no input, and prints the process id and the folder it made. Later lines name them as `<pid>` and `<folder>`.
- **Say where a dependency comes from.** For a service from another repository: the source, the version, and how to start it at another version. Never from a clone that someone else works in.
- **Ready means usable.** Name the signal you wait for.
- **Two worktrees must not collide.** Take the port, the data folder, or the database name from the ticket. A check command gets the id as `JTEK_TICKET` and the folder as `JTEK_WORKTREE`.
- **Find screen elements by role and name,** not by position or a generated class.
- **Three to five features to start.** Add one when a ticket could not be verified because its feature had no file.
