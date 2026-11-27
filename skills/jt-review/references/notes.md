# Review notes template

The author reads these notes to fix the change, and the human reads them before the merge. Write only what you saw happen.

## The form

```markdown
Findings:
- reproduces: <what goes wrong, in one line>
  steps: <the exact command or steps>
  expected: <what should happen, and the `Done when` item or rule that says so>

Notes:
- design: <one line on whether the shape of the change fits the ticket>
- to weigh: <a behaviour the human may not want, or a coverage gap, which the ticket does not settle>
- follow-up: <the new card for that gap: its id from `jtek.py ticket --save` with no board, or the path of a draft ticket file for the outer loop when a board is configured>
- item <n> seen: <what you ran, and what you saw>
- broke: <sealed broke.json covers items 1–N at this commit; seal intact; did not re-break> | <the line you broke, and which checks failed or still passed>
- stand-in: <what you used in place of the real thing, and for which case>
- did not reproduce: <what you suspected, what you tried, what happened>
- not checked: <what you did not look at>
- safe because: <the one fact the change is safe because of> (run <n> | read: <file>:<line> | unproven)

Dropped:
- nit: <a rename, a style note, or anything that is not a bug; left out of the verdict>
```

Use the lines that apply, and leave out the rest. `design:` is required. `Dropped` is optional. Nothing under it changes the verdict.

With nothing to report, the first line is `Findings: none`.

## A filled example

```markdown
Findings:
- reproduces: PATCH /me with an empty phone returns 500, not 422
  steps: start the server as the verify guide says, then PATCH /me with phone ""
  expected: 422, by Done when item 2

Notes:
- design: the check sits in the shared validator, not in the route, which fits a ticket about every form that takes a phone
- item 1 seen: PATCH /me with phone "0812345678" answered 200, and GET /me showed it
- did not reproduce: a phone with spaces. Tried "081 234 5678", got 422 as it should
- broke: sealed broke.json covers items 1–3 at this commit; seal intact; did not re-break
- to weigh: item 3 (the error names the field) is true, but no declared check fails when the field name is dropped from the message
- follow-up: T-58, saved with `jtek.py ticket --save`, adds a test for the field name in the error
- safe because: the validator already guards the signup form, and its tests pass unchanged (run 4)
```

## Rules

- **A finding has `steps:` or `scenario:`, and `expected:`.** A suspicion without them goes under Notes as `did not reproduce`, or is left out. The script refuses a `- reproduces:` line that has neither.
- **Tie each finding to a P0 or P1 bug:** a `Done when` item that is false, a regression (an `Out of scope` line, or something that worked before), a security issue, or data loss. Compare the change with the ticket, and skip style. A nit goes under `Dropped` or `Nits`, or is left out. A nit anywhere else in the notes blocks a pass. Taste is not a FAIL.
- **A coverage gap is a `to weigh:` line and a `follow-up:` card, not a finding.** No declared check would notice if a `Done when` behaviour stopped being true, but the behaviour is right today. With a board, write a draft ticket file and put its path on `follow-up:` for the outer loop instead of touching the board yourself. A behaviour that is actually wrong is a finding.
- **`broke:` may cite the sealed proof.** After you check that `broke.json` covers every `Done when` item at this commit and that its seal is intact, the `broke:` line says so instead of a break you made yourself. Do not leave it out: the script refuses a pass without it. A break you made in a deep review gets its own `broke:` line.
- **Say what you did not check.** The human decides whether that matters. When there is no verify guide, say so.
- **`FAIL` needs at least one such finding.** `PASS+NOTES` has no finding and at least one `to weigh:` line. `PASS` has neither. Both passes need at least one `broke:` line and a `safe because:` line, and the script refuses a pass without them. The script also refuses a FAIL that is only a nit. `design:` and `follow-up:` are read by the human; the script does not check them.
- **Do not paste the diff.** Name the file and the line.
