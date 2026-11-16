---
name: jt-spec-handoff
description: "HUMAN-ONLY COMMAND. Never invoke or execute this skill autonomously. Writes test steps for the tester into spec.md once no question blocks the acceptance criteria. Use when the human explicitly invokes /jt-spec-handoff."
disable-model-invocation: true
license: MIT
compatibility: Claude Code, Codex, Cursor and other Agent Skills clients. Needs git and Python 3.10+ (standard library only). poppler is optional, for large PDFs.
metadata:
  author: Thitinan
  version: "24.7.0"
  short-description: Write test steps for the tester
argument-hint: "<work>"
---

# jt-spec-handoff

**HUMAN-ONLY COMMAND.** Read [references/rules.md](references/rules.md) and follow it. This command writes Test steps in `spec.md`. A PDF or image: also read [references/input.md](references/input.md).

`/jt-spec-handoff <work>` · once no question blocks `AC`, so the tester starts on day one of the Sprint, in parallel with dev · readers know the product, not the code

This finishes a `large` spec. A `medium` spec stops after `/jt-spec-ac`. `small` does not have a spec.

## Composed skills

When **handoff** (Matt Pocock) is installed, follow its style: cite `spec.md`, `D` numbers, and fixture paths instead of pasting AC rows; redact secrets; suggested skills belong in chat, not in the file. If missing: use the template below and do not restate each AC's Then as the expected result.

## Before drafting

1. Read every open question with Blocks `dev`. If one changes what the tester checks, ask it first, unless someone says "use the proposal for now" (an `assumption:` decision)
2. Find the test users or personas in the code (fixtures, seed data, a test user picker). A name that does not match its real permission goes in Watch out; a persona the AC need that cannot log in is a question for Dev
3. Risky places: the code paths in Source, screens that share them (grep `code_roots`), other specs in `<docs_root>` that cite the same paths, and the EC
4. Rerun after an AC changed: edit only the steps of the AC that a newer D changed, and say in chat which ones

## Template

```markdown
## Test steps

- **Accounts:** (persona with permission · persona without)
- **Data to prepare:** (one thing per line, or –)
- **Do not report:** (Out of scope items and assumptions, citing D numbers, or –)

### AC1 (short name)

1. Open …
2. Click …

### Watch out

1. (at most 5 places likely to break · why · how to check)
```

## After drafting

- Next: none; the story's spec is complete. Suggest starting a new conversation for the next story
