---
name: jt-build
description: Makes the smallest change that meets a ticket, with tests, reusing what the codebase already has. Use when jt-work reaches the Build step, or when the user asks to implement a change that has already been understood and scoped.
---

# jt-build

## 1. Before writing new code

Ask in this order, and stop at the first yes:

1. Does this code need to exist to meet `Done when`? If not, do not write it. (P1)
2. Does the repository already have something that does it? Use that.
3. Does the standard library or an installed package do it? Use that.
4. Otherwise write the shortest direct version.

This never applies to security, input validation at a trust boundary, or error handling. Keep those.

## 2. Build

1. Agree the public interface first: the function, endpoint, or command a caller sees. Tests go through it.
2. Write or change a test for each behaviour you add, before or with the code. When the playbook says the test comes first, it does. A test checks what a caller can observe, not how the inside works, and takes its expected values from the ticket, never from the code under test (P10). See each new test fail once before it passes, for the reason you expect, not an import or a setup error. When the code and its test are both new, commit them first. Then break the new code once, see the test fail, and restore it with `git checkout -- <file>`, which brings back what you committed. While that break is still uncommitted, run `jtek.py broke <id> --item <n>` once per `Done when` item, so the script records that a declared check failed. Then restore the file. `finish` refuses without one record for every item on the current commit. Run without a build cache, such as `python3 -B`, so a stale one cannot hide the break. Keep no copy of the file outside git; `git stash` is fine. Prefer no new test over a test that cannot fail. The exception is a test that pins behaviour which must not change, such as a line under `Out of scope`: it passes before and after, and you say in the evidence which tests are pins.
3. Make the smallest change that meets `Done when`. Behaviour listed under `Out of scope` stays exactly as it is now. When an entry names a topic, such as "non-ASCII letters", both readings hold: do not add support for it, and do not change what happens for it today.
4. Apply the principles in [../jt-work/references/principles.md](../jt-work/references/principles.md) where a condition holds, and cite the id of each one that decided something.
5. An existing test, or a script that a check runs, may have to change because `Done when` now asks for another result. Adding new lines to one is fine. Change only the existing lines that can no longer hold, keep every other assertion as strict as it was, and say in the evidence which lines and why. The result names these files for the human. Never change one to make a failure go away.
6. Commit in the worktree. Never commit on the base branch. Write the message the way the repository's log does. When the log shows no form, use `type: summary (<ticket id>)`.
7. A script or a file the ticket asks for is only that. It becomes a check when the ticket says so, and then the first limit below applies.

## Stop instead of building

A new dependency, a migration file, or a change to CI or `jtek.json` is part of the change: make it when the ticket needs it, and say it and why in the evidence. The `attention:` line shows it to the human, and the change then needs a verdict. Two limits:

- The checks install from `setup` in `jtek.json` on the base, and read their commands from there. A dependency that `setup` does not install, or a new check, does not take effect in this ticket: stop with `jtek.py stop <id> --waiting approval --note "<what to add on the base, and why>"`.
- Anything that acts outside the pull request, such as running a migration against a shared database or a deploy, waits for the human (P16).

Stop with `--waiting input` when the change grows past the ticket. A second ticket is cheaper than a wide diff.

## Done when

The change is committed, every new behaviour has a test, and nothing outside the ticket changed.
