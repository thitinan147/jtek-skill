---
name: jt-harness
description: Builds a repository's way to run and observe the real app (a verify guide, a feature map, and a `verify` check) so that agents can prove a change works. Use when the user asks to set up or repair verification for a repository, or when a human asks for it after a change could not be verified. A ticket session does not load it; it goes on without one.
---

# jt-harness

Do this once per repository, before agents work tickets in it. Everything else rests on it: without a way to run the real thing, a passing check only means the code compiles.

This skill writes files under `~/.jtek/repos/<repo id>/` and one script in the repository. It never edits product code. The id is what `jtek.py init` prints.

## 1. Interview the repository, not the human

Read the code, scripts, and CI config to answer six questions. Ask the human only what the repository cannot tell you, such as a test account.

- **Surface:** what does a user touch? Screens, endpoints, commands.
- **Run:** how does the app start, and what is the ready signal? Ready means usable, not that a process answers.
- **Drive:** how can an agent act as a user? Use what exists first: end-to-end specs, scripts, endpoints you can call. Only then add browser automation or a terminal session.
- **Observe:** where does the result show? Output, a response, a stored value, a log line.
- **Isolate:** what must differ between two worktrees running at once? Ports, data folders, databases, accounts.
- **Depend:** what does the app need that lives elsewhere, such as a service in another repository? Where does it come from, which version, and how is it started at another version?

## 2. Write `~/.jtek/repos/<repo id>/verify.md`

A starting point for this file and for a feature file is in [references/verify-template.md](references/verify-template.md).

Short, with these sections, and exact commands in each:

- **Launch:** start the app and wait for the ready signal.
- **Doctor:** what to check when it does not start, most likely cause first.
- **Drive:** how to do a user action. For a screen, find elements by role and name, not by layout.
- **Evidence:** what to capture. A screen: the page state and a screenshot. A command: the command, its output, and the exit code. A write: a second, read-only look at the stored value.
- **Cleanup:** stop what was started and remove what was created, each by the exact id or path the launch printed. A cleanup that matches a pattern can delete another session's work.

## 3. Write the feature map

One file per main feature in `~/.jtek/repos/<repo id>/features/<name>.md`. Start with three to five. Each has:

- **How a user gets to it**
- **How to drive it:** the exact commands or steps
- **What to observe** when it works
- **Gotchas**

## 4. Add the check

Write one script that launches the app, drives the main path of each mapped feature, and exits non-zero on a wrong result. Propose it as `verify` in `~/.jtek/repos/<repo id>/jtek.json`.

## 5. Prove it

1. Run the whole thing once and see it pass on the working app.
2. Break one feature on purpose, run it again, and see it fail. Then undo the break. A check you have never seen fail proves nothing. Make the break in a copy of the working tree, with the script in it, that you remove afterwards, and never commit it. The guide stays in `~/.jtek`. This is the one time this skill touches product code.
3. Run it from a second copy at the same time, when you can, to confirm the isolation.

A harness that was never run is a draft. Do not hand it over as done.

While you test it: remove only what you made, by the exact path you created, and stop only a process you started, by its id. Never delete by a pattern, and never in a folder other sessions share: several sessions work on one machine at the same time.

## 6. Hand over

List what you wrote and what you could not cover. The human reviews the files under `~/.jtek/repos/<repo id>/`. Nothing there is committed.

## Keeping it true

Run this skill again when the harness stops matching the app: a renamed screen, a new start command, a feature with no file. The fault may also be one the check cannot see: the guide lacks something sessions needed. Then read the guide as a newcomer would, find where it leaves them guessing, and run every line you add, as written. Run the `verify` check, fix the guide and the script only, and do step 5 again when the script changed. End with one word and the reason: `clean` (nothing to change), `changed` (list the files), or `blocked` (the app itself is broken; say where).

If the app cannot be run at all, stop and report exactly what is missing. Do not write a harness around a different path and call the feature covered.
