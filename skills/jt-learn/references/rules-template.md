# Template for `~/.jtek/repos/<repo id>/rules.md`

A short table of what this project has learned the hard way. Each row names what enforces the rule. A rule that nothing enforces is a wish, and it is the first to replace.

## The file

```markdown
# Rules

| Rule | Enforced by | Since | Why |
|---|---|---|---|
| Money is an integer number of cents | type `Cents` in `lib/money.ts`; lint rule `no-float-money` | 2026-03-02 | A rounding bug shipped twice |
| Every endpoint checks the caller's tenant | test helper `forEachRoute` in `test/tenant.test.ts` | 2026-04-11 | A ticket added a route with no check |
| Migrations never drop a column in the same release that stops writing it | check `migrations` in `jtek.json` | 2026-05-20 | A deploy lost data on rollback |
| Do not mock the database in integration tests | prose | 2026-06-01 | Mocks hid a broken query. To replace: a lint rule on `jest.mock('db')` |

## Exceptions

| Rule | Where | Reason | Until | Approved by |
|---|---|---|---|---|
| Money is an integer number of cents | `reports/legacy.ts` | Reads a vendor file that has floats | 2026-09-30 | the human |
```

## Rules for the table

- **Add a row only for a mistake that happened twice.** Once is an accident.
- **Prefer the strongest enforcer that fits:** architecture first (make the wrong shape impossible), then a type, then a lint rule whose error says what to use instead, then a test or a check. A written reminder is not a fix for a mistake that already happened twice.
- **`prose` is only the first record.** `jtek.py lesson` refuses a second prose record of the same mistake. The row says what would replace it, and that replacement is the next change.
- **Drop a row when the mistake cannot happen any more,** for example when the type makes it impossible.
- **An exception needs a reason, an end date, and the human's approval.** Remove it when the date passes.
- **Keep it short.** Past about twenty rows, nobody reads it, and the rules belong in code.
