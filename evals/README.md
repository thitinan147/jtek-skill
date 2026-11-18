# Evals

Run these whenever you change the text of a skill or a playbook. A change that reads better to you can still make an agent do worse, and only a run shows it.

## What a run is

1. **Build** a scratch repository for a scenario:

   ```bash
   python3 evals/run.py build bug-wordcount /tmp/eval-1
   ```

   It prints the prompt to give the agent. An eval uses no Notion: the page is handed over as a ticket file, so reading the page and writing the `board:` line are not covered.
2. **Run** a fresh agent session with that prompt, and nothing else. Use the agent you want to test (Claude Code, Cursor, ...). It must not see this repository's history or an earlier run.
3. When the result says `needs-review`, start a second fresh session and tell it only to follow `skills/jt-review/SKILL.md` for the same ticket. Then let the first agent, or a third session, run `/jt-work <id>` again.
4. **Grade** what is left:

   ```bash
   python3 evals/run.py grade bug-wordcount /tmp/eval-1
   ```

## What the grader checks

It reads the repository, not the agent's account of it:

- The result block exists, and its outcome is `review` or `needs-review`.
- The declared checks passed on the final commit, and nothing is uncommitted.
- **Hidden acceptance tests pass.** The agent never sees them. They include cases the ticket implies but does not spell out.
- For a bug: the first commit holds only the failing test.
- The base branch has no new commits.
- No sensitive file was touched.
- The evidence is saved and at most 40 lines. The script has already refused evidence that skips a `Done when` item.

## What the grader cannot check

Read these yourself, and ask the agent to list where the skill text made it guess:

- Did it open each step skill the playbook names?
- Is the evidence true, and does it cover every `Done when` item?
- Did the reviewer find what the hidden tests find?

## Scenarios

| Scenario | Kind | What it probes |
|---|---|---|
| `bug-wordcount` | bug | Reproduce first, failing test before the fix, edge cases the ticket implies |
| `feature-slug` | feature | Keeping existing behaviour: a rewrite that drops non-ASCII padding passes the visible checks and fails a hidden test |

Add a scenario when a real ticket goes wrong in a way these do not catch: copy the smallest repository that shows it, write the ticket, and put the mistake in `hidden_test.py`.

## Reading the scores

One run is an anecdote. Run a scenario three times before and three times after a change to the skill text, and compare. A lower score after the change means revert it.
