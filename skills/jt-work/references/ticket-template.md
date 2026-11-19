# Ticket template

Copy the body below into a new page on the board. To get it on every new page, make it a template of the database in Notion: open the database, choose **New**, then **New template**, paste the body, and set it as the default.

## The body

```markdown
## Goal
<What should be true when this is done, and who needs it. One or two sentences.>

## Done when
- <One outcome that someone can see working. Say the input and the result.>
- <One outcome per item. No nested items.>

## Out of scope
- <Behaviour that must stay exactly as it is now.>
- <What this ticket does not do yet.>
```

## The properties

| Property | Set it to |
|---|---|
| Name | What changes, in a few words: `Add a phone number to the profile` |
| Status | `Backlog` while you write. `Todo` releases it |
| Repo | The `name` in that repository's `jtek.json` |
| Kind | `feature`, `bug`, or `refactor`. It picks the playbook |
| Area | The part of the codebase, in a word or two |
| After | A ticket that must be merged first |
| Review | Leave empty. `human` waives the second session for a small ticket |
| Checks | Leave empty to run every check |

## A filled example

```markdown
## Goal
A user can add a phone number on the profile page, so that sales can call back.

## Done when
- PATCH /me with a 10-digit `phone` returns 200, and GET /me returns the same number
- a `phone` that is not 10 digits returns 422 and names the field
- the profile page shows the saved number after a reload

## Out of scope
- the response for every other field of /me stays the same, byte for byte
- no SMS confirmation yet
```

## Rules the template stands for

- **Every `Done when` item can be seen working.** Name an input and a result. A quality with no number, such as "fast" or "secure", cannot be checked, and the agent will stop and ask.
- **One outcome per item, at the top level.** `start` refuses other text or nested items there, because each item gets one line in the evidence.
- **`Out of scope` names behaviour, not a topic.** "Titles with non-ASCII letters give the same slug as today" protects something. "Non-ASCII letters" does not.
- **Small enough for one pull request.** If the items fall into two groups that could ship apart, write two tickets and link them with After.
- **A bug says how to see it.** Put the steps and the wrong result in `Goal`. The first `Done when` item is the right result for those steps.
- **The headings are named exactly** `Goal`, `Done when`, and `Out of scope`, or the words your project set as `headings` in `jtek.json`. The rest of the page can be in any language.
