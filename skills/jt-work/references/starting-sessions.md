# For whoever starts the sessions

A session works the tickets it is given. Something else decides which ticket runs next and starts the session: the human, a Claude Code session that starts other sessions, or a bot. All three follow the same contract, and none of them needs to read Notion.

## Ask what each ticket needs

Run `jtek.py next` in the repository. It prints one line for each open ticket of this repository: the id, an action, and the reason, separated by tabs.

| Action | What to do |
|---|---|
| `work` | Start a fresh session in this repository: "Follow the `jt-work` skill for ticket `<id>`." |
| `review` | Start a fresh session in this repository: "Follow the `jt-review` skill for ticket `<id>`." It must not be the session that wrote the change. |
| `push` | Run `jtek.py push <id>`. |
| `human` | Nothing. The human answers on the page, or reviews and merges. |
| `hold` | Nothing. The ticket is in Backlog, or it comes after one that is not Done. |
| `running` | Nothing, while a session for this ticket is running. If none is, tell the human: that session died. |
| `elsewhere` | Nothing. Another machine has the ticket. |

After a session ends, run `jtek.py next` again. The action for that ticket has changed.

Run `jtek.py list --sync` now and then. It sets merged tickets to Done and removes their worktrees.

## Rules for whoever starts sessions

- Start a session only for `work` and `review`. Never set a status on the board, never record a verdict, and never merge.
- One session per ticket at a time. Before you start one, check that none is running for that id.
- Give each session only the line in the table. Do not pass on what another session said.
- Limit how many run at once. Three is a reasonable start.
- A session needs `NOTION_TOKEN` in its environment, and permission to run git, the project's checks, and `gh`.
- Which tickets may share one session is in [several-tickets.md](several-tickets.md).

## With Claude Code

`claude --bg -n "jtek <id> work" "<the line from the table>"`, run from the repository, starts a separate background session and returns at once. `claude agents --json` lists the sessions and their state, `claude attach <id>` opens one, and `claude logs <id>` prints its recent output. A session whose state is `blocked` waits for a person.
