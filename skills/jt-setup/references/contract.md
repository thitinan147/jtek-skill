# Task Queue Contract, version 24.1

This contract belongs to `jt-setup`, `jt-add-task`, and `jt-work`. The gate is `scripts/gate.py` in each of those skills (one module). All queue files live under `jt-queue/` in the open repository.

## 1. Files & Branch Locations

- `jt-queue/board.md`: Queue state and project command table (`<TEST_CMD>`, `<SETUP_CMD>`, `<TYPECHECK_CMD>`, `<LINT_CMD>`, `<BROWSER_TOOL>`, `<STACK_LOCK>`).
- `jt-queue/brief.md`: Optional round brief accepted by the human.
- `jt-queue/tasks/<id>/task.md`: Task contract (`kind:`, `size:`, `layer:`, `screen:`, `do:`, `out:`, `pass:`, `files:`, `needs:`, `refs:`, `ask:`; the screen-check command fields are described in `task.template.md`).
- `jt-queue/tasks/<id>/plan.md`: Required for `Standard` tier, optional for `Quick` tier. Contains `## Goal`, `## Architecture`, `## Files`, `## Steps`, `## Out of scope`, `## Done when`, `## Escape`, `## evidence`, `## review-diff`, and `## decisions`.

`jt-queue/` is gitignored by default, so the gate reads these paths from the working tree and they are never part of a commit or a push. Only when a path is tracked is it read from a branch: the board, brief, and `task.md` from `<queue>`, and `plan.md` from `task-<id>`.

## 2. Board Line Format & Status Permissions

```text
- [ ] **<id>** <short name> (<kind>) [ask: | review: <link> | send-back: <note>]
- [x] **<id>** <short name> (<kind>) merge: | drop: <reason>
```

- `<id>` must match `^\d+(\.\d+)*$` with no path traversal.
- Allowed status tokens: `ask:`, `review:`, `send-back:`, `merge:`, `drop:`. Any other colon token in the status slot stops the queue with `unknown-status`.
- **Agent permissions:** May add human-approved new task lines, but must update status tokens on existing lines **only** via `gate.py ask` and `gate.py reach-review --write`. Never write `merge:` or `drop:`. Never run `gate.py approve-commands` and never change `<TEST_CMD>`, `<SETUP_CMD>`, `<LINT_CMD>`, `<TYPECHECK_CMD>`, or a task's screen-check commands to make a refusal pass; the human approves those commands (stored in `.git`, outside every branch).
- **Human permissions (`/jt-review`):** Writes `merge:`, `send-back:`, and `drop:`. Answers `ask:` by updating `jt-queue/tasks/<id>/task.md` until intent is closed and clearing the `ask:` heading; on the next run, `gate.py next` resumes the task (`question-cleared`) and `reach-review --write` replaces `ask:` with `review:`.
- `needs:` names work in another repository (for example a backend task for a frontend task) that must land first. It is text for the human: the gate never reads it and never refuses because of it.
- Same-topic tasks sharing `layer:` must link each other under `refs:`. Do not split into parallel agents without a link.

## 3. Adaptive Gate Tiers (`Quick` vs `Standard`)

The gate computes the task's tier from `(<kind>)` on `jt-queue/board.md`. A tracked board uses the kind at `git merge-base <queue> task-<id>`. A different kind on the current line raises the tier to `Standard`, and that tier does not return to `Quick`. A gitignored or untracked board uses the kind in the working tree, so editing `(<kind>)` there can raise or lower the tier.

- **Quick Tier** requires all 5 conditions:
  1. Task kind is `docs` or `style`: the merge-base kind when the board is tracked, otherwise the kind in the working tree.
  2. Every commit on `task-<id>` outside `jt-queue/` has commit kind matching the task kind.
  3. Task does not set `screen: yes`.
  4. If `docs`: every changed file outside `jt-queue/` is a documentation file (`.md`, `.rst`, `.adoc`, or extensionless/doc-extension `README`, `LICENSE`, `CHANGELOG`, `NOTICE`, `AUTHORS`, `CONTRIBUTING`).
  5. If `style`: code files may change; non-whitespace changes (`git diff -w --ignore-blank-lines`) are reported in `style-changes:`.
- **Standard Tier:** All other tasks (`feat`, `fix`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`) and any `docs`/`style` task that escalates.

| Check | Quick | Standard |
|---|---|---|
| Exactly one branch `task-<id>` or `task-<id>-<slug>` exists | ✓ | ✓ |
| Use existing check commands; no one-off checker script | ✓ | ✓ |
| `<TEST_CMD>` passes (or `no-suite`) | ✓ | ✓ |
| `<LINT_CMD>` and `<TYPECHECK_CMD>` pass when the cell is not empty (empty is `skip` and is not run) | — | ✓ |
| A diff outside `jt-queue/` exists, and `## review-diff` cites the latest code commit, `verdict: pass`, and a `checked:` line. No such diff is refused (`no diff outside jt-queue/ to review`), not `repo-review: skip` | — | ✓ |
| Every `pass:` line of the task appears in `## evidence` of `plan.md` | — | ✓ |
| JTek `gate.py screen-check` when `screen: yes` | — | ✓ |
| Added file whose name starts with `.env` (except `.env.example`), a private-key file (`*.pem`, `id_rsa`, `id_dsa`, `id_ecdsa`, `id_ed25519`, not `*.pub`), or an added `PRIVATE KEY` block: `secret-suspect`, `next: ask`. The output names the file (or `file:line`) and never the value | ✓ | ✓ |
| `test-weakening`: a deleted test file, or an added `.skip` / `.only` / `xit` / `@skip` / `xfail` marker, is reported on `allowed` and does not refuse. A rename or a skip the task asked for looks the same, so the human judges it, as with `outside-files:` | ✓ | ✓ |
| `allowed` prints `gates:` in this order: `tests`, `lint`, `typecheck`, `screen`, `review-diff`, `security`, `test-weakening` | ✓ | ✓ |
| Report `outside-files:` and `style-changes:` | ✓ (both) | ✓ (`outside-files:` only) |

## 4. Plan, Three Rounds, and Diff Review

- **Plan (`Standard` tier):** A `Done when` line is a command to run, or an artifact to open. If `Done when` has no command and no artifact, run `gate.py ask`. If `Escape` is empty, or an `Escape` line is true, run `gate.py ask` and do not set `review:`.
- **Three rounds:** One round is one full attempt. The evidence is that the relevant tests are green, and for screen work of every kind, not only `fix`, the same steps on the same screen do not show the bug. Screen work that cannot be clicked does not count as this round. The gate counts a round each time `<TEST_CMD>`, `<LINT_CMD>`, `<TYPECHECK_CMD>`, or setup fails in `reach-review` (retrying an unchanged commit counts too), and prints `round <n> of 3`. On the third it answers `next: ask`: run `gate.py ask` with what each round tried. `gate.py ask` starts the count again. `secret-suspect` is `next: ask` immediately and does not count a round.
- **Diff review:** On `Standard` tier, review this task's diff yourself before `review:` and record it in `## review-diff`. A Standard task with no diff outside `jt-queue/` is refused. `docs` on the Quick tier does not need that review. Do not skip a review that the tier requires; if you cannot review the diff, do not set `review:`. A note in the plan is not that review.
- **Ticket id:** Copy the id the ticket already has onto `ticket:` in `task.md` (`BOOK-12`, `#45`, a Notion id). Require one. Do not invent one and do not check its shape. The gate does not read `ticket:`.
- **Commit and PR title:** `<type>(<scope>): <summary> (<ticket-id>)`. `<type>` is the task kind (`feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`). `<scope>` is optional. Example: `feat(booking): add room search API (BOOK-12)`. The kind before `(` or `:` is what the gate matches.
- **Task branch:** `task-<id>-<slug>`, with `<slug>` made of words from the task name in ASCII `a-z0-9` only, joined by `-` (`task-12-login-rate-limit`). A plain `task-<id>` still works. The gate finds the branch by its `task-<id>` prefix, so in this contract `task-<id>` means that branch; two branches for one task refuse with `task-branch-missing`. Renaming the task later does not rename the branch. The conventional name `type/<ticket-id>-short-slug` (example `feat/BOOK-12-room-search`) is not looked up yet. Do not create it for a queue task.
- **Draft PR handoff:** When a git remote exists, push the task branch and open a draft PR with `gh pr create --draft --base <queue> --head task-<id>-<slug> --title '<type>(<scope>): <summary> (<ticket-id>)' --body 'Task <id> from jt-queue.'`. Pass `--title` and `--body` every time; `gh` cannot prompt for them when an agent runs it. Keep the title in single quotes and drop any `'` from it. If the draft PR cannot be opened, run `gate.py ask`. The line must not be `review:`. The gate refuses.

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
- `approve-commands` covers each repo's `path:`, `queue:`, `TEST_CMD`, and `SETUP_CMD`, plus `LINT_CMD` and `TYPECHECK_CMD` when that cell is not empty, and a task's per-repo screen-check commands. Changing any of them refuses with `commands-changed`. An empty lint or typecheck cell is left out of the hash, so a v22 approval still matches until one of those cells is set.
- `task.md`: `repos: fe, be` names the repos; none, or only home, keeps the single-repo rules. `files:` entries are `<repo>:<path>` (no prefix means home). `land: be, fe` is the landing order (default: `## repos` order). The screen-check commands take one line per repo, as `task.template.md` shows.
- `reach-review` on such a task is always `Standard`: `task-<id>` in every listed repo, each repo's `TEST_CMD` in its own worktree (a failure counts one round), `## review-diff` with one `<repo>: <sha>` line per repo, and `outside-files:` per repo. A `task-<id>` with code in an unlisted repo refuses with `repo-undeclared`. `--write` writes `review: fe:<url|local> be:<url|local>`.
- `landed.py` prints `landed-<repo>:` for each repo and `landed: all` only when every repo has landed; it adds `order-warning:` when a repo landed before one earlier in `land:`. `merge:` needs `landed: all`.

## 6. Size (`small`, `medium`, `large`)

`size:` on the task is `small`, `medium`, or `large`. The agent sets it when it creates the task or the spec. Unset means `medium`. A `size:` token on that board line overrides the task, including downward; the gate itself never lowers the floor. Each of these raises it one step, capped at `large`: a changed path that names auth (`auth`, `login`, `session`, `password`, `oauth`; not `author`), a migration or `.sql` file, or a diff over `<DIFF_LIMIT>` added and deleted lines (empty means 400). `allowed` prints `size:`. When the floor was raised it also prints `size-from:` and `escalate:` (`auth`, `migrations`, `diff`). `small` appends the affected test paths to `<TEST_CMD>` and prints `affected:` (`none` runs no tests). `medium` and `large` run `<TEST_CMD>` unchanged. `large` also prints `size-hooks: worktree-rounds, fresh-context-review, high-risk`. Those three are only recorded here. `small` needs no spec and uses `/jt-add-task`. `medium` is a short spec. `large` is a full spec.
