# Queue reference

The contract is `skills/jt-work/references/contract.md`. These commands print `merge: no`.

| Command | What it prints |
|---|---|
| `gate.py next` | The next task, or `wait` when a cap, a quota, or `blocked-by:` says so |
| `gate.py loop --max 100` | A batch plan, a question list, and the ids to skip |
| `gate.py resume --id <id>` | The handoff Next line, as data |
| `gate.py merge-queue` | Human merge order |
| `gate.py flags` | Optional Unleash revert path |
| `gate.py title --text <title>` | `title: ok` or `refused: commit-title` |
| `gate.py codeowners` | A proposed lock for approved tests |
| `gate.py run-start` | A fresh quota run |

`<DIFF_LIMIT>` (empty means 400) refuses with `refused: diff-limit`, `step: diff-limit`, and `fix:`. `<IMPORT_CMD>` and `<PBT_CMD>` run only when the cell is set. A failure prints `fix:`.
