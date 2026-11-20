# A feature that spans two repositories

For example a backend and a frontend that live in separate repositories. A ticket, a worktree, the checks, the verdict, and the pull request each belong to one repository. So a feature that changes both is two tickets, and a session works in one repository.

What keeps the two sides in agreement is a contract file and checks that read it. Words in a ticket do not.

## Set up once, by the human

**In the repository that serves the interface (the provider):**

1. Keep the contract as a tracked file, for example an OpenAPI file or a schema.
2. Declare a check that fails when the code and the contract differ.

**In the repository that calls it (the consumer):**

1. Keep a copy of the contract file, and a pin file `.jtek/contract.pin` holding the provider commit the copy came from. A worktree sits at `<repo>.jtek/<id>`, so a path like `../provider` points at the wrong place. The copy lets checks run anywhere.
2. Declare a check that fails when the code uses something the copy does not have. With generated types, this is the type check.
3. Make the `verify` check do three things, in this order:
   - Refuse a pin that is not on the provider's base branch.
   - Refuse a copy that differs from the provider's contract at the pin.
   - Start the provider at the pin, and drive the consumer against it. Do not use a mock here.
4. Say in `.jtek/verify.md`, under Launch, where the provider comes from: an environment variable holding the path of a clone, a remote to fetch, or a container image. A check receives the environment of the session that runs it.

A check command is one program with arguments, so each of these is a script.

## The tickets

- One ticket per repository, each with `repo:`. The provider's ticket comes first.
- Put the contract change in the provider ticket's `Done when`, so the evidence covers it.
- Set After on the consumer's ticket to the provider's ticket. Both are on the same board, so the consumer's ticket file carries `after:` until the provider's ticket is Done, which means merged, and `start` refuses it until then.
- After keeps the order. The checks below keep the two sides in agreement.

## Working the consumer's ticket

1. Move the pin to the newest commit on the provider's base branch, and copy the contract file from that commit. Commit both. Read that commit from the provider's remote: a fresh clone or fetch in a temporary folder outside the worktree, from the place `.jtek/verify.md` names. A folder of the provider that happens to sit on this machine may be old, and is not yours to change.
2. Build against the copy. Never edit the copy by hand.
3. If the copy lacks what the ticket needs, the provider's change is not merged. Stop: `jtek.py stop <id> --waiting input --note "<what the contract lacks>"`. Do not pin an unmerged commit, and do not add the field yourself.

The pin is under `.jtek/`, so the result names it on the `attention:` line, and `review: human` is ignored for that ticket. This is intended: the pin decides which provider the proof ran against.

## What each check catches

| Mistake | Caught by |
|---|---|
| The provider's code changes and the contract does not | The provider's contract check |
| The consumer uses a name the contract does not have | The consumer's contract or type check |
| The consumer's copy was edited by hand | `verify`: the copy differs from the pin |
| The consumer pins a commit that is not merged | `verify`: the pin is not on the base branch |
| Both sides pass alone and fail together | `verify`: the real provider is driven |

## Limits

- A consumer that never moves its pin keeps passing against an old provider. Nothing here notices. A scheduled job that moves the pin and runs the checks closes this, and it is outside this skill set.
- Merging the contract before the provider's code makes the provider's contract check fail on the base, and then `start` refuses every ticket there. Do this only when that check runs one way: everything the code serves is in the contract, and not the reverse.
- A change that removes or renames something the consumer uses needs three steps: the provider adds the new form, the consumer moves to it, the provider removes the old form.
