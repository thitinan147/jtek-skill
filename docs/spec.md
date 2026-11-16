# Spec documents

Human guide for `/jt-spec-split`, `/jt-spec-ac`, `/jt-spec-handoff`, and `/jt-board`. The agent follows each skill's `SKILL.md`. This page is the same rules for people. The queue is a different set of commands: see [Getting started](getting-started.md).

## Why it exists

The PO gets a draft instead of a blank page, dev get acceptance criteria with the code already found, and the tester gets test steps before the code is finished. One story lives in one `spec.md`. The AI proposes. People decide.

## Principles

- **Fact, proposal, or question.** A fact has a source. A proposal is marked "Proposal:". Anything else is a row in Questions.
- **A person's name and a date.** Decisions and the AC approval record who decided. `check.py` fails an approval or a decision given by an AI, and it fails one that has no name and date.
- **Facts come from the code.** The skill reads every repo in `code_roots` before it asks. People are asked only for decisions.
- **You can answer in the file.** Write in the Answer cell, or edit the approve line. The next run records it.
- **These commands do not break work into tasks, estimate, assign owners, write code, commit, or delete.** Dev decide how to build. The queue commands (`/jt-add-task`, `/jt-work`) are the task list. When `/jt-add-task` splits an approved spec into tasks, each `pass:` line is copied from an AC or EC (`- <id>: <Then>`), and the gate checks that id. One spec approval covers those tasks. `/jt-review` is still the only merge.

## Commands

```text
/jt-spec-split <flow>     a whole flow → story map + one folder per story
/jt-spec-ac <work>        story, rules, acceptance criteria, questions
/jt-spec-handoff <work>   test steps, once no question blocks AC
/jt-board [<flow>]        FigJam-style board.html
/jt-help                  every jt- command, the order, and which are human-only
```

Paste the card, bug, or flow after the command, or give a path to a PDF or image.

Headings, table columns, and the marker stay in English because `check.py` reads them. The rest of the text follows the language of your input.

## Files

Everything for one story is in `<docs_root>/<work>/spec.md`. `<work>` starts with the ticket id as the source wrote it, then a short slug (`BOOK-12-book-room`). The id is copied. It is not rewritten into another scheme, and its shape is not checked. The default `docs_root` is `scrum-spec`. That folder name and the first-line marker `<!-- scrum-spec -->` are what the checker looks for. Command names do not use that word.

Order inside the file: Story, Rules, Acceptance Criteria, Questions, Decisions, Test steps. A `## Tasks` section from an older spec is kept as it is and is not checked.

A flow from `/jt-spec-split` also has `<docs_root>/<flow>/map.md`.

Commit `spec.md` with the code. When the ticket is done, delete the folder; git keeps the history.

`scrum-spec/config.md` is optional:

```text
docs_root: scrum-spec
code_roots: ., ../api
roles: PO, BE, UX, QA
```

## Check documents with the script

`check.py` is one module, installed with `/jt-spec-ac`, `/jt-spec-split`, and `/jt-spec-handoff`.

```bash
python3 -I <skill folder>/scripts/check.py scrum-spec/
```

- **Exit 1:** missing marker, a broken table row, an approval or decision without a person and a date or given by an AI, a `✅` approval while an open question Blocks `dev` or `AC`, an EC whose `Guards` cell names no AC or names an AC that is not in the table, a reference to a D that does not exist (including `(incl. D<n>)` and a warning mark before `D<n>`), a path in Source that does not exist (add `(new)` for a file still to be created)
- **Reported, exit 0:** approval status, open and blocking questions, answers not yet recorded, assumptions still waiting, AC/EC with no test step, vague words in AC and EC. A table that still has `| # | Given | When | Then |` and no `Guards` column prints `migration:` and does not fail. Add `Guards` when you next edit it. Each EC names the AC it guards (`AC1`, or `AC1 AC2`).

## The board

```bash
python3 -I <jt-board skill folder>/scripts/board.py scrum-spec/ --open
```

Writes `board.html`. A question is blocking there when `check.py` would report it as blocking, because both scripts use the same `specdoc.py`. Opening the file loads Google Fonts. See [SECURITY.md](../SECURITY.md).
