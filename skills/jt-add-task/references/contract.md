# Task Queue Contract, version 24.6

This contract belongs to `jt-setup`, `jt-add-task`, and `jt-work`. The gate is `scripts/gate.py` in each of those skills (one module). All queue files live under `jt-queue/` in the open repository.

## 1. Files & Branch Locations

- `jt-queue/board.md`: Queue state and project command table (`<TEST_CMD>`, `<AFFECTED_TEST_CMD>`, `<SETUP_CMD>`, `<TYPECHECK_CMD>`, `<LINT_CMD>`, `<SECURITY_CMD>`, `<VERIFY_CMD>`, `<DENYLIST>`, `<BROWSER_TOOL>`, `<STACK_LOCK>`). An empty `<DENYLIST>` uses `jt-queue/denylist.txt` when that file exists.
- `jt-queue/brief.md`: Optional round brief accepted by the human.
- `jt-queue/tasks/<id>/task.md`: Task contract (`kind:`, `size:`, `spec:`, `layer:`, `screen:`, `do:`, `out:`, `pass:`, `files:`, `needs:`, `refs:`, `ask:`; the screen-check command fields are described in `task.template.md`).
- `jt-queue/tasks/<id>/plan.md`: Required for `Standard` tier, optional for `Quick` tier. Contains `## Goal`, `## Architecture`, `## Files`, `## Steps`, `## Out of scope`, `## Done when`, `## Escape`, `## evidence`, `## review-diff`, `## ai-review`, and `## decisions`.

Commit `board.md`, `brief.md`, `tasks/<id>/task.md`, and `tasks/<id>/plan.md` so a teammate can resume. A tracked board, brief, and `task.md` are read from `<queue>`. A tracked `plan.md` is read from the task branch. A gitignored or untracked file is still read from the working tree, so a queue that stays local keeps working. Do not commit `jt-queue/lessons.md` (notes for this agent, not the task), any `.env` or private key, or `.git/jt-queue/`: `approved-commands.json` is the permission to run shell commands and must not travel in a commit, `logs/` can hold secrets, and `attempts.json` is this machine's round counter.

## 2. Board Line Format & Status Permissions

```text
- [ ] **<id>** <short name> (<kind>) [ask: | review: <link> | send-back: <note>]
- [x] **<id>** <short name> (<kind>) merge: | drop: <reason>
```

- `<id>` must match `^\d+(\.\d+)*$` with no path traversal.
- Allowed status tokens: `ask:`, `review:`, `send-back:`, `merge:`, `drop:`. Any other colon token in the status slot stops the queue with `unknown-status`.
- **Agent permissions:** May add task lines that an approved spec covers without a second approval, and other new task lines only after a human approves them. Must update status tokens on existing lines **only** via `gate.py ask` and `gate.py reach-review --write`. Never write `merge:` or `drop:`. Never run `gate.py approve-commands` and never change `<TEST_CMD>`, `<SETUP_CMD>`, `<LINT_CMD>`, `<TYPECHECK_CMD>`, `<SECURITY_CMD>`, `<VERIFY_CMD>`, or a task's screen-check commands to make a refusal pass; the human approves those commands once per machine (stored in `.git`, outside every branch). A spec approval does not replace that, and it does not merge.
- **Human permissions (`/jt-review`):** Writes `merge:`, `send-back:`, and `drop:`. Answers `ask:` by updating `jt-queue/tasks/<id>/task.md` until intent is closed and clearing the `ask:` heading; on the next run, `gate.py next` resumes the task (`question-cleared`) and `reach-review --write` replaces `ask:` with `review:`.
- `needs:` names work in another repository (for example a backend task for a frontend task) that must land first. It is text for the human: the gate never reads it and never refuses because of it.
- Same-topic tasks sharing `layer:` must link each other under `refs:`. Do not split into parallel agents without a link.

## 3. Adaptive Gate Tiers (`Quick` vs `Standard`)

The gate computes the task's tier from `(<kind>)` on `jt-queue/board.md`. A tracked board uses the kind at `git merge-base <queue> <branch>` (the task branch). A different kind on the current line raises the tier to `Standard`, and that tier does not return to `Quick`. A gitignored or untracked board uses the kind in the working tree, so editing `(<kind>)` there can raise or lower the tier.

- **Quick Tier** requires all 5 conditions:
  1. Task kind is `docs` or `style`: the merge-base kind when the board is tracked, otherwise the kind in the working tree.
  2. Every commit on the task branch outside `jt-queue/` has commit kind matching the task kind.
  3. Task does not set `screen: yes`.
  4. If `docs`: every changed file outside `jt-queue/` is a documentation file (`.md`, `.rst`, `.adoc`, or extensionless/doc-extension `README`, `LICENSE`, `CHANGELOG`, `NOTICE`, `AUTHORS`, `CONTRIBUTING`).
  5. If `style`: code files may change; non-whitespace changes (`git diff -w --ignore-blank-lines`) are reported in `style-changes:`.
- **Standard Tier:** All other tasks (`feat`, `fix`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`) and any `docs`/`style` task that escalates.

| Check | Quick | Standard |
|---|---|---|
| Exactly one task branch (`type/<ticket-id>-<slug>` or legacy `task-<id>-<slug>`) exists | ✓ | ✓ |
| Use existing check commands; no one-off checker script | ✓ | ✓ |
| `<TEST_CMD>` passes (or `no-suite`). `<VERIFY_CMD>` passes when that cell is not empty (empty is `skip`) | ✓ | ✓ |
| `<TYPECHECK_CMD>` then `<LINT_CMD>` when the cell is not empty (empty is `skip` and is not run). Quick does not run them | — | ✓ |
| A diff outside `jt-queue/` exists, and `## review-diff` cites the latest code commit, `verdict: pass`, and a `checked:` line. No such diff is refused (`no diff outside jt-queue/ to review`), not `repo-review: skip` | — | ✓ |
| `## ai-review` when the effective size is `medium` or `large` (`ai-review: skip` when `small`) | — | ✓ |
| Every `pass:` line of the task appears in `## evidence` of `plan.md` | — | ✓ |
| JTek `gate.py screen-check` when `screen: yes` | — | ✓ |
| Secret scan, first: `<SECURITY_CMD>` when that program is installed, otherwise `secret-suspect` (added `.env*` except `.env.example`, a private-key file, or a `PRIVATE KEY` block). `next: ask`. The output names the file or `file:line` and never the value | ✓ | ✓ |
| Deprecated names: `<DENYLIST>` or `jt-queue/denylist.txt`, each line `old -> replacement` (`;` separates pairs). A hit in the diff is `deprecated-name` and names the replacement. An empty list is `skip` | ✓ | ✓ |
| `test-weakening`: a deleted test file, or an added `.skip` / `.only` / `xit` / `@skip` / `xfail` marker, is reported on `allowed` and does not refuse. A rename or a skip the task asked for looks the same, so the human judges it, as with `outside-files:` | ✓ | ✓ |
| Fail-fast: stop at the first of secret, denylist, typecheck, lint, tests, verify. Print `step:` and `skipped:` (the next of those). `allowed` prints `gates:` as `secret`, `denylist`, `typecheck`, `lint`, `tests`, `verify`, `screen`, `review-diff`, `test-weakening` | ✓ | ✓ |
| Report `outside-files:` and `style-changes:` | ✓ (both) | ✓ (`outside-files:` only) |

## 4. Plan, Three Rounds, and Diff Review

- **Plan (`Standard` tier):** A `Done when` line is a command to run, or an artifact to open. If `Done when` has no command and no artifact, run `gate.py ask`. If `Escape` is empty, or an `Escape` line is true, run `gate.py ask` and do not set `review:`.
- **Three rounds:** One round is one full attempt. The evidence is that the relevant tests are green, and for screen work of every kind, not only `fix`, the same steps on the same screen do not show the bug. Screen work that cannot be clicked does not count as this round. The gate counts a round each time `<TEST_CMD>`, `<LINT_CMD>`, `<TYPECHECK_CMD>`, `<VERIFY_CMD>`, or setup fails in `reach-review` (retrying an unchanged commit counts too), and prints `round <n> of 3`. On the third it answers `next: ask`: run `gate.py ask` with what each round tried. `gate.py ask` starts the count again. `secret-suspect`, `secret-failed`, and `deprecated-name` do not count a round.
- **Diff review:** On `Standard` tier, review this task's diff yourself before `review:` and record it in `## review-diff`. A Standard task with no diff outside `jt-queue/` is refused. `docs` on the Quick tier does not need that review. Do not skip a review that the tier requires; if you cannot review the diff, do not set `review:`. A note in the plan is not that review.
- **Ticket id:** Copy the id the ticket already has onto `ticket:` in `task.md` (`BOOK-12`, `#45`, a Notion id). Require one. Do not invent one and do not check its shape. The gate reads `ticket:` only to find the task branch.
- **Commit and PR title:** `<type>(<scope>): <summary> (<ticket-id>)`. `<type>` is the task kind (`feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`). `<scope>` is optional. Example: `feat(booking): add room search API (BOOK-12)`. The kind before `(` or `:` is what the gate matches.
- **Task branch:** `type/<ticket-id>-<slug>` (example `feat/BOOK-12-room-search`). `<type>` is the task kind (`feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `perf`, `ci`, `build`, `style`, `revert`). `<slug>` is two to five words from the task name in ASCII `a-z0-9` only, joined by `-`. `<ticket-id>` is copied from `ticket:` (surrounding quotes and a trailing ` # comment` are stripped). Legacy `task-<id>` or `task-<id>-<slug>` still works; the gate prints `branch-deprecated:` on `allowed` when it finds one. Exactly one branch per task; two refuse with `task-branch-missing`. Renaming the task later does not rename the branch.
- **Draft PR handoff:** When a git remote exists, push the task branch and open a draft PR with `gh pr create --draft --base <queue> --head <branch> --title '<type>(<scope>): <summary> (<ticket-id>)' --body 'Task <id> from jt-queue.'`. Pass `--title` and `--body` every time; `gh` cannot prompt for them when an agent runs it. Keep the title in single quotes and drop any `'` from it. If the draft PR cannot be opened, run `gate.py ask`. The line must not be `review:`. The gate refuses.

## 5. Repos (opt-in, for frontend + backend)

A board without `## repos` works exactly as above. With it, one board in the home repo drives several sibling repos.

```text
## repos

### fe
path: .

### be
path: ../app-be
queue: main
(the same two-column table: `<TEST_CMD>`, `<SETUP_CMD>`, `<TYPECHECK_CMD>`, `<LINT_CMD>`, `<STACK_LOCK>`)
```

- One `### <name>` block per repo (`[a-z][a-z0-9-]*`, not a status word such as `merge`). Exactly one has `path: .` and nothing else: the home repo, whose commands stay in the main table. Every other `path:` is relative to home's main worktree and must be the top of its own git repo. `next` stops with `repo-invalid`, `not-ready` (`be.TEST_CMD`), or `repo-missing`.
- `approve-commands` covers each repo's `path:`, `queue:`, `TEST_CMD`, and `SETUP_CMD`, plus `LINT_CMD`, `TYPECHECK_CMD`, `AFFECTED_TEST_CMD`, `SECURITY_CMD`, and `VERIFY_CMD` when that cell is not empty, and a task's per-repo screen-check commands. Changing any of them refuses with `commands-changed`. An empty lint, typecheck, affected-test, security, or verify cell is left out of the hash, so an older approval still matches until one of those cells is set. `<DENYLIST>` is not a shell command and is not part of the hash.
- `task.md`: `repos: fe, be` names the repos; none, or only home, keeps the single-repo rules. `files:` entries are `<repo>:<path>` (no prefix means home). `land: be, fe` is the landing order (default: `## repos` order). The screen-check commands take one line per repo, as `task.template.md` shows.
- `reach-review` on such a task is always `Standard`: the task branch in every listed repo, each repo's `TEST_CMD` in its own worktree (a failure counts one round), `## review-diff` with one `<repo>: <sha>` line per repo, and `outside-files:` per repo. A task branch with code in an unlisted repo refuses with `repo-undeclared`. `--write` writes `review: fe:<url|local> be:<url|local>`.
- `landed.py` prints `landed-<repo>:` for each repo and `landed: all` only when every repo has landed; it adds `order-warning:` when a repo landed before one earlier in `land:`. `merge:` needs `landed: all`.

## 6. Size (`small`, `medium`, `large`)

`size:` on the task is `small`, `medium`, or `large`. The agent sets it when it creates the task or the spec. Unset means `medium`. A `size:` token on that board line overrides the task, including downward; the gate itself never lowers the floor. Each of these raises it one step, capped at `large`: a changed path that names auth (`auth`, `login`, `session`, `password`, `oauth`; not `author`), a migration or `.sql` file, or a diff over `<DIFF_LIMIT>` added and deleted lines (empty means 400). `allowed` prints `size:`. When the floor was raised it also prints `size-from:` and `escalate:` (`auth`, `migrations`, `diff`). `small` runs `<AFFECTED_TEST_CMD>` when that cell is set, or `<TEST_CMD>` when it contains `{files}` (filled with the affected test paths). Otherwise, and when no affected test can be named, it runs the full `<TEST_CMD>` and prints `affected: none -> full suite`. It does not append paths to a command that did not ask for them. An `<AFFECTED_TEST_CMD>` with no `{files}` runs as written and prints `affected: command`. `medium` and `large` run `<TEST_CMD>` unchanged. `large` also prints `size-hooks: worktree-rounds, fresh-context-review, high-risk`. `worktree-rounds` is only recorded. `fresh-context-review` is the `## ai-review` check. `small` needs no spec and uses `/jt-add-task`. `medium` is a short spec. `large` is a full spec.

On Standard, effective size `medium` or `large` needs `## ai-review` before `allowed` (`refused: ai-review`, `next: retry`, and it does not count a round). `small` and Quick print `ai-review: skip`. A line counts when it is `accepted:` or `rejected:` with a reason after ` — ` or ` - `, or exactly `fallback: no reviewer skill installed`. A line that still contains `<` or `|` does not count. `/jt-work` runs that review once, after secret, denylist, typecheck, lint, tests, and verify would pass, in a fresh context that sees only the spec AC/EC, `task.md`, and the diff, never the implementer's chat. One reviewer, and no second one: `/interrogate` when installed, otherwise Matt `/pr`, otherwise `/ponytail-review` when the effective size is `large` (`high-risk` in `size-hooks:`). Accepted findings are fixed and the gate runs again. The reviewer does not approve or merge. `/jt-review` stays human-only.

## 7. Spec pass lines

When `task.md` sets `spec:` to a `spec.md` inside the repo, every `pass:` line is `- <AC id or EC id>: <Then>` copied from that row. `reach-review` refuses `pass-ac` when an id is missing or the text is not that Then, and `spec-unapproved` when the spec has no human `✅` approval or an open question Blocks `dev` or `AC`. No `spec:` line means these checks do not run. One spec approval covers the tasks derived from it: `/jt-add-task` does not ask again, and `/jt-work` does not ask the human to approve each of those tasks or pass lines. Shell commands still need the one-time `approve-commands` on this machine. `/jt-review` stays human-only.
