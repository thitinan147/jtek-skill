---
name: jt-spec-split
description: "HUMAN-ONLY COMMAND. Never invoke or execute this skill autonomously. Splits a flow into a story map and one spec folder per story the PO confirms. Use when the human explicitly invokes /jt-spec-split."
disable-model-invocation: true
license: MIT
compatibility: Claude Code, Codex, Cursor and other Agent Skills clients. Needs git and Python 3.10+ (standard library only). poppler is optional, for large PDFs.
metadata:
  author: Thitinan
  version: "24.12.0"
  short-description: Split a flow into a story map and one folder per story
argument-hint: "<flow> [text or path of a PDF or image]"
---

# jt-spec-split

**HUMAN-ONLY COMMAND.** Read [references/rules.md](references/rules.md) and follow it. This command only writes the story map, then a `spec.md` per confirmed story. A PDF or image: also read [references/input.md](references/input.md).

`/jt-spec-split <flow>` plus the flow's text, or a PDF or image path · for Refinement, before `/jt-spec-ac` · readers are the PO and people who do not read the code

The goal: the PO edits a story map instead of splitting a board by hand. The split, order and cuts stay proposals until the PO confirms.

## How to split

1. **Steps:** list the user's activities in flow order, from the input only, each with who does it and its source
2. **First slice:** the thinnest set of stories that works end to end
3. **Stories:** split along one axis at a time: workflow steps (straight path first), then operation (create / edit / cancel), business rule, simple before complex · a time-boxed spike only when no one knows how to build it
4. **Vertical:** every story gives the user something they can see or use. Never a story per layer ("build the API"); API work is part of the story that uses it
5. **Nothing dropped:** every step is in a story or in Not now

## Rules

- Check every `code_roots` path for each step's screen, route or API. Size signals are those facts ("existing screen", "needs a new API"); never points, S/M/L or days
- No paths in Steps or Stories; code evidence goes in Source · story names are lowercase words joined by `-`

## Template

Save to `<docs_root>/<flow>/map.md`:

```markdown
<!-- scrum-spec -->
# Story map · <flow>

**approve:** ❌ waiting for PO

## Steps

1. (activity) — (who) · (source in input)

## Stories

| Story | Steps | Once done, the user can | Size signal |
|---|---|---|---|
| `<story>` | 1–3 | (1 sentence) | (fact, 1 sentence) |

## Not now

- (topic) — (reason)

## Questions

| # | Question | Ask | Blocks | Answer |
|---|---|---|---|---|
| Q1 | (e.g. "Proposal: first slice is A and B, because …") | PO | stories | |

## Decisions

- (none yet)

## Source

- (code paths found per story)
```

Stories are in the order the PO confirmed; until then, the proposed order plus a question to confirm it.

## After drafting

1. Ask about the split and the first slice first
2. Show the list of story folders to create and ask. The folder is `<ticket-id>-<slug>`: the id copied from the source, then lowercase words (`BOOK-12-book-room`). For each confirmed story create `<docs_root>/<flow>/<story>/spec.md` containing `<!-- scrum-spec -->`, `# <story>` and `## Story` with `- **Ticket:**` set to that same id (ask once if the input has none; do not invent one), `- **Story:**`, `- **In scope:**`, `- **Out of scope:**` and `- **Source:**` filled from the map, then run `python3 -I <this-skill-dir>/scripts/check.py` on it
3. Next: `/jt-spec-ac <flow>/<first story>`
