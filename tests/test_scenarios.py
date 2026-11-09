import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GATE_PATH = REPO / "skills" / "jt-work-queue" / "scripts" / "gate.py"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


def _run_gate(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    if args and args[0] in ("reach-review", "screen-check") and "--id" in args:
        # Simulate the human who reviewed and approved the board and card commands.
        subprocess.run(
            [sys.executable, str(GATE_PATH), "approve-commands", "--id", args[args.index("--id") + 1], "--root", str(repo)],
            cwd=repo,
            capture_output=True,
            text=True,
        )
    return subprocess.run(
        [sys.executable, str(GATE_PATH), *args, "--root", str(repo)],
        cwd=repo,
        capture_output=True,
        text=True,
    )


def _init_fixture_repo(
    repo: Path,
    card_id: str,
    board_line: str,
    card_text: str,
    test_cmd: str = "python3 -m unittest",
) -> None:
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Scenario Test")
    (repo / "jt-queue" / "tasks" / card_id).mkdir(parents=True, exist_ok=True)
    board = (
        "# Board - scenario-app\n\n"
        "queue: main\n\n"
        "| Value | In this repo |\n"
        "|---|---|\n"
        f"| `<TEST_CMD>` | {test_cmd} |\n"
        "| `<SETUP_CMD>` | |\n"
        "| `<TYPECHECK_CMD>` | |\n"
        "| `<LINT_CMD>` | |\n"
        "| `<BROWSER_TOOL>` | |\n"
        "| `<STACK_LOCK>` | python · stdlib · unittest · banned: external-deps |\n"
        "| `<REPO_SKILLS>` | |\n\n"
        "## first\n\n"
        f"{board_line}\n\n"
        "## main\n\nno items\n\n"
        "## later\n\nno items\n"
    )
    (repo / "jt-queue" / "board.md").write_text(board, encoding="utf-8")
    (repo / "jt-queue" / "tasks" / card_id / "task.md").write_text(card_text, encoding="utf-8")


class ScenarioGateIntegrationTests(unittest.TestCase):
    def test_scenario_1_quick_fix_docs_without_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            card = (
                "# 1 - fix readme typo\n\n"
                "kind: docs\n\n"
                "do:\n- Fix typo 'Teh' to 'The' in README.md\n\n"
                "out:\n- Code changes\n\n"
                "pass:\n- README.md contains 'The quick brown fox'\n\n"
                "files:\n- README.md\n\n"
                "refs:\n-\n\n"
                "ask:\n"
            )
            _init_fixture_repo(repo, "1", "- [ ] **1** fix readme typo (docs)", card, test_cmd="no-suite")
            (repo / "README.md").write_text("Teh quick brown fox\n", encoding="utf-8")
            _git(repo, "add", ".")
            _git(repo, "commit", "-m", "docs: initial repo")

            nxt = _run_gate(repo, "next")
            self.assertIn("action: do-task", nxt.stdout)
            self.assertIn("id: 1", nxt.stdout)

            _git(repo, "checkout", "-b", "task-1")
            (repo / "README.md").write_text("The quick brown fox\n", encoding="utf-8")
            _git(repo, "add", "README.md")
            _git(repo, "commit", "-m", "docs(1): fix typo in readme")
            _git(repo, "checkout", "main")

            reach = _run_gate(repo, "reach-review", "--id", "1", "--write", "--link", "local")
            self.assertEqual(reach.returncode, 0, reach.stdout)
            self.assertIn("tier: quick", reach.stdout)
            self.assertIn("repo-review: skip", reach.stdout)
            board_after = (repo / "jt-queue" / "board.md").read_text(encoding="utf-8")
            self.assertIn("- [ ] **1** fix readme typo (docs) review: local", board_after)
            self.assertNotIn("merge:", board_after)

    def test_scenario_2_standard_bug_fix_requires_plan_and_diff_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            card = (
                "# 2 - fix discount rounding bug\n\n"
                "kind: fix\n\n"
                "do:\n- Fix apply_discount(100, 15) in calc.py to return 85 instead of 115\n\n"
                "out:\n- Changing function signature\n\n"
                "pass:\n- python3 -m unittest passes\n\n"
                "files:\n- calc.py\n- test_calc.py\n\n"
                "refs:\n-\n\n"
                "ask:\n"
            )
            _init_fixture_repo(repo, "2", "- [ ] **2** fix discount bug (fix)", card)
            (repo / "calc.py").write_text(
                "def apply_discount(price: int, pct: int) -> int:\n    return price + pct\n",
                encoding="utf-8",
            )
            (repo / "test_calc.py").write_text(
                "import unittest\nfrom calc import apply_discount\n\n"
                "class CalcTests(unittest.TestCase):\n"
                "    def test_discount(self) -> None:\n"
                "        self.assertEqual(apply_discount(100, 15), 85)\n",
                encoding="utf-8",
            )
            _git(repo, "add", ".")
            _git(repo, "commit", "-m", "docs: initial buggy repo")

            nxt = _run_gate(repo, "next")
            self.assertIn("action: do-task", nxt.stdout)
            self.assertIn("id: 2", nxt.stdout)

            _git(repo, "checkout", "-b", "task-2")
            (repo / "calc.py").write_text(
                "def apply_discount(price: int, pct: int) -> int:\n    return price - (price * pct // 100)\n",
                encoding="utf-8",
            )
            _git(repo, "add", "calc.py")
            _git(repo, "commit", "-m", "fix(2): subtract discount percentage")
            code_sha = _git(repo, "rev-parse", "HEAD").stdout.strip()
            plan_dir = repo / "jt-queue" / "tasks" / "2"
            plan_dir.mkdir(parents=True, exist_ok=True)
            (plan_dir / "plan.md").write_text(
                "# Plan 2\n\n## Goal\n- Fix discount\n\n## Done when\n- python3 -m unittest\n\n"
                "## Escape\n- Signature change required\n\n"
                "## evidence\n| python3 -m unittest passes | python3 -m unittest | OK |\n\n"
                f"## review-diff\n- commit: {code_sha}\n- reviewer: self\n- verdict: pass\n- checked: scope\n\n"
                "## decisions\n| decision | why | evidence |\n|---|---|---|\n| subtract pct | fix bug | test_calc.py |\n",
                encoding="utf-8",
            )
            _git(repo, "add", "jt-queue/tasks/2/plan.md")
            _git(repo, "commit", "-m", "docs(2): record plan and review-diff")
            _git(repo, "checkout", "main")

            diff_chk = _run_gate(repo, "diff-check", "--id", "2")
            self.assertEqual(diff_chk.returncode, 0, diff_chk.stdout)
            reach = _run_gate(repo, "reach-review", "--id", "2", "--write", "--link", "local")
            self.assertEqual(reach.returncode, 0, reach.stdout)
            self.assertIn("tier: standard", reach.stdout)
            self.assertIn("repo-review: open", reach.stdout)
            board_after = (repo / "jt-queue" / "board.md").read_text(encoding="utf-8")
            self.assertIn("- [ ] **2** fix discount bug (fix) review: local", board_after)

    def test_scenario_3_ambiguous_requirement_stops_at_ask(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            card = (
                "# 3 - export user report\n\n"
                "kind: feat\n\n"
                "do:\n- Add report export endpoint (format not specified: CSV vs PDF)\n\n"
                "out:\n-\n\n"
                "pass:\n- Export works\n\n"
                "files:\n- report.py\n\n"
                "refs:\n-\n\n"
                "ask:\n"
            )
            _init_fixture_repo(repo, "3", "- [ ] **3** export user report (feat)", card, test_cmd="no-suite")
            (repo / "report.py").write_text("# report module\n", encoding="utf-8")
            _git(repo, "add", ".")
            _git(repo, "commit", "-m", "docs: initial repo")

            nxt = _run_gate(repo, "next")
            self.assertIn("action: do-task", nxt.stdout)

            ask_res = _run_gate(
                repo,
                "ask",
                "--id",
                "3",
                "--question",
                "Should export format be CSV or PDF, and should archived users be included?",
            )
            self.assertEqual(ask_res.returncode, 0, ask_res.stdout)
            _git(repo, "add", "jt-queue/board.md", "jt-queue/tasks/3/task.md")
            _git(repo, "commit", "-m", "docs(3): ask for export format clarification")

            after_next = _run_gate(repo, "next")
            self.assertIn("action: wait", after_next.stdout)
            self.assertIn("reason: question-open", after_next.stdout)

    def test_scenario_4_failing_test_3_rounds_records_ask(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            card = (
                "# 4 - fix external upstream checksum\n\n"
                "kind: fix\n\n"
                "do:\n- Update config.py without modifying test_upstream.py\n\n"
                "out:\n- test_upstream.py\n\n"
                "pass:\n- python3 -m unittest passes\n\n"
                "files:\n- config.py\n\n"
                "refs:\n-\n\n"
                "ask:\n"
            )
            _init_fixture_repo(repo, "4", "- [ ] **4** fix upstream checksum (fix)", card)
            (repo / "config.py").write_text("ATTEMPT = 0\n", encoding="utf-8")
            (repo / "test_upstream.py").write_text(
                "import unittest\n\nclass UpstreamTests(unittest.TestCase):\n"
                "    def test_impossible_invariant(self) -> None:\n"
                "        self.fail('upstream fixture unavailable in sandbox')\n",
                encoding="utf-8",
            )
            _git(repo, "add", ".")
            _git(repo, "commit", "-m", "docs: initial failing test repo")

            _git(repo, "checkout", "-b", "task-4")
            for round_num in (1, 2, 3):
                _git(repo, "checkout", "task-4")
                (repo / "config.py").write_text(f"ATTEMPT = {round_num}\n", encoding="utf-8")
                _git(repo, "add", "config.py")
                _git(repo, "commit", "-m", f"fix(4): attempt {round_num}")
                code_sha = _git(repo, "rev-parse", "HEAD").stdout.strip()
                plan_dir = repo / "jt-queue" / "tasks" / "4"
                plan_dir.mkdir(parents=True, exist_ok=True)
                (plan_dir / "plan.md").write_text(
                    "# Plan 4\n\n## evidence\n| python3 -m unittest passes | python3 -m unittest | fails |\n\n"
                    f"## review-diff\n- commit: {code_sha}\n- reviewer: self\n- verdict: pass\n- checked: scope\n",
                    encoding="utf-8",
                )
                _git(repo, "add", "jt-queue/tasks/4/plan.md")
                _git(repo, "commit", "-m", f"docs(4): review round {round_num}")
                _git(repo, "checkout", "main")
                reach = _run_gate(repo, "reach-review", "--id", "4")
                self.assertIn("refused: test-failed", reach.stdout)
                self.assertIn(f"round {round_num} of 3", reach.stdout)
                self.assertIn("next: retry" if round_num < 3 else "next: ask", reach.stdout)

            ask_res = _run_gate(
                repo,
                "ask",
                "--id",
                "4",
                "--question",
                "Test failed 3 rounds (tried ATTEMPT 1, 2, 3); upstream fixture unavailable. How should we proceed?",
                "--refused",
                "test-failed",
            )
            self.assertEqual(ask_res.returncode, 0, ask_res.stdout)
            card_after = (repo / "jt-queue" / "tasks" / "4" / "task.md").read_text(encoding="utf-8")
            self.assertIn("tried ATTEMPT 1, 2, 3", card_after)
            self.assertIn("refused: test-failed", card_after)

            # The human answered and the task resumes: the round count starts again.
            card_path = repo / "jt-queue" / "tasks" / "4" / "task.md"
            card_path.write_text(
                "\n".join(
                    "ask:" if line.startswith("ask:") else line
                    for line in card_after.splitlines()
                    if not line.startswith("refused:")
                )
                + "\n",
                encoding="utf-8",
            )
            again = _run_gate(repo, "reach-review", "--id", "4")
            self.assertIn("round 1 of 3", again.stdout)
            self.assertIn("next: retry", again.stdout)
            # Retrying the same commit still burns a round, so a flaky test cannot loop forever.
            same = _run_gate(repo, "reach-review", "--id", "4")
            self.assertIn("round 2 of 3", same.stdout)


if __name__ == "__main__":
    unittest.main()
