# Spec rules

These rules apply to `/jt-spec-split`, `/jt-spec-ac`, and `/jt-spec-handoff`. `/jt-help` lists every command and the order. `/jt-board` draws the spec board; `flow` prints queue metrics.

Goal: remove waiting. The PO edits a draft instead of a blank page, dev start from AC with the code found, the tester has test steps on day one. Write what someone acts on; each fact lives in one place.

## Rules

- **Fact, proposal or question, never a guess.** A fact has a source (path, input page, D number); a proposal says "Proposal:" and why; anything else is a row in Questions.
- **People decide.** The PO decides scope, rules and AC; dev decide how to build. Never fill in points, priority, owner or capacity. Never break work into tasks, estimate, write code, commit, push, delete or move files.
- **Every decision has a person's name:** `git config user.name` for chat answers; for answers in the file, the name written there, else `git blame`, else ask. Never an AI.
- **Ask before** overwriting text a person wrote (`git diff`).
- **Language:** headings, labels, columns and markers stay as in the templates (`check.py` reads them); other text follows the file, or the input for a new file.
- No passwords, tokens or customer personal data in documents.

## Where files live

- `<docs_root>/<work>/spec.md` per story (`<flow>/<story>` from `/jt-spec-split`). `<work>` starts with the ticket id as the source wrote it, then a short slug of lowercase words (`BOOK-12-book-room`). Copy the id. Do not invent one and do not require a particular shape. A character a folder cannot hold (`#`, space) becomes `-`
- `scrum-spec/config.md` at git root is optional, with defaults. The folder name stays `scrum-spec` because `check.py` reads it:

```
docs_root: scrum-spec
code_roots: .
roles: PO, Dev, QA
```

`code_roots`: every repo to search (e.g. `., ../api`); `roles` fill the Ask column.

`spec.md` starts with `<!-- scrum-spec -->` and `# <work>`, then `## Story`, `## Roles`, `## Rules`, `## Acceptance Criteria`, `## Questions`, `## Decisions`, `## Test steps`. `## Roles` names the human approver, reviewer, and merger, plus human-only paths or topics. A 0.2 `## Tasks` section is kept as is. The marker and those headings stay, because `check.py` reads them.

## Workflow

1. **Find the work:** the name given, else the one in this conversation, else ask, listing existing folders. Read this file, this command's skill, and the existing `spec.md`.
2. **Gather facts yourself:** the input, then every `code_roots` path (screens, routes, APIs, permissions, fixtures); grep other specs instead of reading them whole. Ask people only for decisions and facts not in the repo. A contradiction: cite the path and ask.
3. **Write only this command's sections,** plus edits a decision requires (item 6). An existing section is the base: change only what has new information. If a person's edit to Rules or AC left Test steps behind, update them and say so. Headings and columns exactly as the template; text in parentheses is an instruction.
4. **Check:** run `python3 -I <this-skill-dir>/scripts/check.py <folder>` (`<this-skill-dir>` holds the SKILL.md you were given). Fix every `ERROR`, rerun; if it cannot run, say so.
5. **Ask** in the same turn, never ending on a bare list. When **grill-me** is installed, invoke it (human-only) and keep these outcomes: at most 4 questions that change scope, an AC, or an API; each with a "(Recommended)" option and "Don't know / ask <role>"; the rest stay in the Questions table. When **brainstorming** is installed and the idea is unclear before drafting, invoke it first. When a skill is missing, ask one short round with those same outcomes yourself.
6. **Apply answers at once** (from chat, or an Answer cell someone filled in):
   - add `- **D<n>** <what was decided> · <name> · <YYYY-MM-DD>` to Decisions and delete the question's row
   - fix every section it affects, replacing the old text; grep other specs in `<docs_root>` for the same rule and fix them too, each with its own D starting `per <work> D<n>:`
   - approval: a change that follows a D keeps a ✅ and appends `(incl. D<n>)`. Any other change to Rules or AC sets `**approve:** ❌ waiting for PO (changed <YYYY-MM-DD>)`. An open question that Blocks `dev` or `AC` fails a ✅
   - "use the proposal for now": start the D with `assumption:` and keep the row with Answer `⚠️ D<n>` until the asked role confirms
7. **Reply** in this format plus any line the command adds, never the whole document:

```
✅ <command> · <work> · saved <path>
Added: <e.g. AC 5 · EC 3 · Questions 2 (blocking 1)>
Decisions: <D numbers, or none> · approve: <✅ name · date / ❌ waiting for PO>
Waiting on: <role: Q numbers, or none>
Next: </jt-spec-split | /jt-spec-ac | /jt-spec-handoff | /jt-board> <work>, or none
```

Input from a PDF or image: also read `references/input.md` in this skill.
