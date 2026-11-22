---
name: jt-build
description: Makes the smallest change that meets a ticket, with tests, reusing what the codebase already has. Use when jt-work reaches the Build step, or when the user asks to implement a change that has already been understood and scoped.
---

# jt-build

## 1. Before writing new code

Ask in this order, and stop at the first yes:

1. Does this code need to exist to meet `Done when`? If not, do not write it.
2. Does the repository already have something that does it? Use that.
3. Does the standard library or an installed package do it? Use that.
4. Otherwise write the shortest direct version.

This never applies to security, input validation at a trust boundary, or error handling. Keep those.

## 2. Build

1. Agree the public interface first: the function, endpoint, or command a caller sees. Tests go through it.
2. Write or change a test for each behaviour you add, before or with the code. When the playbook says the test comes first, it does. A test checks what a caller can observe, not how the inside works. See each new test fail once before it passes. When the code and its test are both new, commit them first. Then break the new code once, see the test fail, and restore it with `git checkout -- <file>`, which brings back what you committed. Keep no copy of the file anywhere. Prefer no new test over a test that cannot fail. The exception is a test that pins behaviour which must not change, such as a line under `Out of scope`: it passes before and after, and you say in the evidence which tests are pins.
3. Make the smallest change that meets `Done when`. Behaviour listed under `Out of scope` stays exactly as it is now. When an entry names a topic, such as "non-ASCII letters", both readings hold: do not add support for it, and do not change what happens for it today.
4. Apply [references/principles.md](references/principles.md) where a condition holds.
5. An existing test, or a script that a check runs, may have to change because `Done when` now asks for another result. Change only the lines that can no longer hold, keep every other assertion as strict as it was, and say in the evidence which lines and why. The result names these files for the human. Never change one to make a failure go away.
6. Commit in the worktree. Never commit on the base branch. Write the message the way the repository's log does. When the log shows no form, use `type: summary (<ticket id>)`.
7. A script or a file the ticket asks for is only that. It becomes a check when the ticket says so, and then the stop below applies.

## Stop instead of building

Stop with `jtek.py stop <id> --waiting approval --note "<what and why>"` before you add a dependency, write a migration, delete data, or change CI or `jtek.json`.

Stop with `--waiting input` when the change grows past the ticket. A second ticket is cheaper than a wide diff.

## Done when

The change is committed, every new behaviour has a test, and nothing outside the ticket changed.
