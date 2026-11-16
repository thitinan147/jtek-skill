---
name: jt-spec-ac
description: "HUMAN-ONLY COMMAND. Never invoke or execute this skill autonomously. Drafts the story, rules, acceptance criteria, and questions for one spec.md from the code and the input. People decide. Use when the human explicitly invokes /jt-spec-ac."
disable-model-invocation: true
license: MIT
compatibility: Claude Code, Codex, Cursor and other Agent Skills clients. Needs git and Python 3.10+ (standard library only). poppler is optional, for large PDFs.
metadata:
  author: Thitinan
  version: "25.0.0"
  short-description: Draft story, rules, acceptance criteria, and questions
argument-hint: "<work> [text or path of a PDF or image]"
---

# jt-spec-ac

**HUMAN-ONLY COMMAND.** Read [references/rules.md](references/rules.md) and follow it. This command writes Story, Rules, Acceptance Criteria, and Questions in `spec.md`. A PDF or image: also read [references/input.md](references/input.md).

`/jt-spec-ac <work>` plus a card, a bug report, or a PDF or image path · for Refinement · readers do not read the code

Goal: the PO approves a draft instead of writing one, and what two devs could build differently is asked before Planning.

## Composed skills

When **grill-me** (Matt Pocock) is installed, invoke it after `check.py` to sharpen the draft; `check.py` still blocks approval while a question blocks `dev` or `AC`. When **brainstorming** (superpowers) is installed and the card or flow is unclear, invoke it before drafting. If a skill is missing: one short question round per [references/rules.md](references/rules.md) step 5. When the story has states, invoke pstack `/statechart` before AC freeze; if it is missing, list each state in Rules.

## Before drafting

1. Create `<docs_root>/<work>/spec.md` if missing (a story from `/jt-spec-split` already has its Story)
2. Grep other specs in `<docs_root>` for the same screen or rule; cite them in Source and reuse their rule wording
3. Find what already exists in the code: screens, routes, APIs, permission checks. A found fact is a source, not a question

## Rules

- Story and Rules come from the input. A missing part is "Proposal: …"
- One AC row is one visible behavior. AC is the main flow. EC is an edge case.
- Story, Rules and AC use on-screen words. Paths go in Source.
- Every control and state is an AC/EC, Out of scope, or a question.
- **Bug:** Story has **Now**, **Expected** and **Repro**. AC is the correct behavior. EC must not change.
- A new API asks its owner (else Dev), Blocks `dev`, with a one-line contract.
- Keep existing AC. A cut AC keeps its number in Out of scope.
- **Size** is `small`, `medium`, or `large`. `small` uses `/jt-add-task`. `medium` stops here. `large` continues with `/jt-spec-handoff`.

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

## Roles

- **approver:** (human name)
- **reviewer:** (human name)
- **merger:** (human name, never an AI)
- **human-only:** `src/auth/**` · payments

## Rules

- **(group, e.g. Permissions)**
  - (one rule per line)

## Acceptance Criteria

**approve:** ❌ waiting for PO

| # | Given | When | Then | Guards |
|---|---|---|---|---|
| AC1 | | | | |
| EC1 | | | | AC1 |

## Questions

| # | Question | Ask | Blocks | Answer |
|---|---|---|---|---|
| Q1 | (one question; "Proposal: …" if there is one) | (a role) | AC / dev / later | |

## Decisions

- (none yet)
```

- Blocks: `AC` = needed to approve · `dev` = needed before dev start · `later` = changes nothing structural
- Roles: human approver, reviewer, and merger. human-only is paths or topics. `check.py` checks names and globs.
- EC Guards names its AC. A missing link fails. No Guards column prints a migration line.
- The PO approves in chat, or by editing the line to `**approve:** ✅ <name> · <YYYY-MM-DD>`

## After drafting

- Too big (over 4 rule groups): propose a split and ask
- Next: `/jt-spec-handoff` once no question blocks `AC`
