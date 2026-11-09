# jtek-skill (v21)

***Constrain the outcome, not the agent.***

`jtek-skill` is an outcome-gated work queue for coding agents in a single Git repository. Instead of scripting every step the agent must follow, a deterministic Python gate ([`skills/jt-work-queue/scripts/gate.py`](skills/jt-work-queue/scripts/gate.py)) verifies the resulting diff, test execution, and review evidence before work can enter `review:`.

Designed for **Claude Code**, **Codex**, **Cursor**, **Grok Build**, and **Antigravity**.

## Install

```bash
# Recommended: pin a release so later changes cannot reach you unreviewed
npx skills add thitinan147/jtek-skill#v21.0.0 -g

# Or follow the default branch (latest, unpinned)
npx skills add thitinan147/jtek-skill -g
```

After installing, read [SECURITY.md](SECURITY.md): the gate runs your test command, so a human must approve it first.

## How It Works

```text
  Human + Agent (/jt-work-queue)                        Human Only (/jt-review-work)
┌────────────────────────────────────────────────────┐  ┌──────────────────────────────┐
│ 1. setup     Create card-loop/board.md on <queue>  │  │ Inspect diff, test evidence, │
│ 2. brief     Align on round scope in brief.md      │  │ scope warnings, and UI shots │
│ 3. add-card  Draft backlog/<id>.md & queue on board│  │                              │
│ 4. do-work   Branch work/<id> + git worktree       ├──►  • merge: <sha>  (land work) │
│              Run Quick / Standard verification     │  │  • send-back:    (fix & redo)│
│              Verify gate → mark review:            │◄──  • drop: <why>   (cancel)    │
└────────────────────────────────────────────────────┘  └──────────────────────────────┘
```

1. **Queue lives on `<queue>`, code lives on `work/<id>`:** Planning files stay cleanly separated from implementation branches using isolated Git worktrees (`.worktrees/work-<id>`).
2. **Deterministic gate before review:** The agent cannot mark a card `review:` on its own. `gate.py verify --id <id>` checks that commits exist, `plan.md` is complete, the test command actually ran and passed on the current `HEAD` SHA, and `Standard` tier reviews (`diff-review.md`, `test-quality.md`, `verify.md`, plus `screen.md` when `screen: yes`) are Recorded.
3. **Human holds the merge key:** `/jt-work-queue` is forbidden from merging into `<queue>` or marking `merge:`. Only a human invoking `/jt-review-work` can close or send back cards.

## Two Commands

| Command | Who Invokes It | Purpose |
|---|---|---|
| [`/jt-work-queue`](skills/jt-work-queue/SKILL.md) | Human or Agent | Set up `card-loop/board.md`, capture a round brief, draft and add cards, pick the next ready card, implement with adaptive verification (`Quick` / `Standard`), and hand off to `review:`. Cannot merge. |
| [`/jt-review-work`](skills/jt-review-work/SKILL.md) | **Human only** | Read the queue, surface cards whose branches have already landed via [`skills/jt-review-work/scripts/landed.py`](skills/jt-review-work/scripts/landed.py), inspect `review:` evidence (`(<kind>)`, files touched outside `files:`, non-whitespace diffs on `style` cards), and mark `merge:`, `send-back:`, `drop:`, or move board lines. |

*(In Codex, use `$jt-work-queue` and `$jt-review-work`.)*

## Day-to-Day Usage

### 1. Start a project or a new round (`setup` → `brief` → `add-card`)
Run `/jt-work-queue` in any Git repository:

```text
/jt-work-queue
```

- **No `card-loop/board.md` yet (`setup`):** The agent inspects your repo (`package.json`, `pyproject.toml`, `Makefile`, etc.), proposes `<BASE>`, `<QUEUE>`, `<TEST_CMD>`, and `<REPO_SKILLS>`, waits for your approval, and creates `card-loop/board.md` from [`skills/jt-work-queue/assets/board.template.md`](skills/jt-work-queue/assets/board.template.md).
- **Empty board and no `card-loop/brief.md` (`brief`):** The agent interviews you to capture the goal and scope of the current round in `card-loop/brief.md`.
- **Brief ready (`add-card`):** The agent drafts cards from [`skills/jt-work-queue/assets/card.template.md`](skills/jt-work-queue/assets/card.template.md) and adds them to `card-loop/board.md` after your approval.

### 2. Add one or multiple cards at once
Pass your task directly to `/jt-work-queue`:

```text
# Add a single card
/jt-work-queue Add rate limiting to POST /api/login

# Break a feature into multiple sequential cards
/jt-work-queue Break user authentication into 3 cards:
1. Database migration and User model (first)
2. POST /api/login and session middleware (main, depends on 001)
3. Login form UI and E2E check (main, depends on 002, screen: yes)
```

- **Priority sections:** Place urgent cards under `## first`, normal work under `## main`, and deferred ideas under `## later`.
- **Dependencies (`depends:`):** Set `depends: 001` in `card-loop/backlog/002.md` so card `002` waits until `001` is marked `- [x] **001** ... merge:`.
- **Card kinds (`<kind>`):** Every card declares `(feature)`, `(bug)`, `(refactor)`, `(perf)`, `(security)`, or `(style)`.
- **Verification tiers:**
  - **`Quick` tier:** Auto-selected for small changes (≤ 2 files in `files:`, `screen: no`, and kind is `style`/`bug`/`refactor`/`perf`). Requires passing tests + `plan.md`.
  - **`Standard` tier:** Required for `feature`, `security`, `screen: yes`, or ≥ 3 files. Adds independent subagent diff review, test-quality audit (`PASS` + `assertions` + `independent-oracle`), and acceptance walk (`verify.md` from [`skills/jt-work-queue/assets/plan.template.md`](skills/jt-work-queue/assets/plan.template.md)).

### 3. Work the queue (`do-work`)
Each invocation of `/jt-work-queue` picks the next ready card (`send-back:` first, then `doing:`, then the first unblocked card in `first` → `main` → `later`):

```text
/jt-work-queue
```

Before the gate runs `<TEST_CMD>` (or any card `start:` / `click:` command) for the first time, a human must approve the exact command strings on the console:

```bash
python3 skills/jt-work-queue/scripts/gate.py approve-commands --id 001
```

Once implemented and verified by `gate.py verify --id 001`, the card is marked `review:` on `card-loop/board.md` (and a draft PR is opened if an `origin` remote exists).

### 4. Review and land (`review:` → `merge:` / `send-back:` / `drop:`)
When one or more cards reach `review:`, the human runs:

```text
/jt-review-work
```

Or to inspect a specific card directly:

```text
/jt-review-work 001
```

`/jt-review-work` summarizes the board, flags any out-of-scope file edits or `style` cards with non-whitespace changes, checks if any branches have already landed on `<base>`/`<queue>`, and asks whether to:
- **`merge:`** — Merge `work/<id>` (or squash-merge the PR), record `- [x] **<id>** ... merge: <sha>`, and clean up the worktree.
- **`send-back:`** — Write the human's feedback to `card-loop/work/<id>/send-back.md` and return the card to the top of the work queue.
- **`drop: <reason>`** — Cancel the card and clean up its worktree.

## Repository Artifacts (`card-loop/`)

See [`skills/jt-work-queue/references/contract.md`](skills/jt-work-queue/references/contract.md) for the complete file and gate contract:

```text
card-loop/
├── board.md                 # Queue configuration (base, queue, test, skills) + card list
├── brief.md                 # Round brief agreed with the human before drafting cards
├── backlog/
│   └── 001.md               # Card spec: kind, tier, depends, do, out, files, pass, screen
└── work/
    └── 001/
        ├── plan.md          # Goal, Steps, Files, Pass Mapping (copied from backlog on start)
        ├── test.log         # Output + exit code + HEAD SHA from gate.py run-tests
        ├── diff-review.md   # Subagent code review (Standard tier)
        ├── test-quality.md  # Test oracle & assertion audit (Standard tier)
        ├── verify.md        # Pass criteria walk (Standard tier)
        ├── screen.md        # Headless browser & console/pageerror evidence (when screen: yes)
        └── send-back.md     # Human review feedback when sent back
```

## Security

`jtek-skill` runs shell commands (your test command and any card `start`/`click`) on your machine; it is not a sandbox. Before the gate runs them, a human must review and approve them with `gate.py approve-commands --id <id>`, and the gate refuses if they change afterwards. Read [SECURITY.md](SECURITY.md) for the full trust model, what leaves your machine (a draft PR push when a remote exists), and how to report a vulnerability.

<details>
<summary><strong>Migrating from v20 to v21</strong></summary>

### 1. Command Mapping (13 v20 skills → 2 v21 skills)

| v20 Command / Skill | v21 Replacement |
|---|---|
| `/jt-new-board` | `/jt-work-queue` (auto-detects when `card-loop/board.md` is missing) |
| `/jt-find-skills` | `/jt-work-queue` (proposes `<REPO_SKILLS>` during board setup) |
| `/jt-ask-brief` | `/jt-work-queue` (runs when queue is empty and no brief exists) |
| `/jt-new-card` | `/jt-work-queue <task>` |
| `/jt-next-step` | `/jt-work-queue` |
| `/jt-do-work` | `/jt-work-queue` |
| `jt-card-gate` | Merged into [`skills/jt-work-queue/references/contract.md`](skills/jt-work-queue/references/contract.md) |
| `/jt-read-board` | `/jt-review-work` |
| `/jt-open-work` | `/jt-review-work <id>` |
| `/jt-send-back` | `/jt-review-work` (`send-back:`) |
| `/jt-merge` | `/jt-review-work` (`merge:`) |
| `/jt-drop-card` | `/jt-review-work` (`drop: <reason>`) |
| `/jt-move-card` | `/jt-review-work` (move line between `first`, `main`, `later`, `closed`) |

### 2. Migrating `card-loop/board.md`

- **`complete:` status (parent-child cards removed):** v21 stops the queue with `unknown-status` if a line uses `complete:`. Replace `- [ ] **<id>** ... complete:` with `- [x] **<id>** ... merge:` or remove the parent summary line. Dotted IDs (`1.1`, `1.2`) still work as normal independent cards.
- **`pair:` line (paired-repo support removed):** Ignored by the v21 gate; you may delete the `pair:` line from `card-loop/board.md`.
- **`<TEK_SKILLS>` row:** Removed from [`skills/jt-work-queue/assets/board.template.md`](skills/jt-work-queue/assets/board.template.md). Only `<REPO_SKILLS>` is used for `Standard` tier diff reviews; existing boards with a `<TEK_SKILLS>` row continue to work without error.

</details>

## Running Tests

```bash
python3 -m unittest discover -s tests
```
