---
name: jt-do-work
description: Work every card the board allows, one branch and one draft pull request each. Skip lines marked review or an open ask, skip a card whose files overlap those lines, and continue send-back on the same branch after merging in the queue branch. Use when the user runs /jt-do-work or asks to do the next cards.
license: MIT
metadata:
  author: Thitinan
  version: "20"
  short-description: Do the card the board line allows
---

# jt-do-work

Work in the open repo. Commit locations are under **Where commits go** in `skills/jt-card-gate/references/loop.md`. Open other skills per `references/skills.md` in that skill. Commit form is under **Commit standard** in the same file.

`loop.md` is the shared policy. This file is the procedure. `skills/jt-next-step/gate.py` enforces. Do not restate the gate here.

One round holds one card. The card is done when the line is `review:` or `ask:`. Then return to **Pick a card**.

Before work, read these headings in `loop.md` and follow them.

- Closed intent. **Closed intent**.
- Irreversible work. **Irreversible work**.
- Three evidence rounds. **Three rounds**.
- When review is forbidden. **Rules** and **Summary**.

If the gate refuses, follow **Write ask** or **Three rounds**. Do not write `review:` yourself.

## Pick a card

1. If `card-loop/board.md` is missing, stop and say to run `/jt-new-board` first. If the file exists and `queue:` is empty, or `<TEST_CMD>` is empty, or `<STACK_LOCK>` is empty, stop the whole queue and name the field to fill. The value `no-suite` is allowed. Do not run it as a command.
2. If files outside `card-loop/` are dirty, stop the whole queue. If the human edited files under `card-loop/`, commit them on the queue branch before you create the card branch.
3. Check out the queue branch.
4. Make three passes in this order. On each pass, walk **first**, then **main**. Walk **later** only when every `- [ ]` under **first** and **main** is done. When you find a card, stop. Do not continue past the rest.
   - Pass one. The first line marked `send-back:`.
   - Pass two. The first line marked `ask:` whose card heading `ask` is empty.
   - Pass three. The first line with no `ask:`, `review:`, or `send-back:`, and with `card-loop/backlog/<id>.md`.
5. On every pass, skip `review:`. Skip `ask:` while heading `ask` still has text. Skip a line with no card file. Skip a card whose `files` heading uses the same path as another line that is still `review:` or `send-back:`. A parent line is a line `**<parent>**` with a line `**<parent>.<child>**` below it. Do not pick that parent line. A section heading such as `## main` is not that line. When every child is done and the parent line has no status, change the parent's `- [ ]` to `- [x]`, append `complete:`, and commit only `card-loop/board.md` on the queue branch. Leave a parent that is already `review:`, `ask:`, or `complete:`.
6. If step 4 finds no card, stop the whole queue here. A line left on `review:` is not a reason to stop. For a card skipped because files overlap, say it waits until that other card is on the queue branch.
7. When you have a card, and its `layer:` matches another card that is still open, and `refs` does not point at the other card, follow **Write ask** and return to step 1. When they are linked, do them one at a time in this order. Do not split into parallel agents. Then check **Closed intent** in `loop.md`.
   - If the line is `ask:` and intent is closed, delete `ask:` from the line, commit only `card-loop/board.md` on the queue branch, and go to **Do the work**.
   - If the line has no `ask:` and intent is closed, go to **Do the work**.
   - Otherwise follow **Write ask** and return to step 1. Before you write `ask:` because two outcomes remain, open one `<TEK_SKILLS>` name whose description mentions grill or interview, if one exists.

The card id is the text inside `**` on the line. The line form is under **Where commits go**.

## Write ask

1. If branch `card-<id>` exists and work files are uncommitted, commit them on that branch. Add one row to `decisions`. Commit only the plan file on that branch.
2. Check out the queue branch.
3. Replace an empty `ask:` heading in the card with these three lines. Do not write the heading twice. On the board line, append `ask:`. The item stays `- [ ]`.

```markdown
ask: <one question>
blocked: <why work cannot continue>
options: <choices the human can pick>
```

4. Commit only `card-loop/board.md` and `card-loop/backlog/<id>.md` on the queue branch.
5. Return to **Pick a card**.

Done when the queue-branch line contains `ask:` and the card heading `ask` contains a question.

## Do the work

If the line is `send-back:` and branch `card-<id>` does not exist, follow **Write ask**.

If branch `card-<id>` already exists, check it out and merge the queue branch into this branch. Keep the existing draft PR. Create a new branch only from the queue branch. Do not create it from another `card-<id>` branch. On a conflict, edit this branch to match `do`, then rerun the relevant tests. If you cannot resolve the conflict without choosing for the human, follow **Write ask**. If `files` in the plan is empty, copy it from the card before you edit work files.

If the branch does not exist yet, create `card-<id>` from the queue branch and check it out. Create `card-loop/plan/<id>.md` from `assets/plan.template.md` in skill `jt-card-gate`. Set Branch to `card-<id>`. Copy `files` from the card. Commit only the plan file on this branch.

If the line is `send-back:` and `round-status` is not `send-back`, set `round` to 1 and `round-status` to `send-back`, then commit only the plan file on `card-<id>`. If `round-status` is already `send-back`, keep the current round.

Then, on `card-<id>`:

- For a `fix` whose cause is still unclear, before a red test, open one `<TEK_SKILLS>` name whose description mentions diagnose or debug, if one exists.
- While editing production code, open one `<TEK_SKILLS>` name whose description mentions YAGNI, stdlib, or delete, if one exists.
- For `feat` or `fix`, write a test of that behavior that is red because the assertion is not true yet, then make it green.
- For `test`, the added test is green, and you do not change production behavior to make it pass.
- Screen work of every kind needs `screen: yes` plus `start:`, `port:`, `wait:`, and `click:` on the card. Start the real frontend and the real backend from those commands. The click must exit 0 and match `pass`. If start fails or the click fails, follow **Write ask**.
- For a screen `fix`, record the steps that show the bug. The same steps after the fix must not show it.
- Edit only files under `files` in the plan.
- For irreversible work, follow **Irreversible work** in `loop.md`, then **Write ask**.
- If the whole evidence set fails, follow **Three rounds** in `loop.md`.
- Each time you choose a path, write `ask:`, or the evidence passes, add one row to `decisions`.
- If this card and another open card share `layer:`, change the skill rule, the gate, or the lint or check script, then add an `update-rule` row in `decisions`. The evidence cell is that path. Do not patch only this card's code. A row alone, with no such file in the diff, cannot open review.

Before you open review, run the existing check commands on the board. Run `<TEST_CMD>`, `<TYPECHECK_CMD>`, and `<LINT_CMD>` when the field has a command and the touched files are in scope. For `feat` or `fix`, run `<TEST_CMD>` unless the value is `no-suite`. For any other kind whose value is `no-suite`, write in the review notes that there is no test suite. Do not create a new check script for this round unless `do` says to create that file. Screen work, before `review:`, uses JTek `scripts/jt-screen-check` or another existing check command on the board. With `<BROWSER_TOOL>` set, start from `start:` and `port:`, and set `click:` to `python3 <jtek-skill folder>/scripts/jt-screen-check --root . --no-start`, including other pages that read the same state. With `<BROWSER_TOOL>` empty on screen work, follow **Write ask**. When the work is not on screen and `<BROWSER_TOOL>` is empty, write which surface could not be checked.

## Paired repo

Read the name from the `pair:` line on the primary repo's board. Do not ask again where the paired repo is. That name is the folder beside the primary repo. Do not invent a repo name.

If the line is `none` or empty, follow the single-repo path. Do not wait for a second side. Do not create files in another repo.

A card that touches both sides is one card. The card heading and the board line contain `·` plus the name on the `pair:` line. A card that does not touch the pair does not include that name.

The card's work may happen in the paired repo, on branch `card-<id>`. The queue and every status stay on the primary repo's board only. Do not set status in the paired repo. Do not create `card-loop/board.md` there. Do not move the whole queue off the primary repo.

Create `card-loop/paired.md` in the paired repo only when this card touches that repo. The contents point back at the primary repo's folder name and `card-loop/board.md`. Under `card-loop/` in the paired repo, this file is the only one allowed. Do not create this file only because the board recorded the name.

The human merges both repos.

## Open for review

Read **Rules** and **Summary** in `loop.md` first. If those rules block review, follow **Three rounds** on this card. Do not set `review:`.

After a commit whose kind is `feat`, `fix`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, or `revert`, and before `review:`, open every name in `<REPO_SKILLS>`. `docs` does not open. An empty row opens nothing else. If a name in that row is not on this machine, review this card's diff yourself before `review:`, even when another name in the row did open. A name from `<TEK_SKILLS>` does not do this review. A note in the plan is not that review. Do not skip that review. If you cannot review the diff, do not set `review:`. Follow **Three rounds**. The gate refuses that line. If an opened skill passes but the evidence in this section is incomplete, follow **Three rounds**. On a card that touches code, record the review under `## review-diff` in the plan, with `- commit:` as the full SHA of the latest commit, `- reviewer:`, and `- found:`, before `review:`. Run `python3 <jtek-skill folder>/scripts/jt-diff-check --root . --id <id>` and require exit 0. A review heading alone is not enough.

Commit the card's work on `card-<id>` first. Check `pass` against that commit. This commit does not contain the word `review:` and does not contain `card-loop/board.md`, unless `do` on the card says to edit that file.

Check out the queue branch. Run reach-review without `--write`.

```bash
python3 <jt-next-step skill folder>/gate.py reach-review --root . --id <id>
```

Trust the output. Do not write `review:` yourself.

If the script prints `allowed` and `git remote` is empty, rerun the same command with `--write --link local`. The script sets the line to `review: local`.

If the script prints `allowed` and `git remote` has a name, push only `card-<id>` and open one draft PR into the queue branch when no open pull request exists for that head. Do not open a duplicate. Do not create a remote.

```bash
git push -u origin card-<id>
gh pr list --head card-<id> --base <queue> --state open --json number,isDraft,url,baseRefName
gh pr create --draft --base <queue> --head card-<id> --title "<id>" --body "card <id>"
```

If `gh pr list` already has an item whose `isDraft` is true and whose `baseRefName` is the queue branch, skip `gh pr create`. If `gh` is not on PATH, push fails, create fails, there is no open PR, the open PR is not a draft, or the base is not the queue branch, follow **Write ask**. Do not pass `--write`. The line must not be `review:`.

When the draft exists, run reach-review with `--write`. The script checks the pull request. If it prints `refused: pr-missing`, `refused: gh-missing`, `refused: pr-not-draft`, `refused: pr-base`, `refused: pr-duplicate`, or `refused: pr-failed` with `step: ask`, follow **Write ask**. Do not set `review:`.

For any other `refused:`, use this map. Do not restate the gate condition.

| Output | Action |
|---|---|
| `step: ask`, `refused: related`, `refused: browser-empty`, `refused: start-down`, `refused: click-mismatch` | Follow **Write ask**. Do not set `review:`. |
| `refused: setup-failed`, `refused: test-failed`, `refused: review-diff`, `refused: one-off-checker`, `refused: repeat-patch`, `refused: pair-not-passed` | Follow **Three rounds** on this card. Do not set `review:`. |
| any other `refused:` | Stop. Do not set `review:`. Do not add a new check script. |

When the script passes, the line is `review:` followed by that draft URL. Set `round-status` in the plan to `review`. Commit only the plan file on `card-<id>`. Check out the queue branch and commit only `card-loop/board.md`. The item stays `- [ ]`.

Return to **Pick a card**.

Done when **Pick a card** step 6 is true.
