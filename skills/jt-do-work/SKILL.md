---
name: jt-do-work
description: Work every card the board allows, one branch and one draft pull request each. Skip lines marked รอรีวิว or an open ถาม, skip a card whose files overlap those lines, and continue ส่งกลับ on the same branch after merging in the queue branch. Use when the user runs /jt-do-work or asks to do the next cards.
license: MIT
metadata:
  author: Thitinan
  version: "20"
  short-description: Do the card the board line allows
---

# jt-do-work

Work in the open repo. Commit locations are under **ที่อยู่ของ commit** in `skills/jt-card-gate/references/loop.md`. Open other skills per `references/skills.md` in that skill. Commit form is under **มาตรฐาน commit** in the same file.

`loop.md` is the shared policy. This file is the procedure. `skills/jt-next-step/gate.py` enforces. Do not restate the gate here.

One round holds one card. The card is done when the line is `รอรีวิว:` or `ถาม:`. Then return to **Pick a card**.

Before work, read these headings in `loop.md` and follow them.

- Closed intent. **เจตนาปิดแล้ว**.
- Irreversible work. **งานที่ย้อนกลับไม่ได้**.
- Three evidence rounds. **เกณฑ์ 3 รอบ**.
- When review is forbidden. **กติกา** and **สรุป**.

If the gate refuses, follow **Write ถาม** or **เกณฑ์ 3 รอบ**. Do not write `รอรีวิว:` yourself.

## Pick a card

1. If `card-loop/board.md` is missing, stop and say to run `/jt-new-board` first. If the file exists and `สาขาคิว:` is empty, or `<TEST_CMD>` is empty, or `<STACK_LOCK>` is empty, stop the whole queue and name the field to fill. The value `ไม่มีชุดเทส` is allowed. Do not run it as a command.
2. If files outside `card-loop/` are dirty, stop the whole queue. If the human edited files under `card-loop/`, commit them on the queue branch before you create the card branch.
3. Check out the queue branch.
4. Make three passes in this order. On each pass, walk **ทำก่อน**, then **งานหลัก**. Walk **เก็บเล็ก** only when every `- [ ]` under **ทำก่อน** and **งานหลัก** is done. When you find a card, stop. Do not continue past the rest.
   - Pass one. The first line marked `ส่งกลับ:`.
   - Pass two. The first line marked `ถาม:` whose card heading **ถาม** is empty.
   - Pass three. The first line with no `ถาม:`, `รอรีวิว:`, or `ส่งกลับ:`, and with `card-loop/backlog/<id>.md`.
5. On every pass, skip `รอรีวิว:`. Skip `ถาม:` while heading **ถาม** still has text. Skip a line with no card file. Skip a card whose **ไฟล์ที่แตะได้** uses the same path as another line that is still `รอรีวิว:` or `ส่งกลับ:`. A parent line is a line `**<parent>**` with a line `**<parent>.<child>**` below it. Do not pick that parent line. A section heading such as `## งานหลัก` is not that line. When every child is done, change the parent's `- [ ]` to `- [x]`, append `ครบ:`, and commit only `card-loop/board.md` on the queue branch.
6. If step 4 finds no card, stop the whole queue here. A line left on `รอรีวิว:` is not a reason to stop. For a card skipped because files overlap, say it waits until that other card is on the queue branch.
7. When you have a card, and its `ชั้น:` matches another card that is still open, and **อ้างอิง** does not point at the other card, follow **Write ถาม** and return to step 1. When they are linked, do them one at a time in this order. Do not split into parallel agents. Then check **เจตนาปิดแล้ว** in `loop.md`.
   - If the line is `ถาม:` and intent is closed, delete `ถาม:` from the line, commit only `card-loop/board.md` on the queue branch, and go to **Do the work**.
   - If the line has no `ถาม:` and intent is closed, go to **Do the work**.
   - Otherwise follow **Write ถาม** and return to step 1. Before you write `ถาม:` because two outcomes remain, open one `<TEK_SKILLS>` name whose description mentions grill or interview, if one exists.

The card id is the text inside `**` on the line. The line form is under **ที่อยู่ของ commit**.

## Write ถาม

1. If branch `card-<id>` exists and work files are uncommitted, commit them on that branch. Add one row to **การตัดสินใจ**. Commit only the plan file on that branch.
2. Check out the queue branch.
3. Replace an empty `ถาม:` heading in the card with these three lines. Do not write the heading twice. On the board line, append `ถาม:`. The item stays `- [ ]`.

```markdown
ถาม: <หนึ่งคำถาม>
ทำไมถึงไปต่อไม่ได้: <เหตุ>
ทางที่เห็น: <ทางที่คนเลือกได้>
```

4. Commit only `card-loop/board.md` and `card-loop/backlog/<id>.md` on the queue branch.
5. Return to **Pick a card**.

Done when the queue-branch line contains `ถาม:` and the card heading **ถาม** contains a question.

## Do the work

If the line is `ส่งกลับ:` and branch `card-<id>` does not exist, follow **Write ถาม**.

If branch `card-<id>` already exists, check it out and merge the queue branch into this branch. Keep the existing draft PR. Create a new branch only from the queue branch. Do not create it from another `card-<id>` branch. On a conflict, edit this branch to match **ทำ**, then rerun the relevant tests. If you cannot resolve the conflict without choosing for the human, follow **Write ถาม**. If **ไฟล์ที่แตะได้** in the plan is empty, copy it from the card before you edit work files.

If the branch does not exist yet, create `card-<id>` from the queue branch and check it out. Create `card-loop/plan/<id>.md` from `assets/plan.template.md` in skill `jt-card-gate`. Set Branch to `card-<id>`. Copy **ไฟล์ที่แตะได้** from the card. Commit only the plan file on this branch.

If the line is `ส่งกลับ:` and `สถานะรอบ` is not `ส่งกลับ`, set `รอบหลักฐาน` to 1 and `สถานะรอบ` to `ส่งกลับ`, then commit only the plan file on `card-<id>`. If `สถานะรอบ` is already `ส่งกลับ`, keep the current round.

Then, on `card-<id>`:

- For a `fix` whose cause is still unclear, before a red test, open one `<TEK_SKILLS>` name whose description mentions diagnose or debug, if one exists.
- While editing production code, open one `<TEK_SKILLS>` name whose description mentions YAGNI, stdlib, or delete, if one exists.
- For `feat` or `fix`, write a test of that behavior that is red because the assertion is not true yet, then make it green.
- For `test`, the added test is green, and you do not change production behavior to make it pass.
- Screen work of every kind needs `เห็นจอ: ใช่` plus `เริ่ม:`, `พอร์ต:`, `รอ:`, and `คลิก:` on the card. Start the real frontend and the real backend from those commands. The click must exit 0 and match **ตรวจผ่านเมื่อ**. If start fails or the click fails, follow **Write ถาม**.
- For a screen `fix`, record the steps that show the bug. The same steps after the fix must not show it.
- Edit only files under **ไฟล์ที่แตะได้** in the plan.
- For irreversible work, follow **งานที่ย้อนกลับไม่ได้** in `loop.md`, then **Write ถาม**.
- If the whole evidence set fails, follow **เกณฑ์ 3 รอบ** in `loop.md`.
- Each time you choose a path, write `ถาม:`, or the evidence passes, add one row to **การตัดสินใจ**.
- If this card and another open card share `ชั้น:`, change the skill rule, the gate, or the lint or check script, then add an `อัปเดตกติกา` row in **การตัดสินใจ**. The evidence cell is that path. Do not patch only this card's code. A row alone, with no such file in the diff, cannot open review.

Before you open review, run the existing check commands on the board. Run `<TEST_CMD>`, `<TYPECHECK_CMD>`, and `<LINT_CMD>` when the field has a command and the touched files are in scope. For `feat` or `fix`, run `<TEST_CMD>` unless the value is `ไม่มีชุดเทส`. For any other kind whose value is `ไม่มีชุดเทส`, write in the review notes that there is no test suite. Do not create a new check script for this round unless **ทำ** says to create that file. Screen work, before `รอรีวิว:`, uses JTek `scripts/jt-screen-check` or another existing check command on the board. With `<BROWSER_TOOL>` set, start from `เริ่ม:` and `พอร์ต:`, and set `คลิก:` to `python3 <jtek-skill folder>/scripts/jt-screen-check --root . --no-start`, including other pages that read the same state. With `<BROWSER_TOOL>` empty on screen work, follow **Write ถาม**. When the work is not on screen and `<BROWSER_TOOL>` is empty, write which surface could not be checked.

## Paired repo

Read the name from the `คู่:` line on the primary repo's board. Do not ask again where the paired repo is. That name is the folder beside the primary repo. Do not invent a repo name.

If the line is `ไม่มี` or empty, follow the single-repo path. Do not wait for a second side. Do not create files in another repo.

A card that touches both sides is one card. The card heading and the board line contain `·` plus the name on the `คู่:` line. A card that does not touch the pair does not include that name.

The card's work may happen in the paired repo, on branch `card-<id>`. The queue and every status stay on the primary repo's board only. Do not set status in the paired repo. Do not create `card-loop/board.md` there. Do not move the whole queue off the primary repo.

Create `card-loop/paired.md` in the paired repo only when this card touches that repo. The contents point back at the primary repo's folder name and `card-loop/board.md`. Under `card-loop/` in the paired repo, this file is the only one allowed. Do not create this file only because the board recorded the name.

The human merges both repos.

## Open for review

Read **กติกา** and **สรุป** in `loop.md` first. If those rules block review, follow **เกณฑ์ 3 รอบ** on this card. Do not set `รอรีวิว:`.

After a commit whose kind is `feat`, `fix`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, or `revert`, and before `รอรีวิว:`, open every name in `<REPO_SKILLS>`. `docs` does not open. An empty row opens nothing else. If a name in that row is not on this machine, review this card's diff yourself before `รอรีวิว:`, even when another name in the row did open. A name from `<TEK_SKILLS>` does not do this review. A note in the plan is not that review. Do not skip that review. If you cannot review the diff, do not set `รอรีวิว:`. Follow **เกณฑ์ 3 รอบ**. The gate refuses that line. If an opened skill passes but the evidence in this section is incomplete, follow **เกณฑ์ 3 รอบ**. On a card that touches code, record the review under `## รีวิว diff` in the plan, with `- commit:` as the full SHA of the latest commit, `- ผู้รีวิว:`, and `- เจอ:`, before `รอรีวิว:`. Run `python3 <jtek-skill folder>/scripts/jt-diff-check --root . --id <id>` and require exit 0. A review heading alone is not enough.

Commit the card's work on `card-<id>` first. Check **ตรวจผ่านเมื่อ** against that commit. This commit does not contain the word `รอรีวิว:` and does not contain `card-loop/board.md`, unless **ทำ** on the card says to edit that file.

Check out the queue branch. Run reach-review without `--write`.

```bash
python3 <jt-next-step skill folder>/gate.py reach-review --root . --id <id>
```

Trust the output. Do not write `รอรีวิว:` yourself.

If the script prints `allowed` and `git remote` is empty, rerun the same command with `--write --link local`. The script sets the line to `รอรีวิว: local`.

If the script prints `allowed` and `git remote` has a name, push only `card-<id>` and open one draft PR into the queue branch when no open pull request exists for that head. Do not open a duplicate. Do not create a remote.

```bash
git push -u origin card-<id>
gh pr list --head card-<id> --base <สาขาคิว> --state open --json number,isDraft,url,baseRefName
gh pr create --draft --base <สาขาคิว> --head card-<id> --title "<id>" --body "card <id>"
```

If `gh pr list` already has an item whose `isDraft` is true and whose `baseRefName` is the queue branch, skip `gh pr create`. If `gh` is not on PATH, push fails, create fails, there is no open PR, the open PR is not a draft, or the base is not the queue branch, follow **Write ถาม**. Do not pass `--write`. The line must not be `รอรีวิว:`.

When the draft exists, run reach-review with `--write`. The script checks the pull request. If it prints `refused: pr-missing`, `refused: gh-missing`, `refused: pr-not-draft`, `refused: pr-base`, `refused: pr-duplicate`, or `refused: pr-failed` with `step: ถาม`, follow **Write ถาม**. Do not set `รอรีวิว:`.

For any other `refused:`, use this map. Do not restate the gate condition.

| Output | Action |
|---|---|
| `step: ถาม`, `refused: related`, `refused: browser-empty`, `refused: start-down`, `refused: click-mismatch` | Follow **Write ถาม**. Do not set `รอรีวิว:`. |
| `refused: setup-failed`, `refused: test-failed`, `refused: review-diff`, `refused: one-off-checker`, `refused: repeat-patch`, `refused: pair-not-passed` | Follow **เกณฑ์ 3 รอบ** on this card. Do not set `รอรีวิว:`. |
| any other `refused:` | Stop. Do not set `รอรีวิว:`. Do not add a new check script. |

When the script passes, the line is `รอรีวิว:` followed by that draft URL. Set `สถานะรอบ` in the plan to `รอรีวิว`. Commit only the plan file on `card-<id>`. Check out the queue branch and commit only `card-loop/board.md`. The item stays `- [ ]`.

Return to **Pick a card**.

Done when **Pick a card** step 6 is true.
