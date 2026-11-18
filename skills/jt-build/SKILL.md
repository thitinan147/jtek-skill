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
2. Write or change a test for each behaviour you add, before or with the code. A test checks what a caller can observe, not how the inside works. See each new test fail once before it passes. Prefer no new test over a test that cannot fail.
3. Make the smallest change that meets `Done when`. Behaviour listed under `Out of scope` stays exactly as it is now.
4. Apply [references/principles.md](references/principles.md) where a condition holds.
5. Commit in the worktree. Never commit on the base branch.

## Stop instead of building

Stop with `jtek.py stop <id> --waiting approval --note "<what and why>"` before you add a dependency, write a migration, delete data, or change CI or `jtek.json`.

Stop with `--waiting input` when the change grows past the ticket. A second ticket is cheaper than a wide diff.

## Done when

The change is committed, every new behaviour has a test, and nothing outside the ticket changed.
