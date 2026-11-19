# Review notes template

The author reads these notes to fix the change, and the human reads them before the merge. Write only what you saw happen.

## The form

```markdown
Findings:
- reproduces: <what goes wrong, in one line>
  steps: <the exact command or steps>
  expected: <what should happen, and the `Done when` item or rule that says so>

Notes:
- did not reproduce: <what you suspected, what you tried, what happened>
- <what the tests do not cover>
```

With nothing to report, the first line is `Findings: none`.

## A filled example

```markdown
Findings:
- reproduces: PATCH /me with an empty phone returns 500, not 422
  steps: start the server as `.jtek/verify.md` says, then PATCH /me with phone ""
  expected: 422, by Done when item 2

Notes:
- did not reproduce: a phone with spaces. Tried "081 234 5678", got 422 as it should
- the new tests cover items 1 and 2. Nothing tests item 3
- I broke the length check on purpose, and the new test failed, so the test is real
```

## Rules

- **A finding has steps that fail when anyone runs them.** A suspicion without steps goes under Notes as `did not reproduce`, or is left out.
- **Tie each finding to a `Done when` item, an `Out of scope` line, or something that worked before.** Taste is not a finding.
- **Say what you did not check.** The human decides whether that matters.
- **`FAIL` needs at least one finding.** `PASS+NOTES` has notes and no finding. `PASS` needs no file.
- **Do not paste the diff.** Name the file and the line.
