# Review notes template

The author reads these notes to fix the change, and the human reads them before the merge. Write only what you saw happen.

## The form

```markdown
Findings:
- reproduces: <what goes wrong, in one line>
  steps: <the exact command or steps>
  expected: <what should happen, and the `Done when` item or rule that says so>

Notes:
- to weigh: <a behaviour the human may not want, which the ticket does not settle>
- item <n> seen: <what you ran, and what you saw>
- broke: <the line you broke, and which checks failed or still passed>
- stand-in: <what you used in place of the real thing, and for which case>
- did not reproduce: <what you suspected, what you tried, what happened>
- not checked: <what you did not look at>
- safe because: <the one fact the change is safe because of> (run <n> | read: <file>:<line> | unproven)

Dropped:
- nit: <a rename, a style note, or anything that is not a bug; left out of the verdict>
```

Use the lines that apply, and leave out the rest. `Dropped` is optional. Nothing under it changes the verdict.

With nothing to report, the first line is `Findings: none`.

## A filled example

```markdown
Findings:
- reproduces: PATCH /me with an empty phone returns 500, not 422
  steps: start the server as `.jtek/verify.md` says, then PATCH /me with phone ""
  expected: 422, by Done when item 2

Notes:
- item 1 seen: PATCH /me with phone "0812345678" answered 200, and GET /me showed it
- did not reproduce: a phone with spaces. Tried "081 234 5678", got 422 as it should
- the new tests cover items 1 and 2. Nothing tests item 3
- broke: the length check in lib/validate.ts; the test check failed, so the test is real
- safe because: the validator already guards the signup form, and its tests pass unchanged (run 4)
```

## Rules

- **A finding has `steps:` or `scenario:`, and `expected:`.** A suspicion without them goes under Notes as `did not reproduce`, or is left out. The script refuses a `- reproduces:` line that has neither.
- **Tie each finding to a bug or a regression:** a `Done when` item, an `Out of scope` line, or something that worked before. A nit goes under `Dropped` or is left out. Taste is not a FAIL.
- **Say what you did not check.** The human decides whether that matters.
- **`FAIL` needs at least one such finding.** `PASS+NOTES` has no finding and at least one `to weigh:` line. `PASS` has neither. Both passes need at least one `broke:` line and a `safe because:` line, and the script refuses a pass without them. The script also refuses a FAIL that is only a nit.
- **Do not paste the diff.** Name the file and the line.
