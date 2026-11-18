# Contributing

Thanks for helping. Issues and pull requests are welcome.

## Report a problem

- **Bug or unclear behaviour:** open an issue and include your agent (Claude Code, Cursor, ...), OS, Python version, the command you ran, and the script output (the `refused:` line helps most).
- **Security problem:** do not open a public issue. See [SECURITY.md](SECURITY.md).

## Change the code

1. Fork, then branch from `main`.
2. Run the tests: `python3 -m unittest discover -s tests` (Python 3.10+, standard library only).
3. Keep the skills dependency-free, and do not make a skill depend on another skill set.
4. `jt-work` owns the order of the steps and the script. A step's judgement goes in that step's skill. `skills/jt-work/scripts/jtek.py` is the source. Copy it to `skills/jt-review/scripts/jtek.py` after every change. A test fails when the two differ. They are real copies because an installer may place each skill on its own.
5. If you change a status, the ticket format, or the result block, update `skills/jt-work/references/ticket.md`, the README, and `CHANGELOG.md`, and add or adjust a test.
6. Open a pull request that says what changed and why.

Commit messages follow `type(scope): summary` (for example `fix(check): ...`).
