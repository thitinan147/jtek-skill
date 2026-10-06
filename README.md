# jt-card-gate

This is the loop for the open repo, not a catalog of dozens of skills. You do not pick a skill. The agent calls the next step through `/jt-next-step`. The queue and the status live on this repo's board. You change the words on the line. The agent works only the cards that line allows. You call `/jt-send-back`, `/jt-merge`, and `/jt-drop-card` yourself. The agent does not call those three commands. `/jt-next-step` cannot merge. The rules belong to this skill. They are not copied into the open repo.

## Install

Once per machine.

```bash
npx skills add thitinan147/jtek-skill -g
```

## Start

Open the git repo you will work in. Stay on the branch that will hold the queue. Leave no dirty files outside `card-loop/`. Then run `/jt-next-step`.

You do not pick a skill. The agent runs the next step the rules allow. You answer until you accept a draft when that step asks. This command cannot merge.

## Before `review:`

Shared policy is `skills/jt-card-gate/references/loop.md`. `skills/jt-next-step/gate.py` enforces it. `/jt-do-work` runs `gate.py reach-review` and trusts that output. Read those files for the rules. This page does not restate them.

When the gate fails, the only moves are `ask:` or a human `/jt-send-back`, `/jt-merge`, or `/jt-drop-card`. Do not skip the gate. Do not write `review:` yourself. Do not invent a one-off checker.

Use the existing check commands on the board, including JTek `scripts/jt-screen-check` for screen work. A new check script that the card did not order cannot reach `review:`. A repeated fault on the same `layer:` needs an `update-rule` row after the rule or the check script changes. A row with no such file change is not enough. Do not split into parallel agents while `refs` is unlinked.

The line must not be `review:` until the gate allows it. If a draft pull request cannot be opened, write `ask:`.

```bash
gh pr create --draft --base <queue> --head card-<id> --title "<id>" --body "card <id>"
```

With a remote, push `card-<id>` and open that draft into the queue branch after the other gates pass. `gh` must be available, and no open pull request may already exist for that head. With no remote, the line is `review: local`. The human merges that pull request on GitHub.

## Commands

| Command | What it does |
|---|---|
| `/jt-new-board` | Create `card-loop/board.md`, fill the table from the repo and skill names from **Search**, and ask once for the paired repo name. |
| `/jt-ask-brief` | Ask what to do, then write `card-loop/brief.md`. Do not create a card. |
| `/jt-new-card` | Ask until the human accepts the draft. One call can create several cards and their board lines. |
| `/jt-read-board` | Read the queue. Do not start work. |
| `/jt-find-skills` | Offer `<REPO_SKILLS>` names for the open repo and `<TEK_SKILLS>` names for the current loop moment. The human chooses. Do not install. Do not write the board until the human accepts. |
| `/jt-do-work` | Work every card the line allows. Skip `review:`. Run `gate.py reach-review` and trust it. Do not write `review:` yourself. |
| `/jt-open-work` | Open a card that is `review:` and compare `pass`. Do not change the line. |
| `/jt-send-back` | Change `review:` to `send-back:`. |
| `/jt-merge` | Set the line mark to `merge:` when `landed: ancestor` or `landed: squash`, including a merge through a pull request. Do not open a PR, merge a PR, or run git merge. |
| `/jt-drop-card` | Change `- [ ]` to `- [x]`, append `drop:` plus the reason, and do not delete other lines. |
| `/jt-move-card` | Move a board line only. Do not change that line's status, touch code, or merge. |
| `/jt-next-step` | Read the board line and do the next step the rules allow. Do not merge. Stop when same-`layer:` cards are still unlinked. |

`/jt-merge` runs `python3 <jt-next-step skill folder>/gate.py landed --root . --id <id>` and changes only the line mark. `landed: ancestor` means the `card-<id>` commit is on the queue branch. `landed: squash` means the pull request whose head is `card-<id>` has status `MERGED`, including a squash that makes `git merge-base --is-ancestor` fail. The script does not run git merge. On `refused: not-landed`, the human has not landed the code yet.

In Codex, use `$` instead of `/`. You can type only the command name.

You can append a card id to `/jt-new-card`, `/jt-open-work`, `/jt-send-back`, `/jt-merge`, `/jt-drop-card`, and `/jt-move-card`. `/jt-do-work` does not take an id, because it works every card the line allows. `/jt-drop-card` takes a reason after the id.
