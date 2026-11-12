# Getting started

This guide explains the words jtek-skill uses, then walks through one real round on a tiny Python repo: two tasks, one refusal from the gate and its fix, and the human review at the end. Every gate output below was captured from a real run. Only local file paths were shortened.

You type the slash commands. The agent runs `gate.py` for you; the commands are shown so you can see what it checks. In the examples, `gate.py` stands for `python3 <skill folder>/scripts/gate.py`.

## Before you start

- A Git repository, `git`, and Python 3.10 or later.
- macOS or Linux (on Windows, use WSL).
- jtek-skill installed (see [Install](../README.md#install)).

## Words you will see

| Word | Meaning |
|---|---|
| **board** | `jt-queue/board.md`: the project's test command and the list of tasks. It is the only place a task's status lives. |
| **brief** | `jt-queue/brief.md`: the goal and limits of this round, agreed before tasks are written. |
| **task** | `jt-queue/tasks/<id>/task.md`: what to do (`do:`), what not to touch (`out:`), how to tell it is done (`pass:`), and which files it may change (`files:`). |
| **kind** | The type of task in brackets on the board line: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`. |
| **queue branch** | The branch named on the `queue:` line of the board, usually `main`. Work lands here. |
| **`task-<id>-<slug>`** | The branch the agent commits a task's code on, such as `task-1-readme-usage`. One per task. |
| **gate** | `gate.py`, a Python script that decides whether a task may go to review. The agent cannot mark `review:` without it. |
| **Quick / Standard** | The gate's tier, worked out from the kind. **Quick** (`docs`, plain `style`) needs passing tests. **Standard** (everything else) also needs `plan.md` with evidence for every `pass:` line and a review of the diff. |
| **plan.md** | `jt-queue/tasks/<id>/plan.md`: the agent's notes for a Standard task, including the `## evidence` table and `## review-diff`. |
| **approve-commands** | The step where **you** confirm the exact test command (and any app start/click commands). The gate will not run a command you have not approved. |
| **round** | One attempt at passing the gate. After three failed test rounds the gate tells the agent to ask you instead of guessing. |

A task's status is written at the end of its board line:

| Status | Who writes it | Meaning |
|---|---|---|
| *(none)* | | Ready to work |
| `ask:` | agent, through the gate | The agent needs a decision from you |
| `review:` | agent, through the gate | Passed the gate; waiting for you |
| `send-back:` | you | Needs another round; your note says why |
| `merge:` | you | Landed on the queue branch; closed |
| `drop:` | you | Cancelled; closed |

## Walkthrough: a round on `tempconv`

The repo has one module with a bug: `c_to_f(0)` returns 23 instead of 32.

```python
def c_to_f(celsius: float) -> float:
    return celsius * 9 / 5 + 23
```

### 1. Set up the board

```text
/jt-work-queue
```

The agent asks the gate what to do next:

```text
$ gate.py next --root .
action: setup-board
command: /jt-work-queue
id:
reason: no-board
merge: no
```

It looks for a test command. `detect` only knows common setups, so here it finds nothing:

```text
$ gate.py detect --root .
TEST_CMD = no-suite  [source: no test runner found]
SETUP_CMD = (empty)  [source: none found]
merge: no
```

The agent reads the repo, sees `test_tempconv.py`, and proposes `python3 -m unittest`, showing where each value came from. **Nothing is written until you confirm.** Then it writes the board and adds `jt-queue/` to `.gitignore`:

```markdown
queue: main

| Value | In this repo |
|---|---|
| `<TEST_CMD>` | python3 -m unittest |
| `<STACK_LOCK>` | Python 3.10+, standard library only, tests with `unittest`; no third-party packages |
```

### 2. Agree the brief, then the tasks

The gate now answers `action: brief`. The agent reads the code, asks you only what the code cannot answer, and writes `jt-queue/brief.md` after you agree. Next it answers `action: add-task`, and the agent drafts one `task.md` per task for your approval. This is part of task 2 (empty fields left out):

```markdown
# 2 - c_to_f adds 23 instead of 32

kind: fix

do:
- Make `c_to_f` use the correct offset (32) and add tests for it

out:
- Changing `f_to_c`

pass:
- `python3 -m unittest` passes and includes a test that `c_to_f(0) == 32`
- `python3 -c "import tempconv; print(tempconv.c_to_f(100))"` prints 212.0

files:
- tempconv.py
- test_tempconv.py
```

Each `pass:` line is something you can run. The board now lists both tasks:

```markdown
## main

- [ ] **1** add usage to README (docs)
- [ ] **2** c_to_f adds 23 instead of 32 (fix)
```

### 3. A Quick task, and approving the test command

Run `/jt-work-queue` again. The gate picks task 1, a `docs` task. The agent commits the README change on `task-1-readme-usage`, then asks the gate:

```text
$ gate.py reach-review --root . --id 1
refused: commands-unapproved
merge: no
next: stop
detail: TEST_CMD/SETUP_CMD in jt-queue/board.md have not been approved on this machine. A human must review them, then run: gate.py approve-commands --root . --id 1
hint: Stop. A human must review the commands and run approve-commands. Never run it yourself.
```

The agent stops here. **This step is yours:** read the commands, then run:

```text
$ python3 <skill folder>/scripts/gate.py approve-commands --root . --id 1
approved board commands:
  TEST_CMD = python3 -m unittest
  SETUP_CMD = (empty)
approved card 1 commands:
  start = (empty)
  port = (empty)
  wait = (empty)
  click = (empty)
merge: no
```

The approval is stored in `.git/`, outside every branch, so a pull request cannot bring its own approval. You approve the board's commands once on each machine; a task that sets its own `start`/`click` commands (for screen checks) needs its own approval too. If anyone changes an approved command, the gate refuses again until you approve the new one. Now the gate runs the tests on `task-1-readme-usage` and lets it through:

```text
$ gate.py reach-review --root . --id 1
allowed
merge: no
tier: quick
repo-review: skip
```

With no Git remote, the agent records it with `--write --link local`. With a remote, it pushes `task-1-readme-usage` and opens a draft PR first. The board line becomes:

```markdown
- [ ] **1** add usage to README (docs) review: local
```

### 4. A Standard task, and a refusal

Task 2 is a `fix`, so it is Standard. The agent reproduces the bug (`c_to_f(100)` prints `203.0`), adds tests, fixes the offset, commits on `task-2-fix-c-to-f`, and writes `plan.md`. The test command is already approved, so there is no stop this time.

The agent's plan forgot the second `pass:` line. The gate catches it:

```text
$ gate.py reach-review --root . --id 2
refused: review-diff
merge: no
next: retry
detail: evidence-missing: every pass: line in task.md must be quoted in the first cell of a filled row (pass line | command | result) in '## evidence' of plan.md: `python3 -c "import tempconv; print(tempconv.c_to_f(100))"` prints 212.0
hint: Fix what detail: names in plan.md ('## review-diff' citing the latest code commit, or a missing '## evidence' row), then run gate.py diff-check.
```

`detail:` names the exact `pass:` line with no evidence. The agent runs that command, adds the row, and tries again. This is the evidence and review the gate accepted:

```markdown
## evidence

| pass line | command or artifact | result |
|---|---|---|
| `python3 -m unittest` passes and includes a test that `c_to_f(0) == 32` | `python3 -m unittest` | Ran 3 tests, OK; `CToFTests.test_freezing_point` checks `c_to_f(0) == 32` |
| `python3 -c "import tempconv; print(tempconv.c_to_f(100))"` prints 212.0 | same command | printed `212.0` |

## review-diff

sha: 6926cfb086ddf08f77fb5e945cddc9ac4c94f855
verdict: pass
checked: scope - tempconv.py and test_tempconv.py only, both under files:
checked: out - f_to_c unchanged
checked: callers and blast radius - c_to_f has no callers inside the repo besides the tests
checked: removed guards - the only removed line is the wrong offset
checked: slop - no debug output or dead code
```

```text
$ gate.py diff-check --root . --id 2
diff-check: ok

$ gate.py reach-review --root . --id 2
allowed
merge: no
tier: standard
repo-review: open
```

The `sha:` must be the latest commit on `task-2-fix-c-to-f`. If the agent commits again, its old review no longer counts.

### 5. When the tests fail

The gate runs your test command itself, on the task branch, so "the tests pass" is never just the agent's word. This is a later task whose change broke an existing test:

```text
$ gate.py reach-review --root . --id 3
refused: test-failed
merge: no
next: retry
detail: ..F
======================================================================
FAIL: test_boiling_point (test_tempconv.FToCTests.test_boiling_point)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/tmp/jt-work-queue-7gzuwf51/card/test_tempconv.py", line 8, in test_boiling_point
    self.assertEqual(f_to_c(212), 100)
    ~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^
AssertionError: 105.0 != 100
----------------------------------------------------------------------
Ran 3 tests in 0.000s
FAILED (failures=1)
round 1 of 3
log: ~/code/tempconv/.git/jt-queue/logs/3-test.log
hint: Read log:, fix the cause on task-<id>, commit, then run reach-review again.
```

On the third failed round the gate answers `next: ask`, and the agent writes you a question with what it tried instead of trying again.

### 6. Your review

When the gate has nothing left for the agent, it waits for you:

```text
$ gate.py next --root .
action: wait
command:
id:
ids: 1, 2
reason: review
merge: no
line: - [ ] **1** add usage to README (docs) review: local
```

```text
/jt-review-work
```

This command is for humans only; the agent is not allowed to start it. It shows each `review:` task with its `pass:` lines, the plan's evidence and review, the diff, and any file changed outside `files:`. You decide:

- **Accept:** merge the branch yourself (on GitHub, or `git merge`). jtek-skill never merges. The command checks that it landed, then writes `merge:`.
- **Send back:** give a reason that points to a `pass:` line or a `file:line`. The agent fixes it in the next round.
- **Drop:** close the task with a reason.

Here both tasks were merged by hand, so `landed.py` confirms them:

```text
$ landed.py --root . --id 2
landed: ancestor
merge: no
```

```markdown
- [x] **1** add usage to README (docs) merge:
- [x] **2** c_to_f adds 23 instead of 32 (fix) merge:
```

```text
$ gate.py next --root .
action: stop
command:
id:
reason: queue-clear
merge: no
```

The round is done. Start the next one with `/jt-work-queue`.

## Where to go next

- [Usage guide](usage.md): priorities (`first`, `main`, `later`), splitting work into tasks, screen checks, and work across two repos.
- [File and gate contract](../skills/jt-work-queue/references/contract.md): every field and rule the gate reads.
- [SECURITY.md](../SECURITY.md): what runs on your machine and what leaves it.
