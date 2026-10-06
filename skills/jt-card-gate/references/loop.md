# Card loop, version 20

These rules belong to skill `jt-card-gate`. They are not copied into the open repo.

The queue lives in the open repo. Work for a card whose heading names the paired repo may happen in that repo, and status does not live there.

The human answers `/jt-ask-brief` until they accept the draft. The agent then writes `card-loop/brief.md`. The human answers `/jt-new-card` until they accept the draft. The agent then creates the card files. The human changes the words on the line. The human calls `/jt-send-back` `/jt-merge` `/jt-drop-card`. The agent does not call those three commands.

## Commands

| Command | What it does |
|---|---|
| `/jt-new-board` | Create `card-loop/board.md`, fill the table from the repo and skill names from **Search**, and ask once for the paired repo name. |
| `/jt-ask-brief` | Ask what to do, then write `card-loop/brief.md`. Do not create a card. |
| `/jt-new-card` | Ask until the human accepts the draft. One call can create several cards, then create the cards and their board lines. |
| `/jt-read-board` | Read the queue. Do not start work. |
| `/jt-find-skills` | Offer `<REPO_SKILLS>` names for the open repo and `<TEK_SKILLS>` names for the moments the loop already uses. The human chooses. Do not install. Do not write the board until the human accepts. |
| `/jt-do-work` | Do every card that can be worked. Skip a card that is `review:`. |
| `/jt-open-work` | Open work that is `review:`. Compare the `pass` heading. Do not change the line. |
| `/jt-send-back` | Change `review:` to `send-back:`. |
| `/jt-merge` | Change the mark on the line to `merge:` after the card commit is on the queue branch. This command does not run git merge, does not open a PR, and does not merge a PR. |
| `/jt-drop-card` | Change `- [ ]` to `- [x]` and append `drop: <reason>`. Do not delete other lines. |
| `/jt-move-card` | Move a board line only. Do not change that line's status, touch code, or merge. |
| `/jt-next-step` | Read the line on the board and do the next step the rules allow. Do not merge. |

In Codex, use `$` instead of `/`. You can type only the command name.

You can append an item id to `/jt-new-card`, `/jt-open-work`, `/jt-send-back`, `/jt-merge`, `/jt-drop-card`, and `/jt-move-card`. `/jt-do-work` does not take an id, because it works every card that can be worked. `/jt-drop-card` takes a reason after the id, for example `/jt-drop-card 12 not doing this`.

## Files in the open repo

- `card-loop/board.md` is the queue. The words on the line are the only status, plus this repo's test-command table.
- `card-loop/brief.md` is the work the human wants this round, after they accept the draft.
- `card-loop/backlog/<id>.md` is a card the human accepted.
- `card-loop/plan/<id>.md` is the agent's working notes, and the `decisions` table the human reads during `/jt-open-work`.
- The paired repo may contain only `card-loop/paired.md`, and only when a card touches that repo. That file points back at the primary repo. It has no board and no status.

Read the table in `card-loop/board.md` before work. An empty `<STACK_LOCK>` cell or an empty `<TEST_CMD>` cell means the board is not ready. Stop the whole queue before you pick a card. A filled `<STACK_LOCK>` has at least a language, a framework, the test command or the check kind, and what this repo must not use. The value `no-suite` means there is no suite to run. When `<SETUP_CMD>` has a command, the gate runs it in the card worktree before tests and before start. The only skills a card may open are the names in `<TEK_SKILLS>` and `<REPO_SKILLS>`, per [skills.md](skills.md).

## Paired repo

Ask once. `/jt-new-board` asks what the paired repo is named, then writes one `pair:` line on the primary repo's board. The line is the name the human answered, or the word `none`. Do not ask again after that. Do not invent a repo name. That name is the folder beside the primary repo.

The queue and every status live only on the primary repo's board. Work may happen in the paired repo, but do not set status there. Do not create a second board. Do not move the whole queue off the primary repo.

A card that touches both sides is one card. The heading contains `·` plus the name on the `pair:` line. A card that does not touch the pair does not include that name.

If the heading names the paired repo, the gate does not set `review:` until both sides have passed, and it sets that status once on the primary repo's board. When the `pair:` line is `none`, follow the single-repo path. Do not wait for a second side. The gate refuses.

The paired repo may contain only `card-loop/paired.md`, and only when a card touches that repo. That file points back at the primary repo. Do not create this file only because the board recorded the name.

The human merges both repos. The agent does not call `/jt-send-back`, `/jt-merge`, or `/jt-drop-card`. The human merges both repos into the queue branch first, then calls `/jt-merge`. That command changes only the mark on the primary board line. It does not run git merge, does not open a PR, and does not merge a PR.

Both sides have passed when each repo has branch `card-<id>` and that repo's test command exits 0. The primary repo's command is `<TEST_CMD>`. The paired repo's command is that repo's test script. A repo with no test suite can pass that side.

## Where commits go

The board line is the whole queue, so it lives on a different branch from each item's code.

- `queue` is the name on the `queue:` line in `card-loop/board.md`. Read the board from that branch.
- Commit `card-loop/board.md`, `card-loop/brief.md`, and `card-loop/backlog/` on the queue branch.
- Commit the item's code and `card-loop/plan/<id>.md` on branch `card-<id>`.
- An item line is `- [ ] **<id>** <short name> (<kind>)`, followed by `ask:`, `review:`, or `send-back:` when it has a status. A closed item is `- [x]` followed by `merge:`, `drop:`, or `complete:`.
- `/jt-do-work` pushes only `card-<id>`, then opens a draft PR into the queue branch when `git remote` has a name and `gh` is available. When no open PR exists for that head, use `gh pr create --draft --base <queue> --head card-<id>`. If one is already open, do not open another.
- With no remote, write the link `local` and go to the next card. If the draft PR cannot be opened, write `ask:`. The line must not be `review:`. The gate refuses.
- `/jt-merge` changes only the `merge:` mark on the line. It does not open a PR, does not merge a PR, and does not run git merge. The human merges on GitHub until the `card-<id>` commit is on the queue branch (`git merge-base --is-ancestor`), including a merge through a pull request, and then calls `/jt-merge`. Push the queue branch with a normal push when that branch has a remote.
- If files outside `card-loop/` are dirty, stop the whole queue. If the human edited files under `card-loop/`, commit them on the queue branch before you create the item branch.
- For a card you are holding whose line has no `ask:` or `review:` yet, follow **Three rounds** on that card. When the rounds are used up, write `ask:` and go to the next card.

Each time you choose a path, stop for `ask:`, or the evidence passes, add one row to the plan's `decisions` table. Record what you decided, why, and evidence as a path, a test command, or a commit.

The only statuses to trust are the words on the line. They are `ask:`, `review:`, `send-back:`, `merge:`, `drop:`, and `complete:`.

```text
human accepts the draft from /jt-new-card
    -> agent runs /jt-do-work
        intent still open -> write ask on the card and the board line -> do not open review
        intent closed -> work on the branch -> record tests and screen evidence
            irreversible, or 3 rounds used and still failing -> write ask -> do not request review
            passed and no remote -> set the line to review local -> pick the next item
            passed and a remote exists -> push, open a draft PR into the queue branch, set the line to review -> pick the next item
                human later runs /jt-open-work
                    accept -> human merges on GitHub, then /jt-merge
                    incomplete -> /jt-send-back
                    drop -> /jt-drop-card
            draft PR cannot be opened -> write ask -> the line is not review
```

## Rules

- Work one branch at a time, branched from the queue branch. One item may open one draft PR into the queue branch. The queue does not stop at `review:`.
- If a card's `files` heading uses the same path as a line that is still `review:` or `send-back:`, wait until that card is on the queue branch.
- If the branch already exists, bring the latest queue branch into that branch before you continue, then run the tests again.
- An item whose line is `send-back:` continues the same work on the same branch. Do not open a new draft PR. When the evidence passes, change the line to `review:` and pick the next item.
- If intent is not closed, the work is irreversible, or 3 rounds are used and the evidence still fails, write `ask:` at the end of the card and at the end of the line, then skip to an item that can be worked.
- Open review only when the evidence is complete, the relevant tests are green, and the diff stays inside `do` and does not cross `out`.
- Before you open review, use the existing check commands on the board, which are `<TEST_CMD>`, `<TYPECHECK_CMD>`, and `<LINT_CMD>`. Do not create a new check script for this round unless `do` says to create that tool. If you create one without that order, the line must not be `review:`. The gate refuses.
- When the same layer fails again, change the skill rule, the gate, or the lint or check script, rather than patching only that card's code, and record an `update-rule` row in the plan's `decisions` table. If you patch only one card, or you record a row while the rule file does not change, the line must not be `review:`. The gate refuses.
- Open cards that share `layer:` must be combined or done one at a time. Put the other card's id under `refs`. Do not split into parallel agents without a link. `/jt-do-work` may write `ask:`. `/jt-next-step` may stop.
- The agent does not check `merge:` or `drop:`, and does not merge the main branch.
- Do not push the main branch until the human merges it.
- Do not put a model trailer on a commit.

### Closed intent

The card has one kind, one path, and `do`, `out`, and `pass` headings that can be carried out without choosing for the human.

Intent is not closed when the scope is vague, two paths have different outcomes, you would delete something people may still use and the card has not chosen, or you would change a contract other callers use and the card has not chosen.

### Irreversible work

Write `ask:` on the card and the line, then skip that card. Do not continue that card when the work would delete production data, force-push, send a message or an artifact out of the repo, or merge `card-<id>` into the queue branch.

You may push the item branch to open a draft PR. Do not merge that PR.

### Three rounds

One round is one full attempt. The evidence is that the relevant tests are green, and for screen work of every kind, not only `fix`, the same steps on the same screen do not show the bug. Screen work that cannot be clicked does not count as this round. Write `ask:`.

Start with `round` set to 1 in the plan. After a full attempt still fails, read the current value first. If it is less than 3, add 1 and try again. If the value is already 3 and it still fails, write `ask:` on the card and on the line. Do not request review. A red test you wrote on purpose before the fix does not count as a failed round.

A human `/jt-send-back` is a new request. The first time the agent sees it, set `round` to 1 and set `round-status` in the plan to `send-back`. If the plan is already `send-back`, do not reset the round again.

When the evidence passes while the line is `send-back:`, set `round-status` to `review` on `card-<id>`, change the queue-branch line to `review:`, and pick the next item.

Count rounds only from the `round` field in the plan.

### Ask

Put `ask:` at the end of the card and at the end of the line. The item stays `- [ ]`. Commit `card-loop/board.md` and `card-loop/backlog/<id>.md` on the queue branch, then skip to an item that can be worked.

```markdown
ask: <one question>
blocked: <why work cannot continue>
options: <choices the human can pick>
```

The human answers by clearing the `ask` heading in the card and editing the card until intent is closed. The human does not have to edit the line.

When the agent sees an empty `ask` heading and closed intent, delete `ask:` from the line, commit that change under `card-loop/`, and continue the item.

## Ticket kinds

One value from the set Conventional Commits allows, and the set `@commitlint/config-conventional` uses.

| Kind | Meaning | Evidence before review opens |
|---|---|---|
| `feat` | New behavior or a new interface | That behavior's tests are green, via `<TEST_CMD>` or the command the `pass` heading names |
| `fix` | A bug whose behavior is broken | That behavior's tests are green, via `<TEST_CMD>` or the command the `pass` heading names |
| `docs` | Docs only | Do not touch production code |
| `style` | Formatting, and the code's meaning does not change | The existing suite passes |
| `refactor` | No bug fix and no new behavior, including deletion of something unused | The existing suite passes |
| `perf` | Faster, with the same user-facing behavior | The existing suite passes |
| `test` | Add or change tests | The added tests are green, without changing production behavior to make them pass |
| `build` | The build system or dependencies | The existing suite passes |
| `ci` | CI scripts | The existing suite passes |
| `chore` | Other work that does not change source or tests | The existing suite passes |
| `revert` | Revert an earlier commit | After the revert, the existing suite passes |

After a commit whose kind touches code, open `<REPO_SKILLS>` per [skills.md](skills.md). `docs` does not open. If you cannot review the diff, the line must not be `review:`. The gate refuses. A note in the plan does not count. The review counts when `scripts/jt-diff-check` exits 0 and the plan heading `review-diff` cites the latest code commit. A name from `<TEK_SKILLS>` does not do this review.

Screen work of every kind, not only `fix`, must start the real frontend and the real backend, then click what the `pass` heading names. How to start, which ports, and the click steps live in that repo.

If `<BROWSER_TOOL>` is empty, start does not come up, or the click misses the `pass` heading, write `ask:`. The line must not be `review:`. The gate refuses.

Before the line is `review:`, screen work uses the JTek screen command at `scripts/jt-screen-check` or a check command already on the board. Do not create a new check script for this round.

For a screen `fix`, make the bug appear on the same screen before the fix, then repeat the same steps after the fix until it does not appear. Green tests with the bug still on screen cannot open review.

When `<TEST_CMD>` is `no-suite` and a `feat` or `fix` card does not name a test command under `pass`, intent is not closed. Write `ask:` and request a test command. An empty `<TEST_CMD>` cell stops the whole queue before you pick a card.

For any other kind, when `<TEST_CMD>` is `no-suite`, write in the review notes that there is no test suite. An empty cell is not this value.

Name tests after the scenario or the behavior.

### Commit standard

```text
<kind>(<id>): <summary>
```

`<kind>` matches the card kind. `<id>` matches the card file name. `<summary>` is English, imperative, present tense, not capitalized, and has no trailing period.

For a kind other than `docs`, leave a blank line and then one sentence of why. Kind `docs` ends at the subject line. One commit has one kind. Work outside the queue has no `<id>`. If it belongs in the loop, create a card first.

A commit that changes only files under `card-loop/` uses `docs(<id>):` when it is about one item. Several items in one commit use `docs: add accepted cards`.

## Steps for each command

The steps that finish a command live in that command's `SKILL.md`. Read the shared rules above only for the heading that command points at.

The human calls `/jt-open-work` before deciding. An empty `decisions` table, or a diff that does not match the card, means the evidence is incomplete. Do not check `merge:`.

## Summary

| Result | What happens next |
|---|---|
| Intent is not closed | `ask:` on the card and the line. The human clears `ask`, then calls `/jt-do-work`. |
| Irreversible, or 3 rounds used | `ask:` on the card and the line |
| The screen cannot be clicked | `ask:` on the card and the line |
| Evidence passed | Open a draft PR into the queue branch, append `review:`, and pick the next item. If it cannot be opened, write `ask:`. |
| A new check script the card did not order | Do not open review |
| The same layer failed again and the rule is unchanged | Do not open review. Record `update-rule` after the rule or the check script changes. A row alone is not enough. |
| Same-layer cards are still unlinked | `ask:`, or stop. Do not split agents. |
| The human accepts | `/jt-merge` |
| The human sends it back | `/jt-send-back`, then `/jt-do-work` |
| The human drops it | `/jt-drop-card` |
