# Card Queue Contract, version 21

These rules belong to skill `jt-work-queue`. The queue lives in `card-loop/` in the open repo.

## Commands

| Command | What it does |
|---|---|
| `/jt-work-queue` | Set up `card-loop/board.md`, capture `card-loop/brief.md`, draft and add cards, and work every ready card in the queue. Cannot merge. |
| `/jt-review-work` | Human-only command to inspect `review:` cards and mark `merge:`, `send-back:`, or `drop:`, or move board lines. |

The human calls `/jt-review-work` to record `send-back:`, `merge:`, or `drop:`. The agent does not call `/jt-review-work` and never writes `merge:` or `drop:`. The human merges on GitHub (or locally), and `merge:` only changes the mark on the board line—it does not open a PR, does not merge a PR, and does not run git merge.

## Files in the open repo

- `card-loop/board.md` — Queue and repo command table (`<SETUP_CMD>`, `<TEST_CMD>`, `<TYPECHECK_CMD>`, `<LINT_CMD>`, `<BROWSER_TOOL>`, `<STACK_LOCK>`, `<REPO_SKILLS>`).
- `card-loop/brief.md` — Optional round brief accepted by the human.
- `card-loop/backlog/<id>.md` — Card scope (`do:`, `out:`, `files:`, `pass:`) on the queue branch.
- `card-loop/plan/<id>.md` — Working plan, `## decisions`, and `## review-diff` on branch `card-<id>` (required for Standard tier, optional for Quick tier).

## Where commits go & Status tokens

- Commit `card-loop/board.md`, `card-loop/brief.md`, and `card-loop/backlog/<id>.md` on the `queue:` branch.
- Commit card code and `card-loop/plan/<id>.md` on branch `card-<id>`.
- Valid status tokens on board lines are `ask:`, `review:`, `send-back:`, `merge:`, and `drop:`. Any other colon token in the status slot stops the queue with `unknown-status`.
- Agent status updates on existing board lines must go through `gate.py ask` or `gate.py reach-review --write`.
- With a remote, push `card-<id>` and open one draft PR with `gh pr create --draft --base <queue> --head card-<id>`. If the draft PR cannot be opened, write `ask:`. The line must not be `review:`. The gate refuses.

## Rules

- Before opening review, use the existing check commands on the board. Do not create a new check script for this round unless `do:` says to create that tool.
- Screen work before `review:` uses the JTek screen command `python3 <jt-work-queue>/scripts/gate.py screen-check` or existing check commands on the board.
- Open cards that share `layer:` must link each other under `refs:`. Do not split into parallel agents without a link.
- When recurring failures occur across cards, propose a new `chore` card with evidence for human approval. Never modify rule files (`SKILL.md` or `gate.py`) inside the current card's diff.

### Plan

For Standard tier cards, create `card-loop/plan/<id>.md` from `assets/plan.template.md`. A Done when line is a command to run, or an artifact to open. If Done when has no command and no artifact, write `ask:`. If Escape is empty, or an Escape line is true, write `ask:` and do not set `review:`.

### Three rounds

One round is one full attempt. The evidence is that the relevant tests are green, and for screen work of every kind, not only `fix`, the same steps on the same screen do not show the bug. Screen work that cannot be clicked does not count as this round. Write `ask:`. After 3 failed rounds on a card, run `gate.py ask` with what was tried and move to the next card.

### `<REPO_SKILLS>` diff review

On Standard tier cards that touch code, open `<REPO_SKILLS>` (or review this card's diff yourself if no repo skill is installed on this machine) before `review:`. `docs` does not open. Do not skip that review; if you cannot review the diff, do not set `review:`. A note in the plan is not that review. Record `- commit: <sha>`, `- reviewer:`, and `- found:` under `## review-diff` in `card-loop/plan/<id>.md`.
