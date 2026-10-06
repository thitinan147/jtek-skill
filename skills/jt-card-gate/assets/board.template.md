# Board - `<REPO_NAME>`

The rules live in skill `jt-card-gate` version 20. The brief is `brief.md`. A card is `backlog/<id>.md`. A plan is `plan/<id>.md`.

queue:

pair:

The name on the `pair:` line is the one answer from `/jt-new-board`, or the word `none`. Do not invent a name.

`/jt-new-board` fills this table from the open repo. The human does not fill it.

`<STACK_LOCK>` must include at least a language, a framework, the test command or the check kind, and what this repo must not use.

| Value | In this repo |
|---|---|
| `<TEST_CMD>` | |
| `<SETUP_CMD>` | |
| `<TYPECHECK_CMD>` | |
| `<LINT_CMD>` | |
| `<BROWSER_TOOL>` | |
| `<STACK_LOCK>` | |
| `<TEK_SKILLS>` | |
| `<REPO_SKILLS>` | |

`<SETUP_CMD>` is the command that prepares dependencies. The gate runs it in the card worktree before tests and before start. An empty cell means do not run it.

`<TEK_SKILLS>` names skills that make the work sharper. `/jt-do-work` opens a name from this row when the card still has two paths, when it is finding the bug cause before a test, and when it is editing production code. An empty cell opens nothing.

`<REPO_SKILLS>` names this repo's skills. `/jt-do-work` opens them when it reviews code after a commit whose kind is `feat`, `fix`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, or `revert`. Kind `docs` does not open. An empty cell opens nothing. Do not swap the two rows. `/jt-new-board` writes the names from **Search**.

**Pick now.** Read the words on the line. Do not look at the host review button.

`- [ ]` is open. `- [x]` is closed here (`merge:` or `drop:`). A parent whose children are all done is `- [x]` followed by `complete:`.

Ticket kinds are `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, and `revert`.

Item numbers. **1, 2, 3** are parents. **1.1, 1.2** are children. Check a parent only when every child is done.

Pick **first**, then **main**, then **later**. A line that has children under it is not picked, and it has no card of its own.

| Rank | Block | Why it comes first |
|---|---|---|
| **P0** | first | It leaks to a user, or it blocks the main work |
| **P1** | main | |
| **P4** | later | Pick it when no higher item is still `- [ ]` |

## closed

`/jt-move-card` may move a line here when the queue is long. That move does not change the status on the line. The agreement stays in the card file.

- (moved from below)

## first

no items

## main

no items

## later

Pick these when **first** and **main** have no `- [ ]` left.

no items

## waiting

The human has not accepted a card yet. Do not let an agent write a card and pick it.

## skip

Do not check this section off as work.
