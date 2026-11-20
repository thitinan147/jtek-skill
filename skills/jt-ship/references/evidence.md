# Evidence template

The human reads this file before the diff, and it is the body of the pull request. Write what you ran and what you saw. Do not write that it works.

## The form

```text
<What changed and why, in two or three sentences.>

1. seen: <the command or the steps> -> <what you saw>
2. seen: <the command or the steps> -> <what you saw>
3. not run: <why you could not see it>

Notes:
- out of scope: <how you compared it with the base, and that it is the same>
- <a choice the ticket left open, and what you chose>
- <something the reviewer should look at first>
```

## A filled example

```text
The profile now stores a phone number. PATCH /me validates it with the existing validator, and the page shows it.

1. seen: PATCH /me with phone "0812345678" on the local server -> 200, then GET /me returns "0812345678"
2. seen: PATCH /me with phone "12ab" -> 422 {"field":"phone","error":"must be 10 digits"}
3. not run: no browser on this machine, so the profile page was not opened. The API returns the value

Notes:
- reused the validator in lib/validate.ts
- the number is stored as text, because a leading 0 is lost in a number
- attached: profile-api.txt (the full output of items 1 and 2)
```

## Rules

- **One numbered line per `Done when` item, in the ticket's order.** It starts with the number, then `seen:` or `not run:`. The script refuses a file that skips an item.
- **`seen:` means you ran it and looked.** Give the exact command, request, or steps, then the result after `->`. A passing test counts when you name the test and it covers the item.
- **`not run:` is honest, not a failure.** Give the reason. The human then knows what to check by hand.
- **Never write `seen:` for something you only read in the code.**
- **At most 40 lines that are not blank.** Put long output in a file and pass it with `--attach`.
- **Notes are short.** A choice you made, a workaround you did not copy, a file the reviewer should open first.
- **Write it again when the code changes.** The script refuses evidence that was saved for an older change.
