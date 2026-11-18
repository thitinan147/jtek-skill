# Principles

Each one has a condition. Apply it only when the condition holds.

- **When you are about to add a rule in prose:** first ask if a type, a lint rule, or a test can enforce it. Prose is the weakest guard.
- **When the nearest example in the code is a workaround:** fix the cause or stop and ask. Agents copy what they read, so one more copy makes the next one more likely.
- **When a function can be called wrongly:** change its shape so the wrong call does not compile or fails at once. Do not add a comment that warns about it.
- **When you add state:** list the states and the moves between them before writing code. Make a state that should not exist impossible to represent.
- **When two events can arrive in either order:** test both orders. A happy-path test does not find this.
- **When you touch a trust boundary** (user input, a network response, a file): validate there, and keep error handling. Never remove either to make a change smaller.
- **When a check fails:** find the cause before changing code. Do not retry until it passes.
- **When a test is hard to write:** treat that as a design problem in the code, and say so.
- **When an operation can be retried or sent twice:** make it safe to repeat.
- **When you report a number** (time, size, count): say how it was measured before you trust it.
- **When the same manual edit repeats across many files:** write the script or codemod, and run that.
- **When you are unsure something works:** run it and look. Do not reason your way to "it should work".
- **When the change grows past the ticket:** stop and return a question. A second ticket is cheaper than a wide diff.
- **When you would add a dependency, a migration, a deletion of data, or a change to CI:** stop with `--waiting approval`.
- **When you finish:** read your own diff once as a stranger would. Delete what does not serve `Done when`.
