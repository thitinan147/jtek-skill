# Install before use

Install these on your machine or in the repo before jtek-skill. None replace `gate.py` or a human `/jt-review`. At `/jt-setup`, confirm `TEST_CMD`, `AFFECTED_TEST_CMD`, `LINT_CMD`, `SECURITY_CMD`, and `VERIFY_CMD` on `board.md`. The same command writes `AGENTS.md` (those commands, the flow spec -> tasks -> work -> gate -> human merge, the house rules, and where `jt-queue/` files live). `CLAUDE.md` is `@AGENTS.md` only. An existing `AGENTS.md`, `CLAUDE.md`, `.cursor/rules`, or board is merged, not replaced. After the gate passes, `/jt-work` invokes one fresh-context reviewer for medium and large: `/interrogate` when installed, otherwise `/pr`, otherwise `/ponytail-review` when the task is high-risk. Do not stack AI reviewers. The AI does not approve or merge.

Copy-paste install commands live in the repo README; here, the Install column is the official page to follow. If a required **skill** is not installed, jt- commands still run: each `SKILL.md` gives a one-line fallback, not the old long prompts.

## Required

| Tool | Official install | JTek step | Why | Slot |
| --- | --- | --- | --- | --- |
| superpowers executing-plans | https://www.skills.sh/obra/superpowers/executing-plans | `/jt-work` | Plan then execute Standard tasks | — |
| superpowers test-driven-development | https://www.skills.sh/obra/superpowers/test-driven-development | `/jt-work` | Red-green-refactor before `reach-review` | — |
| superpowers brainstorming | https://www.skills.sh/obra/superpowers/brainstorming | `/jt-spec-ac` | When the idea is unclear before drafting AC | — |
| grill-me | https://www.skills.sh/mattpocock/skills/grill-me | `/jt-spec-ac` | Questions that unblock AC; `check.py` outcomes unchanged | — |
| Playwright CLI + skills | https://playwright.dev/docs/getting-started-cli and https://playwright.dev/agent-cli/skills | `/jt-work` | Agent drives the app with playwright-cli -s=<ticket-id> (one session per worktree; not Playwright MCP), reads console and network errors, and lists a screenshot per AC id. The gate runs npx playwright test / toHaveScreenshot and does not update snapshots in that task. Install: npm install -g @playwright/cli@latest then playwright-cli install --skills | VERIFY_CMD |
| pstack create-verification-skill | https://www.skills.sh/backnotprop/pstack/create-verification-skill | `/jt-setup` | Project-local verify skill for the real surface | — |
| pstack statechart | https://www.skills.sh/backnotprop/pstack/statechart | `/jt-spec-ac` | Stateful flows: model states and rules before AC freeze | — |
| pstack no-comments | https://www.skills.sh/backnotprop/pstack/no-comments | `/jt-work` (before PR) | Strip noise before human review | — |
| pstack interrogate | https://www.skills.sh/backnotprop/pstack/interrogate | `/jt-work` after the gate passes | The one fresh-context reviewer when this skill is installed | — |
| pstack maintain-verification-skill | https://www.skills.sh/backnotprop/pstack/maintain-verification-skill | after large code changes | Re-align verify skill with the app | — |
| mise | https://mise.jdx.dev/installing-mise.html | `/jt-setup` | Pin tool versions; `gate.py detect` can source commands from `mise.toml` | `TEST_CMD`, `LINT_CMD` |
| pre-commit, typos, actionlint, zizmor | https://pre-commit.com/#install ; https://github.com/crate-ci/typos ; https://github.com/rhysd/actionlint ; https://docs.zizmor.sh/integrations/ | on commit | `/jt-setup` proposes a pinned `.pre-commit-config.yaml` and waits. Typos, workflow syntax, and Actions security run before the gate. The gate does not fail if pre-commit is absent | — |
| reviewdog | https://github.com/reviewdog/reviewdog#installation | `/jt-review` | Post CI or lint output on PR lines | — |
| Vitest affected | https://vitest.dev/guide/cli.html | `/jt-setup` | Example: `npx vitest --changed` in `AFFECTED_TEST_CMD` for `small` tasks | `AFFECTED_TEST_CMD` |
| Jest related | https://jestjs.io/docs/cli | `/jt-setup` | Example: `npx jest --findRelatedTests {files}` in `AFFECTED_TEST_CMD` | `AFFECTED_TEST_CMD` |
| pytest-testmon | https://pypi.org/project/pytest-testmon/ | `/jt-setup` | Example: `pytest --testmon` in `AFFECTED_TEST_CMD` | `AFFECTED_TEST_CMD` |
| TruffleHog | https://github.com/trufflesecurity/trufflehog/blob/main/README.md#-installation | `/jt-setup` | Secret scan. The gate runs `SECURITY_CMD` when that program is installed; otherwise the built-in check. It never prints the value | `SECURITY_CMD` |
| Semgrep | https://docs.semgrep.dev/getting-started/cli | `/jt-setup` | Static analysis; gate runs non-empty `LINT_CMD` on Standard tasks | `LINT_CMD` or `SECURITY_CMD` |
| OSV-Scanner | https://google.github.io/osv-scanner/installation/ | `/jt-setup` | Dependency CVEs from OSV | `SECURITY_CMD` |
| Knip | https://knip.dev/overview/getting-started | `/jt-setup` | Dead exports and unused deps. The gate runs `VERIFY_CMD` after tests when the cell is set | `VERIFY_CMD` |
| commitlint | https://commitlint.js.org/guides/getting-started | `/jt-work` | Conventional commit messages locally | — |
| action-semantic-pull-request | https://github.com/amannn/action-semantic-pull-request#installation | `/jt-review` | Enforce semantic PR titles on GitHub | — |
| release-please | https://github.com/googleapis/release-please-action#basic-configuration | after merge | Conventional-commit releases | — |
| Dependabot | https://docs.github.com/en/code-security/dependabot | ongoing | Dependency update PRs (human merges) | — |
| GitHub Secret Scanning | https://docs.github.com/en/code-security/secret-scanning | on push | Hosted secret detection | — |

## Recommended skills

| Skill | Official install | JTek step | Why |
| --- | --- | --- | --- |
| Matt Pocock /pr | https://www.skills.sh/mattpocock/skills/pr | `/jt-work` when `/interrogate` is not installed | The one fresh-context reviewer in that case; also shapes the PR |
| Matt Pocock handoff | https://www.skills.sh/mattpocock/skills/handoff | `/jt-spec-handoff` | Test steps without duplicating AC text |
| Matt Pocock /retro | https://www.skills.sh/mattpocock/skills/retro | after `/jt-review` | Improve agent environment from the session |
| ponytail /ponytail-review | https://github.com/DietrichGebert/ponytail | `/jt-work` only when the task is high-risk and neither reviewer above is installed | The one reviewer in that case; not a substitute for human merge |
| superpowers systematic-debugging | https://www.skills.sh/obra/superpowers/systematic-debugging | `/jt-work` | Disciplined debug when the gate refuses |
| anthropics webapp-testing | https://github.com/anthropics/skills (skill webapp-testing) | `/jt-work` (local web) | Playwright helpers; see skill for Python deps |

## Optional (when the repo fits)

| Tool | Official install | JTek step | Why | Slot |
| --- | --- | --- | --- | --- |
| Testcontainers | https://testcontainers-python.readthedocs.io/en/latest/index.html | `/jt-setup` | Real DB or services in tests (needs Docker) | `TEST_CMD` |
| Pact | https://docs.pact.io/implementation_guides/python/readme | `/jt-setup` | Contracts across frontend and backend repos | `TEST_CMD` |
| nektos act | https://nektosact.com/installation/ | before push | Run GitHub Actions locally | — |
| Unleash (self-hosted) | https://docs.getunleash.io/ | when feature flags land | Feature toggles in production | — |