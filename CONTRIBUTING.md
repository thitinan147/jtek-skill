# Contributing

Thanks for helping. Issues and pull requests are welcome.

## Report a problem

- **Bug or unclear behaviour:** open an issue and include your agent (Claude Code, Codex, ...), OS, Python version, the command you ran, and the gate output (the `detail:` and `hint:` lines help most).
- **Security problem:** do not open a public issue. See [SECURITY.md](SECURITY.md).
- **Tested on another agent or on Windows?** Tell us in an issue. The README lists what is tested.

## Change the code

1. Fork, then branch from `main`.
2. Run the tests: `python3 -m unittest discover -s tests` (Python 3.10+, standard library only; the suite takes a couple of minutes).
3. Keep the skills dependency-free. `gate.py` and `landed.py` use only the standard library.
4. If you change gate behaviour or a queue file format, update `skills/jt-work/references/contract.md`, the affected `SKILL.md`, and `CHANGELOG.md`, and add or adjust a test. Then copy that contract and `skills/jt-work/scripts/gate.py` into `jt-setup` and `jt-add-task` so the three copies stay byte-identical. `specdoc.py` and `check.py` live in `skills/jt-spec-ac/scripts/`; copy them (and `references/rules.md` and `references/input.md`) into every spec skill that ships them, and copy `specdoc.py` into `jt-board`. `board.py` lives only in `skills/jt-board/scripts/`. The installer skips a symlink that points outside the skill, so these are real copies. If you change a heading, table column, or marker that `check.py` reads, update the skill that writes it and the fixtures in `evals/files/`.
5. Open a pull request that says what changed and why. CI runs the tests, `bandit`, Agent Skills spec validation, and a SkillSpector scan. Any new SkillSpector suppression in `.skillspector-baseline.yaml` needs a written reason.

Commit messages follow `type(scope): summary` (for example `fix(gate): ...`). When the change has a ticket id, put that id at the end: `feat(booking): add room search API (BOOK-12)`. Copy the id the ticket already has. Do not invent one.
