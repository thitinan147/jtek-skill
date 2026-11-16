# Install before use

Install these on your machine or in the repo before jtek-skill. None replace `gate.py` or a human `/jt-review`. At `/jt-setup`, confirm `TEST_CMD`, `AFFECTED_TEST_CMD`, `LINT_CMD`, `SECURITY_CMD`, and `VERIFY_CMD` on `board.md`. Use one AI reviewer at a time (for example `/interrogate` after the gate passes); do not stack AI reviewers.

Copy-paste install commands live in the repo README; here, the Install column is the official page to follow.

## Required

| Tool | Official install | JTek step | Why | Slot |
| --- | --- | --- | --- | --- |
| Playwright CLI + skills | https://playwright.dev/docs/getting-started-cli and https://playwright.dev/agent-cli/skills | `/jt-work` | Agent drives the app (`playwright-cli open … -s=<ticket>` per worktree); gate still runs `npx playwright test` / `toHaveScreenshot` | (agent + `TEST_CMD`) |
| pstack create-verification-skill | https://www.skills.sh/backnotprop/pstack/create-verification-skill | `/jt-setup` | Project-local verify skill for the real surface | — |
| pstack statechart | https://www.skills.sh/backnotprop/pstack/statechart | `/jt-spec-ac` | Stateful flows: model states and rules before AC freeze | — |
| pstack no-comments | https://www.skills.sh/backnotprop/pstack/no-comments | `/jt-work` (before PR) | Strip noise before human review | — |
| pstack interrogate | https://www.skills.sh/backnotprop/pstack/interrogate | after gate passes | Adversarial review; keep only run-proven findings | — |
| pstack maintain-verification-skill | https://www.skills.sh/backnotprop/pstack/maintain-verification-skill | after large code changes | Re-align verify skill with the app | — |
| mise | https://mise.jdx.dev/installing-mise.html | `/jt-setup` | Pin tool versions; `gate.py detect` can source commands from `mise.toml` | `TEST_CMD`, `LINT_CMD` |
| pre-commit, typos, actionlint, zizmor | https://pre-commit.com/#install ; https://github.com/crate-ci/typos ; https://github.com/rhysd/actionlint ; https://docs.zizmor.sh/integrations/ | on commit | Typos, workflow syntax, Actions security before the gate | — |
| reviewdog | https://github.com/reviewdog/reviewdog#installation | `/jt-review` | Post CI or lint output on PR lines | — |
| Vitest affected | https://vitest.dev/guide/cli.html | `/jt-setup` | Example: `npx vitest --changed` in `AFFECTED_TEST_CMD` for `small` tasks | `AFFECTED_TEST_CMD` |
| Jest related | https://jestjs.io/docs/cli | `/jt-setup` | Example: `npx jest --findRelatedTests {files}` in `AFFECTED_TEST_CMD` | `AFFECTED_TEST_CMD` |
| pytest-testmon | https://pypi.org/project/pytest-testmon/ | `/jt-setup` | Example: `pytest --testmon` in `AFFECTED_TEST_CMD` | `AFFECTED_TEST_CMD` |
| TruffleHog | https://github.com/trufflesecurity/trufflehog/blob/main/README.md#-installation | `/jt-setup` | Secret scan on commits or CI | `SECURITY_CMD` |
| Semgrep | https://docs.semgrep.dev/getting-started/cli | `/jt-setup` | Static analysis; gate runs non-empty `LINT_CMD` on Standard tasks | `LINT_CMD` or `SECURITY_CMD` |
| OSV-Scanner | https://google.github.io/osv-scanner/installation/ | `/jt-setup` | Dependency CVEs from OSV | `SECURITY_CMD` |
| Knip | https://knip.dev/overview/getting-started | `/jt-setup` | Dead exports and unused deps | `VERIFY_CMD` |
| commitlint | https://commitlint.js.org/guides/getting-started | `/jt-work` | Conventional commit messages locally | — |
| action-semantic-pull-request | https://github.com/amannn/action-semantic-pull-request#installation | `/jt-review` | Enforce semantic PR titles on GitHub | — |
| release-please | https://github.com/googleapis/release-please-action#basic-configuration | after merge | Conventional-commit releases | — |
| Dependabot | https://docs.github.com/en/code-security/dependabot | ongoing | Dependency update PRs (human merges) | — |
| GitHub Secret Scanning | https://docs.github.com/en/code-security/secret-scanning | on push | Hosted secret detection | — |

## Recommended skills

| Skill | Official install | JTek step | Why |
| --- | --- | --- | --- |
| Matt Pocock /pr | https://www.skills.sh/mattpocock/skills/pr | `/jt-work` (PR body) | Reviewable PR shape |
| Matt Pocock /retro | https://www.skills.sh/mattpocock/skills/retro | after `/jt-review` | Improve agent environment from the session |
| ponytail /ponytail-review | https://github.com/DietrichGebert/ponytail | high-risk PRs only | Deep review; not a substitute for human merge |
| superpowers brainstorming | https://www.skills.sh/obra/superpowers/brainstorming | `/jt-add-task` / early `/jt-work` | Shape the problem before implementation |
| superpowers systematic-debugging | https://www.skills.sh/obra/superpowers/systematic-debugging | `/jt-work` | Disciplined debug when the gate refuses |
| anthropics webapp-testing | https://github.com/anthropics/skills (skill webapp-testing) | `/jt-work` (local web) | Playwright helpers; see skill for Python deps |

## Optional (when the repo fits)

| Tool | Official install | JTek step | Why | Slot |
| --- | --- | --- | --- | --- |
| Testcontainers | https://testcontainers-python.readthedocs.io/en/latest/index.html | `/jt-setup` | Real DB or services in tests (needs Docker) | `TEST_CMD` |
| Pact | https://docs.pact.io/implementation_guides/python/readme | `/jt-setup` | Contracts across frontend and backend repos | `TEST_CMD` |
| nektos act | https://nektosact.com/installation/ | before push | Run GitHub Actions locally | — |
| Unleash (self-hosted) | https://docs.getunleash.io/ | when feature flags land | Feature toggles in production | — |