---
name: jt-review-work
description: HUMAN-ONLY COMMAND. Never invoke or execute this skill autonomously. Reads card-loop/board.md, inspects review: cards, checks landed status, and records human decisions (merge:, send-back:, drop:, or moving lines). Use when the human explicitly invokes /jt-review-work to inspect or close reviewed cards.
disable-model-invocation: true
license: MIT
compatibility: Codex, Claude Code, Cursor, Grok Build, and Antigravity. Needs a git repo.
metadata:
  author: Thitinan
  version: "21"
  short-description: Human-only review and board decision command
---

# jt-review-work

**HUMAN-ONLY COMMAND.** Never invoke this skill autonomously during `/jt-work-queue`.

## 1. Read Board & Check Landed Cards First

1. Read `card-loop/board.md` from the `queue:` branch without modifying files.
2. For every open card with status `review:`, run [scripts/landed.py](scripts/landed.py):
   ```bash
   python3 <this-skill-dir>/scripts/landed.py --root . --id <id>
   ```
3. Surface any `review:` cards that already report `landed: ancestor` or `landed: squash` **first** so the human can immediately mark them `merge:`.
4. Report the remaining queue status (`review:`, `send-back:`, `ask:`, and ready cards).

## 2. Open a Card for Review

When inspecting a `review:` card `<id>`, present:
1. Card `(<kind>)` from `card-loop/board.md`, plus `pass:`, `do:`, `out:`, and `files:` from `card-loop/backlog/<id>.md`.
2. Scope & style checks on `card-<id>` vs `<queue>`:
   - Run `git diff --name-only <queue>...card-<id> -- . ':(exclude)card-loop'` and compare against `files:` to report any files touched outside `files:`.
   - When the card kind is `style`, run `git diff -w --ignore-blank-lines --numstat <queue>...card-<id> -- . ':(exclude)card-loop'` to report non-whitespace changes.
3. Plan `## decisions`, `## review-diff`, and `## Done when` from `card-<id>:card-loop/plan/<id>.md` (when present).
4. `git diff <queue>...card-<id>` and test/screen evidence.

## 3. Record the Human's Decision (on `<queue>` branch, clean tree)

- **Accept (`merge:`):** Verify `python3 <this-skill-dir>/scripts/landed.py --root . --id <id>` prints `landed: ancestor` or `landed: squash` (if not landed yet, tell the human to merge on GitHub/locally first). Never run `git merge`, open a PR, or merge a PR. Change only `- [ ]` to `- [x]` and status to `merge:`, then commit `card-loop/board.md`.
- **Send back (`send-back:`):** Change `review:` to `send-back: <reason>` on `card-loop/board.md` (stays `- [ ]`) and commit on `<queue>`.
- **Drop (`drop:`):** Require a `<reason>`. Change `- [ ]` to `- [x]` and append `drop: <reason>` on `card-loop/board.md`, commit on `<queue>`, and close any open PR without merging.
- **Move (`first` | `main` | `later` | `closed`):** Move only that line on `card-loop/board.md` without changing its status or touching code, then commit on `<queue>`.
