# Principles

Each principle has an id, the moment it applies, the rule, and a test you can run in your head or for real. The step skills mark the lines that carry one with its id, such as `(P8)`. Cite the id behind a decision in the evidence and the report.

A principle applies only when its condition holds.

| Id | When | Rule | Test |
|---|---|---|---|
| P1 | You are about to write code | The smallest change that meets the ticket. Reuse what the codebase has. Nothing "for later". | Can a line go with every `Done when` item still met? Then it goes. |
| P2 | You are about to add a rule in prose | Prefer a type, a lint rule, a check, or a script that enforces it. Prose is the weakest guard. | Would the rule hold if nobody read it? |
| P3 | The nearest example in the code is a workaround | Fix the cause, or stop and ask. Do not copy it. | Would a reader copy your code next? |
| P4 | A function can be called wrongly | Change its shape so the wrong call does not compile or fails at once. A code comment about the wrong call does not stop it. | Write the wrong call. Does it fail before it runs? |
| P5 | You add state, or a branch to a long if/else, or a flag that must stay in step with another | List the states and the moves between them first. Make a state that should not exist impossible to represent. | Can you name a value of the new state that means nothing? |
| P6 | Two events can arrive in either order | Test both orders. | Is there a test for the other order? |
| P7 | Data crosses a trust boundary (user input, a network answer, a file, config) | Check and parse it there, once, and keep the error handling. Never remove either to make a change smaller. | Where does this data first enter? Is it checked there? |
| P8 | A check fails, or the code does something you did not expect | Find the cause before changing code. Name two or three candidate causes and the one observation that tells them apart. Revert what a refuted guess added. | Can you say the cause in one sentence that a run could prove false? |
| P9 | You would add a guard, a retry, a default, or a caught error where a symptom shows | Ask whether the state that reached it should exist. If not, the guard hides the bug: fix what produced the state. | Is the state the guard handles a legitimate one? |
| P10 | You write, change, or keep a test | It checks what a caller can observe. Take each expected value from the ticket, never from the code under test. See it fail once, for the reason you expect. | Would it fail if the behaviour broke? Would it still pass if only the internals changed? |
| P11 | A test is hard to write | Treat it as a design problem in the code, and say so. | What would the code need for the test to be easy? |
| P12 | An operation can be retried, sent twice, or stopped halfway | Make it safe to repeat: read the current state, apply only the difference, write a file to a temporary path and rename it into place. | What happens if it runs twice, or crashes at each step? |
| P13 | You report a number (a time, a size, a count) | Rest it on more than one recorded run. Give the run count and the spread. Rule out that it counted cached, skipped, or failed work. | Is the difference larger than the spread between runs? |
| P14 | The same edit repeats across many files | Write the script or codemod, and run that. | Could a reviewer rerun what you did? |
| P15 | You are unsure something works, or a result surprises you | Run it and look. When a result is wrong or comes too easily, first rule out the way you looked: a stale build or cache, the wrong worktree, port, or commit, an earlier run. | Did the run reach the code you changed? |
| P16 | The change would add a dependency, a migration, a deletion of data, or a change to CI or `jtek.json` | Stop with `--waiting approval`, unless the ticket allows that change in so many words. | Did the human write that this is allowed? |
| P17 | A choice is easy to undo, and the ticket does not decide it | Choose the one that changes least of what users see today. Write it down as a `choice:` line. | Would a user notice the other option? |
| P18 | You judge whether a change is safe | Name the one fact the change is safe because of, and prove it with a run. Look where a search stops: a library's own code, stored data, wire formats, flags, other readers of the same data. | Is the fact proven by a run, read in a file, or only said? |
| P19 | You are about to ask the human something | Ask only what neither the code, its history, nor a run can answer. Put the options and your pick in the question. | Could a run have answered it? |
