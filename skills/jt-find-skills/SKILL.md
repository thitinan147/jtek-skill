---
name: jt-find-skills
description: Find REPO_SKILLS of the open repo and TEK_SKILLS at the moments the loop already uses those names. Propose the names for the person to choose. Use when the user runs /jt-find-skills. Do not install anything. Do not write the board until the person accepts.
license: MIT
metadata:
  author: Thitinan
  version: "20"
  short-description: Propose skill names, then write the accepted ones
---

# jt-find-skills

Find `<REPO_SKILLS>` for the open repo and `<TEK_SKILLS>` for the moments the loop already uses, from `references/skills.md` in skill `jt-card-gate`. Propose the names for the human to choose.

Do not install yet. Do not write `card-loop/board.md` until the human accepts the chosen names.

`/jt-new-board` fills names from **Search** when it creates the board. When this command runs on its own, propose the names first.

## Search

Read the stack from the open repo. That is `<STACK_LOCK>` on `card-loop/board.md` when it exists, plus `package.json`, `go.mod`, `pyproject.toml`, and `Cargo.toml`.

Installed skills are every `SKILL.md` under every folder in home whose name starts with `.`, including under `~/.config`. Do not walk home folders named `.npm`, `.cache`, `.local`, or `.Trash`. While walking, skip folders named `node_modules`, `.git`, `.tmp`, `backups`, `sessions`, `projects`, `tmp`, or `downloads`. Follow each symlink to the real file. The same real path counts as one skill, and the same `name` counts as one skill. Read `name` and `description` from every skill that remains.

A name that starts with `jt-` or `jtek-` does not enter either group.

Search for a skill this rule did not find with

`https://skills.sh/api/search?q=<words>&limit=5`

Read `skills[].skillId`, `skills[].source`, and `skills[].installs`. Sort `installs` from high to low. Skip a skill whose `installs` is 0. Skip a skill whose name matches one you already found.

The work group is `<TEK_SKILLS>` for the moments the loop already uses. Search the three words `grill`, `debug`, and `yagni`, then keep a skill whose on-machine `description` or web `skillId` matches a moment in `references/skills.md`. Do not add a moment.

The repo group is `<REPO_SKILLS>` for the open repo. Read `name` from `SKILL.md` in this repo first, then search by the language or framework found in this repo when the cell is not full. Do not open another repo.

Each group on the board gets at most three names. Names found from `SKILL.md` come first. Names from the web fill what remains. The table below shows every name that qualifies, including web skills, even when the board cell is full.

Show this table in the reply, one row per qualifying name.

| Group | Name | Status |
|---|---|---|
| group name | skill name | `on this machine` or `install this` |

`on this machine` means you found `SKILL.md` by the rule above. `install this` means the name came from the web and that file is not found yet.

An `install this` row gives the human this command to copy. Do not run an install command. The command does not pass `-a`, so it installs for every agent the CLI sees on this machine.

`npx skills add <source>@<skillId> -g -y`

## Propose

Propose both groups with the status table from **Search**. The human chooses. Do not run an install command. Do not open any skill. Do not write the board yet.

After the human accepts names, write only the accepted names into `<TEK_SKILLS>` and `<REPO_SKILLS>` on the queue branch. Do not write a name the human did not accept. Do not delete other lines. Then commit only `card-loop/board.md`. If the human has not accepted, stop without editing the board.

If `card-loop/board.md` is missing, stop and say to run `/jt-new-board` first.

Done when the human has accepted and both cells match the accepted names, or the human has not accepted and this command has not written the board.
