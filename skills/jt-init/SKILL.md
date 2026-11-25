---
name: jt-init
description: Sets up this repository on the machine in one confirmation. Guesses the checks, asks the board once, records the machine config, then the harness, then doctor. Use when the user types /jt-init, and only then.
disable-model-invocation: true
---

# jt-init

One confirmation. Nothing is written into the repository. Config goes under `$HOME/.jtek/repos/<repo id>/`.

## 1. Old files, or a new file

Run `jtek.py doctor` from the `jt-work` scripts and read its `init:` line.

- **`init: migrate`:** the repository still has `jtek.json` or `.jtek/`. Run `jtek.py migrate`. Do not run `init`. Tell the human to commit the removal. Leave the moved file as it is. Then go to step 4.
- **`init: ok`:** a machine config already exists. Show its path. Run doctor and stop, unless the human asked to change it.
- **`init: needed`:** run `jtek.py init`, then step 2.

## 2. Guess

Run `jtek.py guess`. It only reads. It does not open a dotenv file and it does not print a secret. Do not open one yourself.

## 3. Ask once

Show the guessed commands and this one question, then wait:

`board? none (tickets as files) / Notion database link / FLO product link`

The human may edit any guessed command in that same answer. `none` records `"board": ""`, so tickets are files. A Notion database link or a FLO product link is recorded as `board`. Do not ask a second time.

Record the accepted `setup`, `checks`, and `board` in `$HOME/.jtek/repos/<repo id>/jtek.json` (the file `init` named). Delete a check the human removed. Do not put that file in the repository.

## 4. Harness, then doctor

Follow the `jt-harness` skill for this repository. Then run `jtek.py doctor`.

- It prints `ready`: show that line and stop.
- It names something still missing: fix that once, run doctor again, and if it is still not ready, report the `missing` lines and stop.

## From /jt or /jt-work

Those skills run this flow when doctor prints `init: needed` or `init: migrate`. Say that in one line, ask once, then continue the original request.
