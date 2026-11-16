# jtek-skill

**Let your coding agent draft a spec, work a task queue, and stop at review until a script, not the agent, says the work is ready.**

`jtek-skill` is a set of [Agent Skills](https://agentskills.io/). One group drafts a story into `spec.md` (acceptance criteria and test steps) and leaves every decision with a person. The other runs a task queue in `jt-queue/`: the agent commits on a branch, and a deterministic Python gate ([`gate.py`](skills/jt-work/scripts/gate.py)) checks the diff, tests, and lint and typecheck when the board sets them. Only then does the task move to `review:`. You hold the merge key.

*Constrain the outcome, not the agent. The AI proposes. People decide.*

## Why

- Agents say "done" when they are not. Here "done" is something a script checks.
- You do not script every step. The agent chooses how; the gate checks what came out.
- Spec text is a fact with a source, a proposal, or a question. An approval or a decision signed by an AI fails `check.py`.
- Queue files are plain text under `jt-queue/`. Spec files are plain Markdown. No service and no account. Dependencies are `git` and Python.

## Install

Pick **one** method. Installing both the plugin and the skills CLI gives you every skill twice.

**Any agent (Claude Code, Codex, Cursor, ...)** with [skills.sh](https://skills.sh/thitinan147/jtek-skill):

```bash
# Everything, pinned (recommended)
npx skills add thitinan147/jtek-skill#v24.4.0

# Or follow the default branch
npx skills add thitinan147/jtek-skill
```

Add `-g` to install for all your projects instead of the current one.

**Claude Code plugin** (installs the whole set; commands are also `/jtek:<name>`):

```text
/plugin marketplace add thitinan147/jtek-skill#v24.4.0
/plugin install jtek@jtek-skill
```

Without `#v24.4.0` the marketplace follows the default branch.

### Install what you need

Each skill is a folder of its own. The name is a separate argument, with a space: `--skill jt-help`. (`--skill=jt-help` is ignored by current installers and installs every skill.)

| Skill | Command | Who | Install just this |
|---|---|---|---|
| [`jt-help`](skills/jt-help/SKILL.md) | `/jt-help` | anyone | `npx skills add thitinan147/jtek-skill --skill jt-help` |
| [`jt-spec-split`](skills/jt-spec-split/SKILL.md) | `/jt-spec-split` | **human-only** | `npx skills add thitinan147/jtek-skill --skill jt-spec-split` |
| [`jt-spec-ac`](skills/jt-spec-ac/SKILL.md) | `/jt-spec-ac` | **human-only** | `npx skills add thitinan147/jtek-skill --skill jt-spec-ac` |
| [`jt-spec-handoff`](skills/jt-spec-handoff/SKILL.md) | `/jt-spec-handoff` | **human-only** | `npx skills add thitinan147/jtek-skill --skill jt-spec-handoff` |
| [`jt-board`](skills/jt-board/SKILL.md) | `/jt-board` | **human-only** | `npx skills add thitinan147/jtek-skill --skill jt-board` |
| [`jt-setup`](skills/jt-setup/SKILL.md) | `/jt-setup` | human confirms the commands | `npx skills add thitinan147/jtek-skill --skill jt-setup` |
| [`jt-add-task`](skills/jt-add-task/SKILL.md) | `/jt-add-task` | human approves each task | `npx skills add thitinan147/jtek-skill --skill jt-add-task` |
| [`jt-work`](skills/jt-work/SKILL.md) | `/jt-work` | agent | `npx skills add thitinan147/jtek-skill --skill jt-work` |
| [`jt-review`](skills/jt-review/SKILL.md) | `/jt-review` | **human-only** | `npx skills add thitinan147/jtek-skill --skill jt-review` |

Pin the same way: `npx skills add thitinan147/jtek-skill#v24.4.0 --skill jt-work`.

In Codex the commands are `$jt-help`, `$jt-setup`, and so on.

Then read [SECURITY.md](SECURITY.md). The gate runs your test command, so a human must approve it first. **New here? Read [Getting started](docs/getting-started.md).** Spec drafts: [Spec documents](docs/spec.md).

## Quick start

```text
/jt-help
/jt-setup
/jt-add-task Add rate limiting to POST /api/login
/jt-work
/jt-review
```

A story, before or beside the queue:

```text
/jt-spec-split room-booking
/jt-spec-ac BOOK-12-book-room
/jt-spec-handoff BOOK-12-book-room
/jt-board room-booking
```

## How it works

```text
Spec (human types the command)          Queue
/jt-spec-split   flow → story map        /jt-setup      board.md, human confirms commands
/jt-spec-ac      story, rules, AC        /jt-add-task   brief, then tasks
/jt-spec-handoff test steps              /jt-work       ready tasks, in order
/jt-board        board.html              /jt-review     human: merge / send-back / drop
```

1. **Commit the queue context; keep secrets local.** Commit `jt-queue/board.md`, `brief.md`, `tasks/<id>/task.md`, and `plan.md` (including `## decisions`) so another machine can resume. Leave `lessons.md` uncommitted (notes for this agent, not the task). Leave `.git/jt-queue/` uncommitted: `approved-commands.json` is permission to run shell commands and must not travel in a commit, `logs/` can hold secrets, and `attempts.json` is this machine's round counter. Also leave `.env` files and private keys out. `/jt-work` is one command and has no `--loop` flag. With no id it works every ready task in board order and skips a blocked one. `/jt-work BOOK-12` works only that ticket. Spec files live under `scrum-spec/` (or `docs_root`) and are meant to be committed. The folder name and the marker `<!-- scrum-spec -->` stay, because `check.py` reads them. The commands do not use that word. A human approves the spec once; that covers the tasks derived from it. `/jt-review` is still the only merge.
2. **The gate checks before review.** The agent cannot mark a task `review:` itself. `Quick` tasks need the test command to pass. `Standard` tasks need a diff outside `jt-queue/`, a `plan.md` whose evidence covers every `pass:` line, and a review that cites the latest commit. When the board sets `<LINT_CMD>` or `<TYPECHECK_CMD>`, those must pass too. Size is separate: `small` (no spec; affected tests only when the board says how, otherwise the full suite), `medium` (short spec, full gate), `large` (full spec). The agent sets `size:`; you can override it on the board line. The gate may raise it (`escalate:`) and never lowers it.
3. **You hold the merge key.** Only `/jt-review`, run by a human, can close or send back a task. The spec commands never commit.

| Command | Who | What it does |
|---|---|---|
| [`/jt-help`](skills/jt-help/SKILL.md) | anyone | Lists every command, the order, and which are human-only. |
| [`/jt-spec-split`](skills/jt-spec-split/SKILL.md) | **human-only** | Split a flow into a story map and one folder per confirmed story. |
| [`/jt-spec-ac`](skills/jt-spec-ac/SKILL.md) | **human-only** | Draft story, rules, acceptance criteria, and questions. |
| [`/jt-spec-handoff`](skills/jt-spec-handoff/SKILL.md) | **human-only** | Write test steps once nothing blocks the AC. |
| [`/jt-board`](skills/jt-board/SKILL.md) | **human-only** | Write a FigJam-style `board.html`. |
| [`/jt-setup`](skills/jt-setup/SKILL.md) | human confirms | Write `jt-queue/board.md`. |
| [`/jt-add-task`](skills/jt-add-task/SKILL.md) | spec approval covers derived tasks | Agree the brief, then add tasks. |
| [`/jt-work`](skills/jt-work/SKILL.md) | agent | Work ready tasks in order, or one ticket id. Cannot merge. |
| [`/jt-review`](skills/jt-review/SKILL.md) | **human-only** | Inspect `review:` and write `merge:`, `send-back:`, or `drop:`. |

## Names

A ticket keeps the id it already has. Jira `BOOK-12`, GitHub `#45`, and a Notion id are all fine. The skills require an id on `ticket:` and do not check its shape.

- Commit and pull request title: `type(scope): summary (<ticket-id>)`, for example `feat(booking): add room search API (BOOK-12)`. The type is the task kind (`feat`, `fix`, `refactor`, `test`, `docs`, `chore`, and the other kinds the board already uses). Scope is optional.
- Task branch: `type/<ticket-id>-short-slug`, for example `feat/BOOK-12-room-search` (type and slug are lowercase, with hyphens; the ticket id is copied as written). Legacy `task-<id>-<slug>` still works; the gate prints `branch-deprecated:` when it finds one. Quote ticket ids in the shell when needed, for example `/jt-work '#45'`.

## Install before use

[jtek-skill](#install) above is only the skills. The tables below are a fixed checklist (no machine scanning): copy-paste install commands, the jtek step each tool plugs into, and the board slot when the gate runs the command. None of these replace `gate.py` or a human `/jt-review`. At [`/jt-setup`](skills/jt-setup/SKILL.md), confirm `TEST_CMD`, `AFFECTED_TEST_CMD`, `LINT_CMD`, `SECURITY_CMD`, and `VERIFY_CMD` on `board.md` (the shipped template includes the first two plus `TYPECHECK_CMD`). Use **one** AI reviewer at a time (for example pstack `/interrogate` after the gate passes); do not stack AI reviewers.

The same list ships in [`skills/jt-help/references/install-before-use.md`](skills/jt-help/references/install-before-use.md) for `/jt-help`. If a required **skill** is not installed, jt- commands still run using the one-line fallback in each `SKILL.md` (not the old long prompts).

### Required

| Tool | Install | JTek step | Why | Board slot |
| --- | --- | --- | --- | --- |
| [superpowers `executing-plans`](https://www.skills.sh/obra/superpowers/executing-plans) | `npx skills add obra/superpowers --skill executing-plans` | [`/jt-work`](skills/jt-work/SKILL.md) | Plan then execute Standard tasks; gate evidence unchanged | — |
| [superpowers `test-driven-development`](https://www.skills.sh/obra/superpowers/test-driven-development) | `npx skills add obra/superpowers --skill test-driven-development` | [`/jt-work`](skills/jt-work/SKILL.md) | Red-green-refactor before `reach-review` | — |
| [superpowers `brainstorming`](https://www.skills.sh/obra/superpowers/brainstorming) | `npx skills add obra/superpowers --skill brainstorming` | [`/jt-spec-ac`](skills/jt-spec-ac/SKILL.md) | When the idea is unclear before drafting AC | — |
| [grill-me](https://www.skills.sh/mattpocock/grill-me) | `npx skills add mattpocock/skills --skill grill-me` | [`/jt-spec-ac`](skills/jt-spec-ac/SKILL.md) | Questions that unblock AC (`check.py` outcomes unchanged) | — |
| [Playwright CLI](https://playwright.dev/docs/getting-started-cli) + [skills](https://playwright.dev/agent-cli/skills) | `npm install -g @playwright/cli@latest` then `playwright-cli install --skills -g` | [`/jt-work`](skills/jt-work/SKILL.md) | Agent clicks through AC (`playwright-cli open … -s=<ticket>` per worktree); gate still runs `npx playwright test` / `toHaveScreenshot` | agent + `TEST_CMD` |
| pstack [`create-verification-skill`](https://www.skills.sh/backnotprop/pstack/create-verification-skill) | `npx skills add backnotprop/pstack --skill create-verification-skill` | [`/jt-setup`](skills/jt-setup/SKILL.md) | Project-local verify skill for the real user surface | — |
| pstack [`statechart`](https://www.skills.sh/backnotprop/pstack/statechart) | `npx skills add backnotprop/pstack --skill statechart` | [`/jt-spec-ac`](skills/jt-spec-ac/SKILL.md) | Stateful systems: model states before AC freeze | — |
| pstack [`no-comments`](https://www.skills.sh/backnotprop/pstack/no-comments) | `npx skills add backnotprop/pstack --skill no-comments` | [`/jt-work`](skills/jt-work/SKILL.md) (before PR) | Strip comment noise before review | — |
| pstack [`interrogate`](https://www.skills.sh/backnotprop/pstack/interrogate) | `npx skills add backnotprop/pstack --skill interrogate` | after gate passes | Adversarial review; keep only run-proven findings | — |
| pstack [`maintain-verification-skill`](https://www.skills.sh/backnotprop/pstack/maintain-verification-skill) | `npx skills add backnotprop/pstack --skill maintain-verification-skill` | after large code changes | Re-align verify skill with the app | — |
| [mise](https://mise.jdx.dev/installing-mise.html) | `curl -fsSL https://mise.run \| sh` | [`/jt-setup`](skills/jt-setup/SKILL.md) | Pin tool versions; detect can source commands from `mise.toml` | `TEST_CMD`, `LINT_CMD` |
| [pre-commit](https://pre-commit.com/#install) + [typos](https://github.com/crate-ci/typos) / [actionlint](https://github.com/rhysd/actionlint) / [zizmor](https://docs.zizmor.sh/integrations/) | `python3 -m pip install pre-commit` then `pre-commit install` (hooks in `.pre-commit-config.yaml`) | on `git commit` | Typos, workflow lint, Actions security before the gate | — |
| [reviewdog](https://github.com/reviewdog/reviewdog#installation) | `go install github.com/reviewdog/reviewdog/cmd/reviewdog@latest` | [`/jt-review`](skills/jt-review/SKILL.md) | Post lint or check annotations on PR lines | — |
| Vitest affected | `npx vitest --changed` in `AFFECTED_TEST_CMD` (requires Vitest in the repo) | [`/jt-setup`](skills/jt-setup/SKILL.md) | Narrow tests on `small` tasks | `AFFECTED_TEST_CMD` |
| Jest related | `npx jest --findRelatedTests {files}` in `AFFECTED_TEST_CMD` (requires Jest in the repo) | [`/jt-setup`](skills/jt-setup/SKILL.md) | Related tests on `small` tasks | `AFFECTED_TEST_CMD` |
| [pytest-testmon](https://pypi.org/project/pytest-testmon/) | `pytest --testmon` in `AFFECTED_TEST_CMD` after `pip install pytest-testmon` | [`/jt-setup`](skills/jt-setup/SKILL.md) | Affected pytest modules on `small` tasks | `AFFECTED_TEST_CMD` |
| [TruffleHog](https://github.com/trufflesecurity/trufflehog/blob/main/README.md#-installation) | `curl -sSfL https://raw.githubusercontent.com/trufflesecurity/trufflehog/main/scripts/install.sh \| sh -s -- -b /usr/local/bin` | [`/jt-setup`](skills/jt-setup/SKILL.md) | Secret scan on commits or CI | `SECURITY_CMD` |
| [Semgrep](https://docs.semgrep.dev/getting-started/cli) | `python3 -m pip install semgrep` | [`/jt-setup`](skills/jt-setup/SKILL.md) | Static analysis; gate runs non-empty `LINT_CMD` on Standard tasks | `LINT_CMD` or `SECURITY_CMD` |
| [OSV-Scanner](https://google.github.io/osv-scanner/installation/) | `brew install osv-scanner` or `go install github.com/google/osv-scanner/v2/cmd/osv-scanner@latest` | [`/jt-setup`](skills/jt-setup/SKILL.md) | Dependency CVEs from OSV | `SECURITY_CMD` |
| [Knip](https://knip.dev/overview/getting-started) | `npm install -D knip typescript @types/node` | [`/jt-setup`](skills/jt-setup/SKILL.md) | Unused exports and dependencies | `VERIFY_CMD` |
| [commitlint](https://commitlint.js.org/guides/getting-started) | `npm install -D @commitlint/cli @commitlint/config-conventional` | [`/jt-work`](skills/jt-work/SKILL.md) | Conventional commit messages locally | — |
| [action-semantic-pull-request](https://github.com/amannn/action-semantic-pull-request#installation) | Add `uses: amannn/action-semantic-pull-request@v6` to a workflow | [`/jt-review`](skills/jt-review/SKILL.md) | Enforce semantic PR titles on GitHub | — |
| [release-please](https://github.com/googleapis/release-please-action#basic-configuration) | Add `uses: googleapis/release-please-action@v4` to a workflow | after merge | Versioned releases from conventional commits | — |
| [Dependabot](https://docs.github.com/en/code-security/dependabot) | Enable in repo **Settings → Code security** | ongoing | Dependency update PRs (human merges) | — |
| [GitHub Secret Scanning](https://docs.github.com/en/code-security/secret-scanning) | Enable in **Settings → Code security** | on push | Hosted secret detection | — |

### Recommended skills

| Skill | Install | JTek step | Why |
| --- | --- | --- | --- |
| Matt Pocock `/pr` ([repo](https://github.com/mattpocock/skills)) | `npx skills add mattpocock/skills --skill pr` | [`/jt-work`](skills/jt-work/SKILL.md) (PR body) | Reviewable PR shape |
| Matt Pocock `/retro` ([repo](https://github.com/mattpocock/skills)) | `npx skills add mattpocock/skills --skill retro` | after [`/jt-review`](skills/jt-review/SKILL.md) | Retrospective on the agent environment |
| [ponytail `/ponytail-review`](https://github.com/DietrichGebert/ponytail) | `npx skills add DietrichGebert/ponytail --skill ponytail-review` | high-risk PRs only | Extra review pass; human still merges |
| [Matt Pocock `handoff`](https://www.skills.sh/mattpocock/handoff) | `npx skills add mattpocock/skills --skill handoff` | [`/jt-spec-handoff`](skills/jt-spec-handoff/SKILL.md) | Test steps without duplicating AC text |
| [superpowers `systematic-debugging`](https://www.skills.sh/obra/superpowers/systematic-debugging) | `npx skills add obra/superpowers --skill systematic-debugging` | [`/jt-work`](skills/jt-work/SKILL.md) | Debug when the gate refuses |
| [anthropics `webapp-testing`](https://github.com/anthropics/skills) | `npx skills add anthropics/skills --skill webapp-testing` | [`/jt-work`](skills/jt-work/SKILL.md) (local web) | Playwright helpers (`pip install playwright` + `playwright install chromium` when the skill runs Python scripts) |

### Optional (when the repo fits)

| Tool | Install | JTek step | Why | Board slot |
| --- | --- | --- | --- | --- |
| [Testcontainers](https://testcontainers-python.readthedocs.io/en/latest/index.html) | `python3 -m pip install "testcontainers[postgres]"` (pick an extra) | [`/jt-setup`](skills/jt-setup/SKILL.md) | Real DB or services in tests (needs Docker) | `TEST_CMD` |
| [Pact Python](https://docs.pact.io/implementation_guides/python/readme) | `pip install pact-python` | [`/jt-setup`](skills/jt-setup/SKILL.md) | Contracts across frontend and backend repos | `TEST_CMD` |
| [nektos act](https://nektosact.com/installation/) | `curl --proto '=https' --tlsv1.2 -sSf https://raw.githubusercontent.com/nektos/act/master/install.sh \| sudo bash` | before push | Run GitHub Actions locally | — |
| [Unleash](https://docs.getunleash.io/) self-hosted | Follow Unleash Docker docs | when feature flags land | Feature toggles in production | — |

## Migration from `/scrum-spec` and the old queue names

v24 is breaking for command names. Queue files and spec files do not need a rewrite. The marker `<!-- scrum-spec -->`, `scrum-spec/config.md`, and every `check.py` rule are unchanged. `gate.py` still checks the same things; `next` prints the new command for each action.

| Old | New |
|---|---|
| `/scrum-spec` or `/scrum-spec help` | `/jt-help` |
| `/scrum-spec split` | `/jt-spec-split` |
| `/scrum-spec ac` | `/jt-spec-ac` |
| `/scrum-spec handoff` | `/jt-spec-handoff` |
| `/scrum-spec board` | `/jt-board` |
| `/jt-work-queue` when there is no board | `/jt-setup` |
| `/jt-work-queue` to agree the brief or add a task | `/jt-add-task` |
| `/jt-work-queue` to implement | `/jt-work` |
| `/jt-review-work` | `/jt-review` |
| `/jtek:jt-work-queue`, `/jtek:jt-review-work` | `/jtek:jt-setup`, `/jtek:jt-add-task`, `/jtek:jt-work`, `/jtek:jt-review` |

The gate's `brief` and `add-task` actions both name `/jt-add-task`. There is no separate brief command. Details: [MIGRATING.md](MIGRATING.md).

## Documentation

- [Getting started](docs/getting-started.md): one queue round, with the gate's output
- [Spec documents](docs/spec.md): story map, acceptance criteria, test steps, the checker
- [Usage guide](docs/usage.md): priorities, task kinds, two repos
- [File and gate contract](skills/jt-work/references/contract.md)
- [Security and trust model](SECURITY.md)
- [Changelog](CHANGELOG.md) and [migrating](MIGRATING.md)

## Platform support

| | Status |
|---|---|
| macOS, Linux | Supported. CI runs the tests on Ubuntu with Python 3.10 and 3.13. |
| Windows | **Not supported yet.** The gate uses POSIX process groups (`os.killpg`) and `fcntl`. Use WSL. |
| Claude Code | Install from a release tag with skills.sh, or load the plugin. |
| Codex, Cursor, Grok Build, Antigravity | Follows the Agent Skills format. Reports are welcome. |

Needs `git` and Python 3.10 or later (standard library only). The GitHub CLI (`gh`) is optional. Large PDFs need poppler (`poppler-utils`).

## Security

`jtek-skill` runs shell commands on your machine (your test, lint, and typecheck commands, and any task `start`/`click`). It is not a sandbox. A human must approve those exact commands with `gate.py approve-commands` first. `check.py` only reads files. `board.py` writes `board.html`, and that page loads Google Fonts when opened. See [SECURITY.md](SECURITY.md).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Run the tests with:

```bash
python3 -m unittest discover -s tests
```

## License

[MIT](LICENSE)
