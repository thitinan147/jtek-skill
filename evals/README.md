# Evals

Run these whenever you change the text of a skill or a playbook. A change that reads better to you can still make an agent do worse, and only a run shows it.

## What a run is

1. **Build** a scratch repository for a scenario:

   ```bash
   python3 evals/run.py build bug-wordcount ~/work/wordcount
   ```

   It prints the prompt to give the agent, with the ticket handed over as a local file.

   The run is blind. Pick a folder name a person would use, not `eval-1`. The skills are copied into the folder beside the repository, so the agent never reads the folder that holds the hidden tests, and the prompt and the git author say nothing about a test. An agent that knows it is measured does not work as it would on a real ticket.
2. **Run** a fresh agent session with that prompt, and nothing else. Use the agent you want to test (Claude Code, Cursor, ...). It must not see this repository's history or an earlier run.
3. When the result says `needs-review`, start a second fresh session and tell it only to follow `skills/jt-review/SKILL.md` for the same ticket. Then let the first agent, or a third session, run `/jt-work <id>` again.
4. **Grade** what is left:

   ```bash
   python3 evals/run.py grade bug-wordcount ~/work/wordcount
   ```

## What the grader checks

It reads the repository, not the agent's account of it:

- The result block exists, and its outcome is `review` or `needs-review`.
- The declared checks passed on the final commit, and nothing is uncommitted.
- **Hidden acceptance tests pass.** The agent never sees them. They include cases the ticket implies but does not spell out.
- For a bug: the first commit holds only the failing test.
- The base branch has no new commits.
- No sensitive file was touched.
- The evidence is saved and at most 40 lines. The script has already refused evidence that skips a `Done when` item or has no `clean-up:` line.

It also reads the agent's own session files when it can find them (Claude Code keeps them under `~/.claude/projects/`), and prints which skills the agent opened and which `jtek.py` commands it ran, in order. That is what it did, not what it says it did.

## What the grader cannot check

Read these yourself. Do not ask the agent where it had to guess: an agent asked about its work tells you what sounds right, and asking tells it that it is watched. Read its session file instead.

- Did it open each step skill the playbook names? The grade lists what it opened.
- Is the evidence true, and does it cover every `Done when` item?
- Did the reviewer find what the hidden tests find?

## Scenarios

| Scenario | Kind | What it probes |
|---|---|---|
| `bug-wordcount` | bug | Reproduce first, failing test before the fix, edge cases the ticket implies |
| `feature-slug` | feature | Keeping existing behaviour: a rewrite that drops non-ASCII padding passes the visible checks and fails a hidden test |
| `refactor-config` | refactor | Two loops that look like copies differ in two places (an inline comment, an empty value); a merge that flattens them passes the visible checks and fails hidden tests |

Add a scenario when a real ticket goes wrong in a way these do not catch: copy the smallest repository that shows it, write the ticket, and put the mistake in `hidden_test.py`.

## Lean against full

The step skills teach a method. A stronger model may not need it, and then the text only costs context. To find out, build the same scenario both ways:

```bash
python3 evals/run.py build --lean feature-slug ~/work/slug-lean
python3 evals/run.py build feature-slug ~/work/slug-full
```

`--lean` gives the agent a short router (`evals/lean/jt-work.md`), the script, the principles, and the reviewer's skill, with no step skills and no playbooks. The script's checks and the review are the same in both. Run each variant three times per scenario with the model you want to judge. When lean scores the same as full, the step text is not helping that model: cut what it does not need, and keep the full set for the models that still gain from it. Run it again when a new model comes out.

## Reading the scores

One run is an anecdote. Run a scenario three times before and three times after a change to the skill text, and compare. A lower score after the change means revert it.
