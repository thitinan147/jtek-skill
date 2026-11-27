# Starting sessions

Work starts in one of two ways:

1. **A goal typed in chat:** give the goal to `/jt` or `/jt-work`. The agent starts directly with `jtek.py start --local --goal "<goal>"` (assigning `LOCAL-<n>` and storing the goal in the claim folder), with no ticket file, no `Done when`, and no `broke` step, and proceeds unless the change reaches outside the pull request (P16). The second-session reviewer reads that stored goal and the diff.
2. **Existing ticket files:** local Markdown files in `$HOME/.jtek/repos/<repo id>/tickets/` ([files.md](files.md)), saved with `jtek.py ticket <file> --save` (or written directly). The human releases a file by setting `status: Todo`. A session works the ids it is given; the human, another session, or a script decides which ticket runs next.

## Ask what each ticket file needs

1. Run `jtek.py next` in the repository. It reads the ticket files on this machine (and any local `LOCAL-<n>` claims under `.git/jtek/work/`) and prints one line for each of this repository's tickets: the id, an action, and the reason, separated by tabs. `jtek.py status` prints a read-only readiness line and summary table of the same state.

| Action | What to do |
|---|---|
| `work` | Start a fresh session in this repository: "Read <jt-work folder>/worker.md before anything else. Follow the `jt-work` skill for ticket `<id>`." |
| `review` | Start a fresh session in this repository: "Read <jt-work folder>/worker.md before anything else. Follow the `jt-review` skill for ticket `<id>`." It must not be the session that wrote the change. |
| `human` | Nothing. The human answers in the ticket file and sets `status: Todo`, splits a multi-repo ticket file, or reviews and merges. |
| `hold` | Nothing. The ticket is in Backlog, finished, or comes after one that is not Done. |
| `running` | Nothing, while a session for this ticket is running. If none is, tell the human: that session died. |
| `stuck` | Nothing. Tell the human: a `start` died half way, or the claim is damaged. The reason says which command cleans it up. |
| `elsewhere` | Nothing. Another machine has the ticket. |

After a session ends, run `jtek.py next` again. The action for that ticket has changed.

A session may end with `needs-review` while a reviewer it started is still at work, when the project's checks are slow. Run `jtek.py next` before you start another reviewer: `review` means no verdict is recorded yet, and one may be on its way.

## When a session stops, and how the human answers

A session does not stop to ask about a decision that belongs in the pull request. It chooses, writes `choice: <question> → <picked> (other options: …)` with the principle id in the evidence, which becomes the pull request body, and goes on to the pull request (P19). The human sees each choice at review and changes it there. So ticket to pull request can finish in one session, with no new session after an answer.

A session still stops and waits in two cases: before an act outside the pull request (`--waiting approval`, P16), and with `--waiting input` where a step or the script says so, such as after the third FAIL verdict or three failed checks.

For a ticket file, `jtek.py stop` writes `waiting:` to the file's header. The human answers in the ticket file (or under `## Log`) and sets `status: Todo`, or submits a review on the pull request. Submit a review as a whole (GitHub or GitLab "Submit review", with several notes), not one comment at a time: a session acts on the whole review, so the human is interrupted by a review they chose to send, not by every comment. When `next` says `work` for that ticket, the new session reads every comment since the latest verdict with `gh` or the forge, and answers them in one round with `jt-babysit`. For a `--local` chat goal, the human replies in chat and the session resumes with `jtek.py start --local <id> --answered`.

Now and then, run `jtek.py sync`. It prints one line for each of this repository's tickets in Review, Done, or Cancelled (including `LOCAL-<n>` claims). When the forge reports a pull request as merged, `sync` marks the ticket Done, promotes any `verify.d/<id>/` overrides (or prints `hold` on conflict), removes the worktree, and deletes the ticket's branch only when every commit is on the base or the forge says the pull request merged at the branch's last commit.

## Rules for whoever starts sessions

- Start a session only for `work` and `review`. Never set Todo or Cancelled, never record a verdict, and never merge.
- One session per ticket at a time. Before you start one, check that none is running for that id.
- Give each session only the line in the table. Do not pass on what another session said.
- Run one ticket at a time. Run tickets in parallel only when they do not share a database, a port, an e2e stack, or shared files. You decide this when you start or release tickets; no command checks it.
- A session needs permission to run git, the project's checks, and `gh` (or `glab`).
- Which tickets may share one session is in [several-tickets.md](several-tickets.md).

## Which agent reviews

For a `review` line, run `jtek.py reviewer --vendor <the vendor of the model that wrote the change>`. It reads the owner's list, `~/.jtek/agents.json`, and prints the command of the first entry that is installed and comes from another vendor; without one, the first installed entry of the same vendor; with no list, it says to start a fresh session of your own agent. An old list at `~/.config/jtek/agents.json` is still read, with a one-line notice, until `jtek.py migrate` moves it. It prints a command and starts nothing. The list is the owner's ranking and holds only models they trust to review. `jtek.py doctor --agents` shows which agent programs this machine has and the models of those that can list them.

When you do not know which model wrote the change, name your own vendor. Another agent may not have these skills installed: give it the full path of `worker.md` and of `jt-review`'s `SKILL.md` in place of the skill's name.

## Starting a separate session

Any agent that can start a separate session that does not share this one's conversation will do. In Cursor: `cursor-agent -p "<the line>"`, run from the repository. In Antigravity: `agy -p "<the line>"`. In Claude Code:

`claude --bg -n "jtek <id> work" "<the line from the table>"`, run from the repository, starts a separate background session and returns at once. `claude agents --json` lists the sessions and their state, `claude attach <id>` opens one, and `claude logs <id>` prints its recent output. A session whose state is `blocked` waits for a person.

A background session does not close itself. After it prints its `result` (the `jtek-result` block), run `claude stop <id>`. Do not ask the human anything on its behalf while it runs: a decision inside the pull request is its `choice:` line, for the human to change at review.
