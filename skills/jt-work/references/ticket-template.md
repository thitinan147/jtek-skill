# Ticket template

Use this form when writing a local ticket file (`jtek.py ticket <file> --save`). Chat goals (`jtek.py start --local --goal "<goal>"`) run directly without a ticket file or `Done when`.

## The body

```markdown
## Goal
<What should be true when this is done, and who needs it. One or two sentences. No guessed cause, and no fix.>

## Done check
- <One outcome that someone can see working. Say the input and the result.>
- <One outcome per item. No nested items. Not a step the skills already run.>

## Proof
- <What to show: the command output, a stored value, or a before and after number.>

## Context
- <What is already known: a symptom, a log, a file, or a link. `none` when there is nothing.>

## Constraints
- <Behaviour that must stay exactly as it is now.>
- <What this ticket does not do yet.>
```

## The header fields

Put header fields right under the `# Title` line, with no blank line between them:

| Field | Set it to |
|---|---|
| `# <title>` | What changes, in a few words: `# Add a phone number to the profile` |
| `id:` | Set by `jtek.py ticket --save` (`T-<n>`) |
| `status:` | `Backlog` while drafting; `Todo` releases a saved ticket file |
| `repo:` | The `name` in that repository's machine config |
| `kind:` | `feature`, `bug`, or `refactor`. It picks the playbook |
| `area:` | The part of the codebase, in a word or two |
| `after:` | A ticket id that must be Done (merged) first |
| `review:` | Leave empty. `human` waives the second session for a small ticket file (ignored on sensitive changes) |
| `checks:` | Leave empty to run every declared check |

## A filled example

```markdown
# Add a phone number to the profile
kind: feature
area: profile

## Goal
A user can add a phone number on the profile page, so that sales can call back.

## Done check
- PATCH /me with a 10-digit `phone` returns 200, and GET /me returns the same number
- a `phone` that is not 10 digits returns 422 and names the field
- the profile page shows the saved number after a reload

## Proof
- the response body of that PATCH and the following GET

## Context
- PATCH /me today ignores `phone`. The handler is `updateProfile` in `lib/me.ts`.

## Constraints
- the response for every other field of /me stays the same, byte for byte
- no SMS confirmation yet
```

## Rules the template stands for

- **Every `Done check` item can be seen working.** Name an input and a result. A quality with no number, such as "fast" or "secure", cannot be checked: `jtek.py ticket` refuses it before `start`, and during work the agent picks a measurable reading as a `choice:` line or saves a follow-up ticket file for the gap.
- **One outcome per item, at the top level.** `start` refuses other text or nested items there, because each item gets one line in the evidence.
- **`Constraints` names behaviour, not a topic.** "Titles with non-ASCII letters give the same slug as today" protects something. "Non-ASCII letters" does not.
- **Small enough for one pull request.** If the items fall into two groups that could ship apart, save two ticket files and link them with `after:`.
- **A bug says how to see it.** Put the steps and the wrong result in `Goal`. The first `Done check` item is the right result for those steps.
- **The headings are named exactly** `Goal`, `Done check`, `Proof`, `Context`, and `Constraints`, or the words your project set as `headings` in the machine config. The rest of the file can be in any language. `Done when` and `Out of scope` are still accepted by `start`, but not by `jtek.py ticket`.
- **No guessed fix, and no steps the skills already run.** Do not add a cause, a fix, a plan, or a list of skills. The playbook already has the steps. A bug's steps and the wrong result go in `Goal`, as facts, not as a theory of the line that is wrong.

## Spec handoff

The handoff a session receives is this same file. Copy the five slots. Do not add a section for the cause, the fix, or the order of skills. `jtek.py ticket <file>` refuses a draft that is missing a slot, that has any other heading, that puts a skill step under `Done check`, or that states a guessed cause or fix.
