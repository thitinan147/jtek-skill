---
name: jt-status
description: Shows a Thai table of tickets in progress, waiting for review, waiting for merge, and the one next action. Read-only. Use when the user types /jt-status, and only then.
disable-model-invocation: true
---

# jt-status

Read-only. Show where the work stands, then stop. Do not claim a ticket, do not edit a file, and do not change the board.

## 1. Ask the script

`jtek.py status` is at `scripts/jtek.py` in the `jt-work` skill. It prints four groups, in Thai:

- `กำลังทำ`, tickets a session holds, with the stored session hash (never a raw session id)
- `รอรีวิว`, tickets waiting for a verdict
- `รอ merge`, tickets waiting for the human to merge
- `ถัดไป`, the one next action

A `-` in a group means none.

With a board, read the open tickets the way [starting-sessions.md](../jt-work/references/starting-sessions.md) says and pass them as `--board-file`. With no board, run `jtek.py status` with no file: the ticket files are on this machine.

## 2. Show the table

Show the script's lines as a short table, still in Thai. Do not translate them away, and do not add a ticket the script did not name. The `ถัดไป` row is the only next action.

If the script prints `refused:`, show that and stop.

## What this skill does not do

It does not run `init`, `migrate`, `start`, `release`, `sync`, or `finish`. It does not open a pull request and it does not merge.
