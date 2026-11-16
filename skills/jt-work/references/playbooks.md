# Playbooks for `do-task`

The gate checks evidence, not method. See SKILL.md for when to invoke **executing-plans** and **test-driven-development**. Those skills are not bundled here.

## If superpowers skills are missing

Write `plan.md` from the template, keep changes inside `files:` and `do:`, run `<TEST_CMD>` green, and fill `## evidence` for every `pass:` before `reach-review`.

## Gate habits (always)

- Never cut security, input validation at a trust boundary, or error handling to save effort.
- Start each task from `gate.py next`; re-read `task.md` and `jt-queue/lessons.md`. Prefer a fresh session per task when you can.
- Inside `files:`, remove dead code before adding; do not tidy files outside `files:`. Before the draft PR, compose pstack /no-comments. If that skill is missing, delete comments that restate the code and unused code inside `files:`.
- A story with states composes pstack /statechart at `/jt-spec-ac` before AC freeze. If that skill is missing, list each state in Rules.
- Optional `<IMPORT_CMD>` is an import boundary (dependency-cruiser or import-linter). Optional `<PBT_CMD>` is a property check (fast-check or Hypothesis). A failure names the fix. Do not silence the rule or delete the property to get past the gate.
- `gate.py loop` plans a batch with mise and reviewdog when they are installed. Testcontainers, Pact, and act stay optional. Each ticket starts from the latest queue commit. Skip a task that depends on unmerged work.
- Review the diff against `files:` and `out:` before `review:`; write what you checked in `## review-diff` (not your memory of the change).

## If no reviewer skill is installed

Write `fallback: no reviewer skill installed` under `## ai-review`. Do not invent findings, and do not run a second reviewer.

## Screen

Use Microsoft's Playwright CLI. Do not use Playwright MCP. Install with `npm install -g @playwright/cli@latest` then `playwright-cli install --skills`. Docs: https://playwright.dev/docs/getting-started-cli and https://playwright.dev/agent-cli/skills

One session per worktree. Pass `-s=<ticket-id>` on every call (the long flag is `--session`).

1. `playwright-cli -s=<ticket-id> open <url>` and do the AC steps on the touched screens.
2. `playwright-cli -s=<ticket-id> console error`. Read network errors too (`Failed to load resource`, `net::ERR_`). An uncaught error or a console error is `finding:` in `## evidence`, tied to that AC id. Do not record the row as ok.
3. Put a screenshot path in that row (`.png`, `.jpg`, or `.webp`). A short video (`.webm`, `.mp4`) or trace (`.zip`) path is optional.
4. The gate decides with `<VERIFY_CMD>`: `npx playwright test`, including `toHaveScreenshot`. Do not pass `--update-snapshots` or `-u`. `updateSnapshots` stays `none`. A baseline update is a separate step a human reviews. This task does not accept new snapshots.