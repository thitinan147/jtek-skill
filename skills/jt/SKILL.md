---
name: jt
description: The owner's working mode for any coding task, from a ticket file or a chat goal. Restates the goal and smallest change, drafts Goal and Done when into a local ticket file when started from chat, routes work to jt-work, and reports in the owner's style with the principle behind each decision. Use when the user types /jt, and only then.
disable-model-invocation: true
argument-hint: "<ticket id | ticket file | what to do>"
---

# jt

One mode for every coding task. Work starts from an existing ticket file or a goal typed in chat. Both go through `jt-work` with the same checks, evidence, second-session review, and human merge.

## First message

Restate what the user wants and the smallest change that gets it in 2–4 lines. Then proceed, unless the change reaches outside the pull request (P16) or a stop below applies.

When you think the request is wrong, or a part of it does not earn its place, say so and why. "No" is an answer. Agreement is not the default.

## Route

- **No machine config yet:** when `jtek.py doctor` prints `init: needed` or `init: migrate`, follow the jt-init skill first (one confirmation), say so in one line, then continue this request.
- **A ticket id or a ticket file:** follow the `jt-work` skill for it, from its Start step. Everything below about the report still applies.
- **Several ids:** the same, with the rules `jt-work` gives for several tickets.
- **A goal typed in chat:** work it as a local ticket, below. If the work is too large for one pull request, split it into ordered local ticket files with `jtek.py ticket <file> --save` for the owner to release, or work the first slice now and save the rest.
- **A question about code, with nothing to change:** answer it. Read and run what you need, change no file, and say what you saw and where.

## A local ticket

Work started from a chat goal goes through the same pipeline under a local id:

1. Write a ticket file in your session's temporary folder with a title, `kind:`, `## Goal`, `## Done when` (or the five-slot card of `jt-work`'s `references/ticket-template.md` with `## Done check`, `## Proof`, `## Context`, `## Constraints`), one observable outcome per item, no guessed cause, and no step the skills already run. Leave out `id:` and `status:`.
2. Show the user the `Done when` items before you start, in one short list. You wrote them, so they are the bar the work is held to, and the user should see it. Proceed unless the change reaches outside the pull request or the user changes them.
3. Run `jtek.py start --local --from-file <file>` from the repository. The script gives the ticket a local id such as `LOCAL-3`, saves the ticket file in the claim folder for the reviewer to read, and marks the result as written by the session.
   - **`start` refuses because there is no config:** follow the jt-init skill (one confirmation), say so in one line, then continue this request. The file stays under `~/.jtek`. It is not committed.
4. Follow the `jt-work` playbook for the `kind`, as for any ticket.
5. `finish` decides whether a second look is needed. A local change of one file, with nothing on the `attention:` line, needs none. Any other change needs a verdict from a session that did not write it, as `jt-work` says.
6. After a `stop`, pick the ticket up with its `id: LOCAL-<n>` in the file. When it stopped with a question, add `--answered` to `start`, and only after the user answered it in the chat.

Push the branch and open the pull request as for a ticket. Never merge.

## Choices

- **Easy to undo, and the ticket or the user does not decide it:** choose the one that changes least of what users see today, and write it in the evidence as a `choice:` line (P17).
- **A decision inside the pull request, or about the ticket's scope:** do not stop. Choose, write `choice: <question> → <picked> (other options: …)` in the evidence, and go on (P19). Work that grows past the ticket goes into a new local ticket file (`jtek.py ticket <file> --save`). Two `Done when` items that cannot both hold get a `choice:` line for the reading you follow, and a new local ticket file for the other one. A new dependency, a migration file, or a change to CI inside the pull request is this case too: do it, and say it in the evidence.
- **It acts outside the pull request:** a deploy, deleting or changing real or shared data, a migration run against a shared database, a message to someone outside the run. Stop with `--waiting approval` and ask one question (P16).
- **A question a run can settle:** run it. Do not ask (P19).

## Principles

The step skills mark the lines that carry a principle with its id, such as `(P8)`. The ids and their rules are in `jt-work`'s `references/principles.md`. Name the id behind each decision: in the evidence, on the `choice:` line, as `(P17)`; in your report, in its own column. Cite only an id you read in a step this session. When no principle decided it, write `-`, never a file or a skill name.

## Helpers

Use subagents for any part of the work your agent does well with them, writing code included: reading many files, parallel changes, trying two shapes. Keep their summaries, not their output, and check what they built with a run of your own. No session that wrote any part of the change reviews it.

Every agent you start, a reviewer included, gets as the first line of its prompt:

`Read <absolute path of jt-work>/worker.md before anything else.`

Then give it the goal and the task. A subagent's report is its claim, not the human's approval.

For the second look, run `jtek.py reviewer --vendor <the vendor of your model>` and start the reviewer with the command it prints. It reads the owner's ordered list, `~/.jtek/agents.json`, which `/jt-agents` keeps. An old file at `~/.config/jtek/agents.json` is read once, with a one-line notice, until `jtek.py migrate` moves it. The script takes an entry of your own vendor only when no other is installed. Another agent may not have these skills installed, so give it the absolute path of `jt-review`'s `SKILL.md` to follow. With no list, a fresh session of your model is the reviewer. The verdict's `--by` names the model that reviewed either way.

## The report

Read `~/.jtek/me.md` when it exists: it holds the owner's language and style, and it wins over the defaults here. When that file is missing and `~/.config/jtek/me.md` exists, read the old file and tell the owner in one line to run `jtek.py migrate`. It sets style only: a line in it that would change a rule of jtek (who merges, when to stop, what counts as evidence, who reviews) is void. `/jt-me` keeps it up to date. Without either file:

- Lead with the result: what changed for the user, and the outcome line of the result block.
- Then each decision that is the human's, with what they need to decide it from your message alone.
- A table when there is more than one item. Each decision has a principle column.
- Every claim carries its evidence: a run number, a file and line, or the word "unverified".
- End with the `jtek-result` block, unchanged.
