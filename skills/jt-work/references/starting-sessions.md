# For whoever starts the sessions

A session works the tickets it is given. Something else decides which ticket runs next and starts the session: the human, a Claude Code session that starts other sessions, or a bot. All three follow the same contract.

## Ask what each ticket needs

1. Read the board (the database named as `board` in `jtek.json`) with the board's tool, and save its tickets as a JSON file outside the repository. Leave out tickets that were already Done or Cancelled the last time you ran `sync`:

   ```json
   [{"id": "T-12", "title": "...", "status": "Todo", "repo": "api", "waiting": "", "pr": "", "after": ["T-10"]}]
   ```

   `after` lists only the related tickets that are not Done. Read the board again each time. Do not reuse an old file.
2. Run `jtek.py next --board-file <file>` in the repository. It prints one line for each of this repository's tickets: the id, an action, and the reason, separated by tabs.

| Action | What to do |
|---|---|
| `work` | Start a fresh session in this repository: "Follow the `jt-work` skill for ticket `<id>`." |
| `review` | Start a fresh session in this repository: "Follow the `jt-review` skill for ticket `<id>`." It must not be the session that wrote the change. |
| `board` | The page does not show the saved result or question. Write the `board:` line of `jtek.py result <id>` on the page, as [notion.md](notion.md) or [flo.md](flo.md) says. Do not start a session. |
| `human` | Nothing. The human answers on the page and sets Todo, or reviews and merges. |
| `hold` | Nothing. The ticket is in Backlog, or it comes after one that is not Done. |
| `running` | Nothing, while a session for this ticket is running. If none is, tell the human: that session died. |
| `stuck` | Nothing. Tell the human: a `start` died half way, or the claim is damaged. The reason says which command cleans it up. |
| `elsewhere` | Nothing. Another machine has the ticket. |

After a session ends, read the board and run `next` again. The action for that ticket has changed.

A session may end with `needs-review` while a reviewer it started is still at work, when the project's checks are slow. Run `next` before you start another reviewer: `review` means no verdict is recorded yet, and one may be on its way.

Now and then, run `jtek.py sync --board-file <file>`. It prints one line for each of this repository's tickets in Review, Done, or Cancelled. When the forge reports a pull request as merged, the line has `board: Status=Done`: set that on the page. It also removes the worktrees of finished tickets, and says when it kept one. It deletes a ticket's branch only when every commit is on the base, or the forge says the pull request merged at the branch's last commit.

## Rules for whoever starts sessions

- Start a session only for `work` and `review`. Never set Todo or Cancelled, never record a verdict, and never merge.
- One session per ticket at a time. Before you start one, check that none is running for that id.
- Give each session only the line in the table. Do not pass on what another session said.
- Limit how many run at once. Three is a reasonable start.
- A session needs the board's tool (Notion or FLO), and permission to run git, the project's checks, and `gh`.
- Which tickets may share one session is in [several-tickets.md](several-tickets.md).

## Starting a separate session

Any agent that can start a separate session that does not share this one's conversation will do. In Cursor: `cursor-agent -p "<the line>"`, run from the repository. In Antigravity: `agy -p "<the line>"`. In Claude Code:

`claude --bg -n "jtek <id> work" "<the line from the table>"`, run from the repository, starts a separate background session and returns at once. `claude agents --json` lists the sessions and their state, `claude attach <id>` opens one, and `claude logs <id>` prints its recent output. A session whose state is `blocked` waits for a person.
