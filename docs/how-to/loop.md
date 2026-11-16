# Loop a batch

`/jt-work --loop` runs `gate.py loop`. It plans at most 100 tickets. It does not merge and it does not ask a new approval question.

- Each ticket starts from the latest queue commit.
- A task named in `blocked-by:` that is not `merge:` or `drop:` is skipped.
- An unclear task (an open question, or no task file) is listed for `/jt-board`. It is not started.
- Open reviews stop the batch at `<MAX_REVIEW>` when that cell is set, otherwise at 10, and never above 10.
- `<MAX_PARALLEL>` limits how many ready ids the plan includes.
- `<QUOTA>` limits how many tasks one run may offer. `gate.py run-start` begins a new run.
- mise and reviewdog are the tools to use when they are installed. Testcontainers, Pact, and act stay optional.

`gate.py resume --id <id>` prints the Next line from `handoff.md` as data. It does not run that line.

`gate.py merge-queue` prints the human merge order. It does not merge.
