# Roles and risk

`## Roles` names three people: who approves the spec, who reviews the PR, and who merges. The merger is always a human. `human-only` lists paths or topics an agent must not change on its own. The spec approver records `human-sign-off` on the task. That is the same approval the spec already has. `/jt-work` does not ask again.

`/jt-board` and `/jt-review` stay human-only. Nothing in the gate merges or approves.

`risk:` is `low`, `medium`, or `high`. High means the diff touches a human-only area, auth, a migration, or more lines than `<DIFF_LIMIT>`. High suggests `/ponytail-review`. The suggestion does not run that review by itself, and it does not merge.

Before the draft PR, `/jt-work` composes pstack `/no-comments` so comments that restate the code, and unused code, are cut inside `files:`.
