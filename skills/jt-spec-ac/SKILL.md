---
name: jt-spec-ac
description: "HUMAN-ONLY COMMAND. Never invoke or execute this skill autonomously. Drafts the story, rules, acceptance criteria, and questions for one spec.md from the code and the input. People decide. Use when the human explicitly invokes /jt-spec-ac."
disable-model-invocation: true
license: MIT
compatibility: Claude Code, Codex, Cursor and other Agent Skills clients. Needs git and Python 3.10+ (standard library only). poppler is optional, for large PDFs.
metadata:
  author: Thitinan
  version: "24.2.1"
  short-description: Draft story, rules, acceptance criteria, and questions
argument-hint: "<work> [text or path of a PDF or image]"
---

# jt-spec-ac

**HUMAN-ONLY COMMAND.** Read [references/rules.md](references/rules.md) and follow it. This command writes Story, Rules, Acceptance Criteria, and Questions in `spec.md`. A PDF or image: also read [references/input.md](references/input.md).

`/jt-spec-ac <work>` plus a card, a bug report, or a PDF or image path · for Refinement · readers do not read the code

Goal: the PO approves a draft instead of writing one, and what two devs could build differently is asked before Planning.

## Before drafting

1. Create `<docs_root>/<work>/spec.md` if missing (a story from `/jt-spec-split` already has its Story)
2. Grep other specs in `<docs_root>` for the same screen or rule; cite them in Source and reuse their rule wording
3. Find what already exists in the code: screens, routes, APIs, permission checks. A found fact is a source, not a question

## Rules

- Story and Rules come from the input; a missing part (often "so that") is written "Proposal: …"
- One AC row = one behavior a person can see or check. AC = main flow · EC = edge cases (empty, too long, no permission, failure, double submit)
- Story, Rules and AC use words seen on screen, no paths, fields or endpoints; code evidence goes in Source
- Every button, field and state (empty, error, no permission) on input screens is in an AC/EC, Out of scope, or a question
- **Bug:** the Story section has **Now**, **Expected** and **Repro** instead of the user story. AC = the correct behavior · EC = what must not change
- A new or changed API: a question for its owner in `roles` (else Dev), Blocks `dev`, with a one-line proposed contract
- Keep existing AC and add only what is missing; a cut AC keeps its number in Out of scope ("was EC4")
- **Review before asking:** read the draft as a dev and as the tester; fix or ask about the places two people would read differently (data rules, permissions, states, errors, vague words like "fast" or "own")
- **Size** on the Story is `small`, `medium`, or `large` (how much process, not points). `small`: do not draft; the human uses `/jt-add-task`. `medium`: this spec is enough. `large`: continue with `/jt-spec-handoff`

## Template

```markdown
## Story

- **Ticket:** (the id the ticket already has, copied as written, or ask)
- **Size:** small | medium | large
- **Story:** As a … I want … so that …
- **In scope:**
  - (one topic per line)
- **Out of scope:**
  - (one topic per line)
- **Source:** (input page or frame, related specs, code paths found)

## Rules

- **(group, e.g. Permissions)**
  - (one rule per line)

## Acceptance Criteria

**approve:** ❌ waiting for PO

| # | Given | When | Then |
|---|---|---|---|
| AC1 | | | |
| EC1 | | | |

## Questions

| # | Question | Ask | Blocks | Answer |
|---|---|---|---|---|
| Q1 | (one question; "Proposal: …" if there is one) | (a role) | AC / dev / later | |

## Decisions

- (none yet)
```

- Blocks: `AC` = needed to approve · `dev` = needed before dev start the work · `later` = changes nothing structural
- The PO approves in chat, or by editing the line to `**approve:** ✅ <name> · <YYYY-MM-DD>`

## After drafting

- Too big (over 4 rule groups): propose a split and ask
- Next: `/jt-spec-handoff` once no question blocks `AC`
