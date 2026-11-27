---
name: jt-status
description: Shows machine and repository readiness from doctor followed by a Thai table of tickets in progress, waiting for review, waiting for merge, choices to confirm, and the one next action. Read-only. Use when the user types /jt-status, and only then.
disable-model-invocation: true
---

# jt-status

Read-only. Show whether the machine and repository are ready and where the work stands, then stop. Do not claim a ticket, do not edit a file, and do not change the board.

## 1. Ask the script

`jtek.py status` is at `scripts/jtek.py` in the `jt-work` skill. Its first line reports machine and repository readiness from doctor:

- `พร้อมใช้`, both the machine and this repository are ready (optional items do not block readiness)
- `ยังไม่พร้อม`, what required machine or repository item is missing and the command that fixes it

After that first line, it prints five groups, in Thai:

- `กำลังทำ`, tickets a session holds, with the stored session hash (never a raw session id)
- `รอรีวิว`, tickets waiting for a verdict
- `รอ merge`, tickets waiting for the human to merge
- `choice รอยืนยัน`, `choice:` lines from ticket evidence for the human to confirm
- `ถัดไป`, the one next action

A `-` in a group means none.

With a board, read the open tickets the way [starting-sessions.md](../jt-work/references/starting-sessions.md) says and pass them as `--board-file`. With no board, run `jtek.py status` with no file. It reads the ticket files on this machine, and a claim that has no ticket file, such as a local ticket.

## 2. Show readiness and the table

Show the readiness line first, then the script's lines as a short table, still in Thai. Do not drop the readiness line, do not translate the labels away, and do not add a ticket the script did not name. The `ถัดไป` row is the only next action. Then stop.

If the script prints `refused:`, show that and stop.

## What this skill does not do

It does not run `init`, `migrate`, `start`, `release`, `sync`, or `finish`. It does not open a pull request and it does not merge.
