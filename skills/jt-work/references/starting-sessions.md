# For whoever starts the sessions

A session works the tickets it is given. Something else decides which ticket runs next and starts the session: the human, a Claude Code session that starts other sessions, or a bot. All three follow the same contract.

## Ask what each ticket needs

1. Read the board (the database named as `board` in the machine config) with the board's tool, and save its tickets as a JSON file outside the repository. Leave out tickets that were already Done or Cancelled the last time you ran `sync`:

   ```json
   [{"id": "T-12", "title": "...", "status": "Todo", "repo": "api", "waiting": "", "pr": "", "after": ["T-10"]}]
   ```

   `after` lists only the related tickets that are not Done. Read the board again each time. Do not reuse an old file.

   A repository with no board needs no such file: its tickets are files, as [files.md](files.md) says, and `next` and `sync` read them when you leave `--board-file` out. `next` and `status` also read a claim that has no ticket file, such as a local ticket. `sync` does not: it only tidies a ticket the page already names.
2. Run `jtek.py next --board-file <file>` in the repository. It prints one line for each of this repository's tickets: the id, an action, and the reason, separated by tabs.

| Action | What to do |
|---|---|
| `work` | Start a fresh session in this repository: "Read <jt-work folder>/worker.md before anything else. Follow the `jt-work` skill for ticket `<id>`." |
| `review` | Start a fresh session in this repository: "Read <jt-work folder>/worker.md before anything else. Follow the `jt-review` skill for ticket `<id>`." It must not be the session that wrote the change. |
| `board` | The page does not show the saved result or question. Write the `board:` line of `jtek.py result <id>` on the page, as [notion.md](notion.md), [flo.md](flo.md), or [files.md](files.md) says. Do not start a session. |
| `human` | Nothing. The human answers on the page and sets Todo, or reviews and merges. |
| `hold` | Nothing. The ticket is in Backlog, or it comes after one that is not Done. |
| `running` | Nothing, while a session for this ticket is running. If none is, tell the human: that session died. |
| `stuck` | Nothing. Tell the human: a `start` died half way, or the claim is damaged. The reason says which command cleans it up. |
| `elsewhere` | Nothing. Another machine has the ticket. |

After a session ends, read the board and run `next` again. The action for that ticket has changed.

A session may end with `needs-review` while a reviewer it started is still at work, when the project's checks are slow. Run `next` before you start another reviewer: `review` means no verdict is recorded yet, and one may be on its way.

## When a session stops, and how the human answers

A session does not stop to ask about a decision that belongs in the pull request. It chooses, writes `choice: <question> → <picked> (other options: …)` with the principle id in the evidence, which becomes the pull request body or a `## Log` line, and goes on to the pull request (P19). The human sees each choice at review and changes it there. So ticket to pull request can finish in one session, with no new session after an answer.

A session still stops and waits in two cases: before an act outside the pull request (`--waiting approval`, P16), and with `--waiting input` where a step or the script says so, such as after the third FAIL verdict or three failed checks.

The human answers on the page or in the ticket file and sets Todo, as before. That is no longer the only way: they may also comment on the pull request, or leave a note under `## Log`. Submit a review as a whole (GitHub or GitLab "Submit review", with several notes), not one comment at a time: a session acts on the whole review, so the human is interrupted by a review they chose to send, not by every comment. When `next` says `work` for that ticket, the new session reads every comment since the latest verdict with `gh` or the forge, and answers them in one round with `jt-babysit`. Nobody moves the card to another status to have the comments picked up.

Now and then, run `jtek.py sync --board-file <file>`. It prints one line for each of this repository's tickets in Review, Done, or Cancelled. When the forge reports a pull request as merged, the line has `board: Status=Done`: set that on the page. It also removes the worktrees of finished tickets, and says when it kept one. It deletes a ticket's branch only when every commit is on the base, or the forge says the pull request merged at the branch's last commit.

## Rules for whoever starts sessions

- Start a session only for `work` and `review`. Never set Todo or Cancelled, never record a verdict, and never merge.
- One session per ticket at a time. Before you start one, check that none is running for that id.
- Give each session only the line in the table. Do not pass on what another session said.
- Run one ticket at a time. Run tickets in parallel only when they do not share a database, a port, an e2e stack, or shared files. You decide this when you release the cards; no command checks it.
- A session needs the board's tool (Notion or FLO; none when the tickets are files), and permission to run git, the project's checks, and `gh`.
- Which tickets may share one session is in [several-tickets.md](several-tickets.md).

## Which agent reviews

For a `review` line, run `jtek.py reviewer --vendor <the vendor of the model that wrote the change>`. It reads the owner's list, `~/.jtek/agents.json`, and prints the command of the first entry that is installed and comes from another vendor; without one, the first installed entry of the same vendor; with no list, it says to start a fresh session of your own agent. An old list at `~/.config/jtek/agents.json` is still read, with a one-line notice, until `jtek.py migrate` moves it. It prints a command and starts nothing. The list is the owner's ranking and holds only models they trust to review. `jtek.py doctor --agents` shows which agent programs this machine has and the models of those that can list them.

When you do not know which model wrote the change, name your own vendor. Another agent may not have these skills installed: give it the full path of `worker.md` and of `jt-review`'s `SKILL.md` in place of the skill's name.

## Starting a separate session

Any agent that can start a separate session that does not share this one's conversation will do. In Cursor: `cursor-agent -p "<the line>"`, run from the repository. In Antigravity: `agy -p "<the line>"`. In Claude Code:

`claude --bg -n "jtek <id> work" "<the line from the table>"`, run from the repository, starts a separate background session and returns at once. `claude agents --json` lists the sessions and their state, `claude attach <id>` opens one, and `claude logs <id>` prints its recent output. A session whose state is `blocked` waits for a person.

A background session does not close itself. After it prints its `result` (the `jtek-result` block), run `claude stop <id>`. Do not ask the human anything on its behalf while it runs: a decision inside the pull request is its `choice:` line, for the human to change at review.
