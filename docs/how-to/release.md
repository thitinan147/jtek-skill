# Release titles

`gate.py title --text '<title>'` accepts `type(scope): summary` and rejects anything else. Scope may be omitted. The ticket id stays in the summary. This check is not a CI gate.

`/jt-setup` can show two templates the human copies if they want them:

- `skills/jt-setup/assets/commitlint.config.cjs`
- `skills/jt-setup/assets/release-please-config.json`

A human merges. After that merge, release-please can open the release PR. The agent does not merge, and this repo does not require that workflow.
