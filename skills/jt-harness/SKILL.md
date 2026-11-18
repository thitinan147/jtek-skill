---
name: jt-harness
description: Builds a repository's way to run and observe the real app (a verify guide, a feature map, and a `verify` check) so that agents can prove a change works. Use when a repository has no `.jtek/verify.md`, when the user asks to set up or repair verification for a project, or when a change could not be verified because the real thing could not be run.
---

# jt-harness

Do this once per repository, before agents work tickets in it. Everything else rests on it: without a way to run the real thing, a passing check only means the code compiles.

This skill writes files under `.jtek/` and one script. It never edits product code.

## 1. Interview the repository, not the human

Read the code, scripts, and CI config to answer five questions. Ask the human only what the repository cannot tell you, such as a test account.

- **Surface:** what does a user touch? Screens, endpoints, commands.
- **Run:** how does the app start, and what is the ready signal? Ready means usable, not that a process answers.
- **Drive:** how can an agent act as a user? Use what exists first: end-to-end specs, scripts, endpoints you can call. Only then add browser automation or a terminal session.
- **Observe:** where does the result show? Output, a response, a stored value, a log line.
- **Isolate:** what must differ between two worktrees running at once? Ports, data folders, databases, accounts.

## 2. Write `.jtek/verify.md`

Short, with these sections, and exact commands in each:

- **Launch:** start the app and wait for the ready signal.
- **Doctor:** what to check when it does not start, most likely cause first.
- **Drive:** how to do a user action. For a screen, find elements by role and name, not by layout.
- **Evidence:** what to capture. A screen: the page state and a screenshot. A command: the command, its output, and the exit code. A write: a second, read-only look at the stored value.
- **Cleanup:** stop what was started and remove what was created.

## 3. Write the feature map

One file per main feature in `.jtek/features/<name>.md`. Start with three to five. Each has:

- **How a user gets to it**
- **How to drive it:** the exact commands or steps
- **What to observe** when it works
- **Gotchas**

## 4. Add the check

Write one script that launches the app, drives the main path of each mapped feature, and exits non-zero on a wrong result. Propose it as `verify` in `jtek.json`.

## 5. Prove it

1. Run the whole thing once and see it pass on the working app.
2. Break one feature on purpose, run it again, and see it fail. Then undo the break. A check you have never seen fail proves nothing.
3. Run it from a second worktree at the same time, when you can, to confirm the isolation.

A harness that was never run is a draft. Do not hand it over as done.

## 6. Hand over

List what you wrote and what you could not cover. The human reviews `.jtek/` and `jtek.json` and commits them on the base branch.

If the app cannot be run at all, stop and report exactly what is missing. Do not write a harness around a different path and call the feature covered.
