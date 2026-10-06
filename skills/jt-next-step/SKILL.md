---
name: jt-next-step
description: Read the current line on card-loop/board.md and do the next step the loop already allows. Use when the user runs /jt-next-step or asks for the next board step without naming a command. This command cannot merge.
license: MIT
metadata:
  author: Thitinan
  version: "20"
  short-description: Do the next step the board line allows
---

# jt-next-step

Read the line on `card-loop/board.md`. Do the next step that `skills/jt-card-gate/references/loop.md` already allows. This file is a router. `gate.py` enforces. Trust its output. Do not restate the gate.

Run from the open repo root, with this skill's `gate.py`.

```bash
python3 <folder of this skill>/gate.py next --root .
python3 <folder of this skill>/gate.py reach-review --root . --id <id>
python3 <folder of this skill>/gate.py landed --root . --id <id>
```

Do the one `command` that `next` prints, then stop.

- If `reason` is `need-id`, ask for the id and stop.
- If `reason` is `wait`, show the question and stop.
- If `action` is `stop`, report `reason` and stop.
- If `reason` is `related`, report `ids` and stop. Those cards share `ชั้น:` and **อ้างอิง** does not link them. Do not split into parallel agents.
- If `command` is `/jt-open-work`, use the text under `merge:`. Do not change the line.

This script cannot merge, even if the human types the word merge in this turn. The mark belongs to `/jt-merge`, and only after the human compares **ตรวจผ่านเมื่อ** with the diff. That command changes only the line mark. It does not run git merge, open a PR, or merge a PR. The gate cannot call that command. The human merges on GitHub after the card commit is on the queue branch, including a merge through a pull request. `landed` only reports. `landed: ancestor` or `landed: squash` is what `/jt-merge` reads. `refused: not-landed` means the human has not landed the code.

`/jt-do-work` sets `รอรีวิว:` by running `reach-review` on the queue branch. The first run omits `--write`. The script runs `<SETUP_CMD>` and `<TEST_CMD>` in a clean worktree of `card-<id>`.

If `git remote` is empty and the first run prints `allowed`, run again with `--write --link local`. The line becomes `รอรีวิว: local`.

If `git remote` has a name and the first run prints `allowed`, push only `card-<id>` and open one draft PR into the queue branch. Before `--write`, `gh` must be available, and no open pull request may already exist for that head.

```bash
git push -u origin card-<id>
gh pr list --head card-<id> --base <สาขาคิว> --state open --json number,isDraft,url,baseRefName
gh pr create --draft --base <สาขาคิว> --head card-<id> --title "<id>" --body "card <id>"
```

If `gh pr list` already has a draft whose `baseRefName` is the queue branch, skip `gh pr create`. If push fails, `gh` is not on PATH, create fails, there is no open PR, the open PR is not a draft, or the base is not the queue branch, write `ถาม:`. Do not pass `--write`. The line must not be `รอรีวิว:`. The gate refuses the line.

Then run with `--write`. If the script prints `refused: pr-missing`, `refused: gh-missing`, `refused: pr-not-draft`, `refused: pr-base`, `refused: pr-duplicate`, or `refused: pr-failed` with `step: ถาม`, write `ถาม:`. Do not set `รอรีวิว:`.

Screen work, before `รอรีวิว:`, uses the JTek screen command or an existing check command on the board. Do not add a new check script.

```bash
python3 <jtek-skill folder>/scripts/jt-screen-check --root . --id <id>
```

Code-touching commits use `scripts/jt-diff-check`. A plan note is not that review. A name from `<TEK_SKILLS>` does not do this review.

When the gate prints `refused:`, use this map. Do not restate the condition.

| Output | Action |
|---|---|
| `step: ถาม`, `refused: related`, `refused: browser-empty`, `refused: start-down`, `refused: click-mismatch`, `refused: pr-missing`, `refused: gh-missing`, `refused: pr-not-draft`, `refused: pr-base`, `refused: pr-duplicate`, `refused: pr-failed` | Write `ถาม:`. Do not set `รอรีวิว:`. |
| `refused: setup-failed`, `refused: test-failed`, `refused: review-diff`, `refused: one-off-checker`, `refused: repeat-patch`, `refused: pair-not-passed` | Follow **เกณฑ์ 3 รอบ** in `loop.md` on the same card. Use the existing check commands on the board. Do not set `รอรีวิว:`. |
| any other `refused:` | Stop. Do not set `รอรีวิว:`. Do not add a new check script. |

Done when you have run the printed command, or the script told you to stop, and the line is not marked `merge:`.
