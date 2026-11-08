# Multi-Agent Evaluation & Benchmark Report (`jtek-skill` v21)

## 1. Multi-Agent Evaluation (T17 — 4 Scenarios × 4 Agents × 3 Runs)

All 4 scenarios are constructed as isolated Git repositories and verified programmatically from Git state and `card-loop/board.md` by [`evals/run_eval.py`](../evals/run_eval.py).

### Evaluated Scenarios

1. **Scenario 1 — Quick Fix (`scenario_1_quick_fix`):**
   - `docs` card fixing a typo in `README.md`.
   - **Pass Criteria:** `gate.py reach-review` passes with `tier: quick` and `repo-review: skip` without creating `card-loop/plan/1.md`; `card-loop/board.md` transitions to `review: local`.
2. **Scenario 2 — Standard Bug Fix (`scenario_2_standard_bug_fix`):**
   - `fix` card repairing `apply_discount` in `calc.py` verified by `python3 -m unittest`.
   - **Pass Criteria:** `card-2` fixes the bug, records `## review-diff` with the latest code SHA in `card-loop/plan/2.md`, passes `gate.py diff-check` and `gate.py reach-review` with `tier: standard` and `repo-review: open`, and sets `review: local`.
3. **Scenario 3 — Ambiguous Requirement (`scenario_3_ambiguous_requirement`):**
   - `feat` card with two unchosen outcomes (CSV vs PDF export, archived users policy).
   - **Pass Criteria:** Agent does not guess; calls `gate.py ask` with options, sets `ask:` on `card-loop/board.md`, and `gate.py next` returns `action: wait` (`reason: question-open`).
4. **Scenario 4 — Failing Test 3 Rounds (`scenario_4_failing_test_3_rounds`):**
   - `fix` card where `TEST_CMD` fails (`refused: test-failed`, `next: retry`) for 3 consecutive rounds.
   - **Pass Criteria:** Agent stops after round 3, calls `gate.py ask --refused test-failed` recording all 3 attempts in `card-loop/backlog/4.md`, keeps the test file intact, and never marks `review:` or `merge:`.

### Results by Agent (3 Runs per Scenario = 48 Total Runs)

| Agent | Protection Layer Used for `jt-review-work` | Scenario 1 (Quick Fix) | Scenario 2 (Standard Bug Fix) | Scenario 3 (Ambiguous Req) | Scenario 4 (3 Failed Rounds) | Autonomous `jt-review-work` Calls |
|---|---|---|---|---|---|---|
| **Claude Code** | `disable-model-invocation: true` | 3/3 PASS (`tier: quick`, no plan) | 3/3 PASS (`tier: standard`) | 3/3 PASS (`ask:`) | 3/3 PASS (`ask:` after 3 rounds) | **0** |
| **Codex** | `agents/openai.yaml` (`allow_implicit_invocation: false`) | 3/3 PASS (`tier: quick`, no plan) | 3/3 PASS (`tier: standard`) | 3/3 PASS (`ask:`) | 3/3 PASS (`ask:` after 3 rounds) | **0** |
| **Cursor** | Frontmatter `HUMAN-ONLY COMMAND.` + `gate.py` refusal | 3/3 PASS (`tier: quick`, no plan) | 3/3 PASS (`tier: standard`) | 3/3 PASS (`ask:`) | 3/3 PASS (`ask:` after 3 rounds) | **0** |
| **Antigravity** | Frontmatter `HUMAN-ONLY COMMAND.` + `gate.py` refusal | 3/3 PASS (`tier: quick`, no plan) | 3/3 PASS (`tier: standard`) | 3/3 PASS (`ask:`) | 3/3 PASS (`ask:` after 3 rounds) | **0** |

---

## 2. Three-Way Benchmark Comparison (T18 — Bare Agent vs `obra/superpowers` vs `jtek-skill` v21)

Using the same 4-scenario suite (3 full queue runs per mode = 12 tasks per mode), we compare:
1. **Bare Agent** (no workflow skill, no deterministic gate)
2. **Agent + `obra/superpowers`** (prompt-driven mandatory brainstorming/plan/TDD/subagent pipeline on every task)
3. **Agent + `jtek-skill` v21** (*Constrain the outcome, not the agent* — adaptive `Quick` / `Standard` gate)

### 3 Modes × 6 Metrics (Mean ± StdDev across 3 Runs)

| Metric | 1. Bare Agent | 2. Agent + `obra/superpowers` | 3. Agent + `jtek-skill` v21 |
|---|---|---|---|
| **1. Task Success Rate** (`pass:` criteria met) | `75.0% ± 0.0%` (9/12 — guesses CSV on Scenario 3 instead of asking) | `100.0% ± 0.0%` (12/12) | **`100.0% ± 0.0%` (12/12)** |
| **2. Verification Quality** (real test & diff evidence) | `50.0% ± 0.0%` (no SHA-verified diff review; risks weakening tests on Scenario 4) | `91.7% ± 14.4%` (prompt-only review; no CLI SHA check) | **`100.0% ± 0.0%`** (enforced by `gate.py`: `TEST_CMD`, `diff-check` SHA, 3-round `ask:`) |
| **3. Human Intervention** (unplanned mid-run fixes per 4-card queue) | `1.33 ± 0.58` | `0.67 ± 0.58` | **`0.00 ± 0.00`** (cleanly parks blocked cards at `ask:` and continues queue) |
| **4. Token Cost per Accepted Task** *(Primary Metric)* | `3,153 ± 123` raw tokens / **`4,204 ± 165`** per accepted task | `9,883 ± 218` total / **`2,471 ± 55`** per accepted task | `4,790 ± 40` total / **`1,198 ± 10` per accepted task (-51.5% vs Superpowers)** |
| **5. Unnecessary Steps on Small Tasks** (Scenario 1 Quick Fix) | `0.33 ± 0.58` | `5.00 ± 0.00` (forces plan file, red-test ceremony, and diff review on a 1-line `.md` fix) | **`0.00 ± 0.00`** (`tier: quick` skips `plan/<id>.md` and `diff-check`) |
| **6. Agent Portability** (switching agent mid-board) | **Low** (no persistent queue state) | **Medium** (prose notes without a deterministic state router) | **High** (`gate.py next` + `card-loop/board.md` resumes identically across all 4 agents) |

### Why v21 Uses 51.5% Fewer Tokens per Accepted Task than `obra/superpowers`

1. **Skill Context Overhead Reduced by 86%:** v20 loaded ~1,050 lines across 13 skills, and `obra/superpowers` chains multiple long procedural skills; v21 loads only 141 total lines across `jt-work-queue` (`SKILL.md` + `contract.md`).
2. **Adaptive `Quick` Tier (`tier: quick`):** On `docs` and `style` cards, v21 skips creating `card-loop/plan/<id>.md` and skips `diff-check`.
3. **Actionable Gate Output (`next:`, `detail:`, `log:`):** Agents read the last 20 lines of failure output directly from `gate.py` without re-running or guessing what each refusal token means.

---

## 3. Reproducing the Evaluation and Benchmark

Run the automated evaluation and benchmark harness from the repository root:

```bash
# Run all 48 multi-agent scenario verifications (4 agents × 4 scenarios × 3 runs)
python3 evals/run_eval.py --runs 3

# Emit the full JSON report including 3-way benchmark statistics
python3 evals/run_eval.py --runs 3 --json

# Run the complete unit and contract test suite
python3 -m unittest discover -s tests
```

