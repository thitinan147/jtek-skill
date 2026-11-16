# Install before use

Install these on your machine or in the repo before jtek-skill. None replace `gate.py` or a human `/jt-review`. At `/jt-setup`, confirm commands for board slots `TEST_CMD`, `LINT_CMD`, `SECURITY_CMD`, and `VERIFY_CMD` (today the shipped template lists the first two plus `TYPECHECK_CMD`; extend the table when you add security or verify commands). Use one AI reviewer at a time (for example `/interrogate` after the gate passes); do not stack AI reviewers.

## Required

| Tool | Install | JTek step | Why | Slot |
| --- | --- | --- | --- | --- |
| Playwright CLI + skills | `npm install -g @playwright/cli@latest` then `playwright-cli install --skills -g` | `/jt-work` | Agent drives the app (`playwright-cli open … -s=<ticket>` per worktree); gate still runs `npx playwright test` / `toHaveScreenshot` | (agent + `TEST_CMD`) |
| pstack `create-verification-skill` | `npx skills add backnotprop/pstack --skill create-verification-skill` | `/jt-setup` | Project-local verify skill for driving the real surface | — |
| pstack `statechart` | `npx skills add backnotprop/pstack --skill statechart` | `/jt-spec-ac` | Stateful flows: model states and rules before AC freeze | — |
| pstack `no-comments` | `npx skills add backnotprop/pstack --skill no-comments` | `/jt-work` (before PR) | Strip noise before human review | — |
| pstack `interrogate` | `npx skills add backnotprop/pstack --skill interrogate` | after gate passes | Adversarial review; keep only run-proven findings | — |
| pstack `maintain-verification-skill` | `npx skills add backnotprop/pstack --skill maintain-verification-skill` | after large code changes | Re-align verify skill with the app | — |
| mise | `brew install mise` | `/jt-setup` | Pin tool versions; `gate.py detect` can source `TEST_CMD` / `LINT_CMD` from `mise.toml` tasks | `TEST_CMD`, `LINT_CMD` |
| pre-commit (typos, actionlint, zizmor) | `python3 -m pip install pre-commit` then `pre-commit install` | on commit | Catches typos, workflow syntax, and Actions security before the gate | — |
| reviewdog | `go install github.com/reviewdog/reviewdog/cmd/reviewdog@latest` | `/jt-review` | Post CI or lint output on PR lines | — |
| Vitest affected | (Vitest in repo) `vitest --changed` in `TEST_CMD` | `/jt-setup` | Faster feedback on touched files | `TEST_CMD` |
| Jest related | (Jest in repo) `jest --findRelatedTests` in `TEST_CMD` | `/jt-setup` | Run tests tied to the diff | `TEST_CMD` |
| pytest-testmon | `python3 -m pip install pytest-testmon` | `/jt-setup` | Run pytest modules affected by edits | `TEST_CMD` |
| TruffleHog | `brew install trufflehog` | `/jt-setup` | Secret scan on commits or CI | `SECURITY_CMD` |
| Semgrep | `python3 -m pip install semgrep` | `/jt-setup` | Static analysis; gate runs non-empty `LINT_CMD` on Standard tasks | `LINT_CMD` or `SECURITY_CMD` |
| OSV-Scanner | `brew install osv-scanner` or `go install github.com/google/osv-scanner/v2/cmd/osv-scanner@latest` | `/jt-setup` | Dependency CVEs from OSV | `SECURITY_CMD` |
| Knip | `npm install -D knip typescript @types/node` | `/jt-setup` | Dead exports and unused deps | `VERIFY_CMD` |
| commitlint | `npm install -D @commitlint/cli @commitlint/config-conventional` | `/jt-work` | Enforce conventional commits locally | — |
| action-semantic-pull-request | Add `amannn/action-semantic-pull-request@v6` to a workflow | `/jt-review` | Block non-semantic PR titles on GitHub | — |
| release-please | Add `googleapis/release-please-action@v4` to a workflow | after merge | Conventional-commit releases | — |
| Dependabot | Enable in repo **Settings → Code security** | ongoing | Dependency update PRs (human merges) | — |
| GitHub Secret Scanning | Enable **Secret scanning** in **Settings → Code security** | on push | Hosted secret detection | — |

## Recommended skills

| Skill | Install | JTek step | Why |
| --- | --- | --- | --- |
| Matt Pocock `/pr` | `npx skills add mattpocock/skills --skill pr` | `/jt-work` (PR body) | Reviewable PR shape |
| Matt Pocock `/retro` | `npx skills add mattpocock/skills --skill retro` | after `/jt-review` | Improve agent environment from the session |
| ponytail `/ponytail-review` | `npx skills add DietrichGebert/ponytail --skill ponytail-review` | high-risk PRs only | Deep review; not a substitute for human merge |
| superpowers `brainstorming` | `npx skills add obra/superpowers --skill brainstorming` | `/jt-add-task` / early `/jt-work` | Shape the problem before implementation |
| superpowers `systematic-debugging` | `npx skills add obra/superpowers --skill systematic-debugging` | `/jt-work` | Disciplined debug when the gate refuses |
| anthropics `webapp-testing` | `npx skills add anthropics/skills --skill webapp-testing` | `/jt-work` (local web) | Playwright helpers for local apps (`pip install playwright` + `playwright install chromium` in the repo if needed) |

## Optional (when the repo fits)

| Tool | Install | JTek step | Why | Slot |
| --- | --- | --- | --- | --- |
| Testcontainers | `python3 -m pip install "testcontainers[postgres]"` (pick extra) | `/jt-setup` | Real DB/services in tests; needs Docker | `TEST_CMD` |
| Pact | `pip install pact-python` | `/jt-setup` | Consumer-driven contracts across fe/be repos | `TEST_CMD` |
| nektos act | `brew install act` | before push | Run GitHub Actions locally | — |
| Unleash (self-hosted) | Follow https://docs.getunleash.io/ (Docker Compose) | when feature flags land | Toggle features safely | — |