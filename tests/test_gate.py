import importlib.util
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GATE_PATH = REPO / "skills" / "jt-work-queue" / "scripts" / "gate.py"


def load_gate():
    spec = importlib.util.spec_from_file_location("tek_gate", GATE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["tek_gate"] = module
    spec.loader.exec_module(module)
    return module


gate = load_gate()


def board_text(
    cards: str,
    test: str = "python3 check.py",
    stack: str = "py · none · test · ban",
    browser: str = "",
    pair: str | None = None,
    setup: str = "",
) -> str:
    pair_line = "" if pair is None else f"pair: {pair}\n\n"
    return (
        "# Board - app\n\n"
        "queue: main\n\n"
        f"{pair_line}"
        "| Value | In this repo |\n"
        "|---|---|\n"
        f"| `<SETUP_CMD>` | {setup} |\n"
        f"| `<TEST_CMD>` | {test} |\n"
        "| `<TYPECHECK_CMD>` | |\n"
        "| `<LINT_CMD>` | |\n"
        f"| `<BROWSER_TOOL>` | {browser} |\n"
        f"| `<STACK_LOCK>` | {stack} |\n"
        "| `<TEK_SKILLS>` | grill |\n"
        "| `<REPO_SKILLS>` | review-skill |\n\n"
        "## first\n\n"
        f"{cards}\n\n"
        "## main\n\n"
        "no items\n\n"
        "## later\n\n"
        "no items\n"
    )


def card_body(
    files: list[str],
    question: str = "",
    header: str = "HEADER_TOKEN",
    kind: str = "feat",
    screen: bool = False,
    start: str = "",
    port: str = "",
    wait: str = "",
    click: str = "",
    title: str = "title",
    topic: str = "",
    refs: list[str] | None = None,
    do: str = "something",
) -> str:
    listed = "\n".join(f"- {name}" for name in files) if files else "-"
    question_line = "ask:" if not question else f"ask: {question}"
    screen_block = ""
    if screen:
        wait_line = f"wait: {wait}\n" if wait else ""
        screen_block = f"screen: yes\nstart: {start}\nport: {port}\n{wait_line}click: {click}\n\n"
    topic_line = f"layer: {topic}\n\n" if topic else ""
    ref_body = "\n".join(f"- {ref}" for ref in refs) if refs else "-"
    return (
        f"# 12 - {title}\n\n"
        f"kind: {kind}\n\n"
        f"{topic_line}"
        f"{screen_block}"
        "do:\n"
        f"- {do}\n\n"
        "out:\n"
        "- other\n\n"
        "pass:\n"
        f"- {header}\n\n"
        "chosen:\n"
        "- no fork\n\n"
        "files:\n"
        f"{listed}\n\n"
        "refs:\n"
        f"{ref_body}\n\n"
        f"{question_line}\n"
    )


def decide_board(text: str, bodies: dict[str, str | None], brief: bool = False):
    board = gate.hydrate(gate.parse_board(text), bodies)
    return gate.decide(board, brief_exists=brief, dirty=False, is_git=True)


class DecideTests(unittest.TestCase):
    def test_send_back_comes_before_a_fresh_card(self) -> None:
        text = board_text(
            "- [ ] **12** fresh (feat)\n- [ ] **13** back (fix) send-back:"
        )
        decision = decide_board(
            text,
            {"12": card_body(["src/a.py"]), "13": card_body(["src/b.py"])},
        )
        self.assertEqual(decision.action, "do-card")
        self.assertEqual(decision.id, "13")
        self.assertEqual(decision.reason, "send-back")
        self.assertEqual(decision.command, "/jt-work-queue")
        self.assertNotEqual(decision.action, "merge")

    def test_cleared_question_comes_before_a_fresh_card(self) -> None:
        text = board_text(
            "- [ ] **12** fresh (feat)\n- [ ] **13** asked (fix) ask:"
        )
        decision = decide_board(
            text,
            {
                "12": card_body(["src/a.py"]),
                "13": card_body(["src/b.py"], question=""),
            },
        )
        self.assertEqual(decision.action, "do-card")
        self.assertEqual(decision.id, "13")
        self.assertEqual(decision.reason, "question-cleared")

    def test_open_question_waits_and_does_not_merge(self) -> None:
        text = board_text("- [ ] **12** asked (fix) ask:")
        decision = decide_board(text, {"12": card_body(["src/a.py"], question="delete it?")})
        self.assertEqual(decision.action, "wait")
        self.assertEqual(decision.question, "delete it?")
        self.assertEqual(decision.command, "")

    def test_small_section_waits_while_a_higher_line_is_open(self) -> None:
        text = (
            "# Board - app\n\nqueue: main\n\n"
            "| Value | In this repo |\n|---|---|\n"
            "| `<TEST_CMD>` | python3 check.py |\n"
            "| `<TYPECHECK_CMD>` | |\n| `<LINT_CMD>` | |\n| `<BROWSER_TOOL>` | |\n"
            "| `<STACK_LOCK>` | py · none · test · ban |\n"
            "| `<TEK_SKILLS>` | |\n| `<REPO_SKILLS>` | |\n\n"
            "## first\n\n- [ ] **12** waiting (feat) review: local\n\n"
            "## main\n\nno items\n\n"
            "## later\n\n- [ ] **13** later (chore)\n"
        )
        decision = decide_board(
            text,
            {"12": card_body(["src/a.py"]), "13": card_body(["src/b.py"])},
        )
        self.assertEqual(decision.action, "wait")
        self.assertEqual(decision.reason, "review")
        self.assertEqual(decision.id, "12")
        self.assertEqual(decision.ids, ("12",))

    def test_overlap_with_review_does_not_start_work(self) -> None:
        text = board_text(
            "- [ ] **12** waiting (feat) review: local\n- [ ] **13** next (feat)"
        )
        decision = decide_board(
            text,
            {"12": card_body(["src/a.py"]), "13": card_body(["src/a.py"])},
        )
        self.assertEqual(decision.action, "wait")
        self.assertEqual(decision.reason, "review")
        self.assertEqual(decision.id, "12")
        self.assertEqual(decision.ids, ("12",))

    def test_two_reviews_wait_with_ids(self) -> None:
        text = board_text(
            "- [ ] **12** one (feat) review: local\n- [ ] **13** two (fix) review: local"
        )
        decision = decide_board(
            text,
            {"12": card_body(["src/a.py"]), "13": card_body(["src/b.py"])},
        )
        self.assertEqual(decision.action, "wait")
        self.assertEqual(decision.reason, "review")
        self.assertEqual(decision.id, "")
        self.assertEqual(decision.ids, ("12", "13"))
        self.assertEqual(decision.command, "")

    def test_missing_board_is_setup_and_empty_queue_is_brief_then_add(self) -> None:
        setup = gate.decide(None, brief_exists=False, dirty=False, is_git=True)
        self.assertEqual(setup.action, "setup-board")
        empty = decide_board(board_text("no items"), {})
        self.assertEqual(empty.action, "brief")
        with_brief = decide_board(board_text("no items"), {}, brief=True)
        self.assertEqual(with_brief.action, "add-card")

    def test_empty_test_command_stops_before_work(self) -> None:
        text = board_text("- [ ] **12** fresh (feat)", test="")
        decision = decide_board(text, {"12": card_body(["src/a.py"])})
        self.assertEqual(decision.action, "stop")
        self.assertEqual(decision.reason, "not-ready")
        self.assertIn("TEST_CMD", decision.fields)

    def test_actions_cannot_be_merge(self) -> None:
        self.assertNotIn("merge", gate.ALLOWED_ACTIONS)
        with self.assertRaises(gate.GateError):
            gate.Decision("merge")

    def test_unlinked_same_topic_stops_instead_of_starting_work(self) -> None:
        text = board_text("- [ ] **12** one (fix)\n- [ ] **13** two (fix)")
        decision = decide_board(
            text,
            {
                "12": card_body(["src/a.py"], topic="login"),
                "13": card_body(["src/b.py"], topic="login"),
            },
        )
        self.assertEqual(decision.action, "stop")
        self.assertEqual(decision.reason, "related")
        self.assertEqual(decision.command, "")
        self.assertEqual(decision.ids, ("12", "13"))
        self.assertNotEqual(decision.action, "do-card")

    def test_linked_same_topic_does_the_first_card(self) -> None:
        text = board_text("- [ ] **12** one (fix)\n- [ ] **13** two (fix)")
        decision = decide_board(
            text,
            {
                "12": card_body(["src/a.py"], topic="login", refs=["13"]),
                "13": card_body(["src/b.py"], topic="login", refs=["12"]),
            },
        )
        self.assertEqual(decision.action, "do-card")
        self.assertEqual(decision.id, "12")
        self.assertEqual(decision.reason, "ready")

    def test_checker_basename_is_only_a_new_check_script(self) -> None:
        self.assertIsNotNone(gate._CHECKER_BASENAME.match("check_once.py"))
        self.assertIsNotNone(gate._CHECKER_BASENAME.match("lint.sh"))
        self.assertIsNotNone(gate._CHECKER_BASENAME.match("verify.py"))
        self.assertIsNone(gate._CHECKER_BASENAME.match("checkout.py"))
        self.assertIsNone(gate._CHECKER_BASENAME.match("test_check.py"))
        self.assertIsNone(gate._CHECKER_BASENAME.match("my-checker"))


class ApplyReviewTests(unittest.TestCase):
    def test_red_exit_does_not_write_review(self) -> None:
        text = board_text("- [ ] **12** fresh (feat)")
        with self.assertRaises(gate.GateError) as caught:
            gate.apply_waiting_review(text, "12", 1)
        self.assertEqual(caught.exception.reason, "test-failed")
        self.assertNotIn("review:", text)

    def test_green_exit_writes_review_and_not_merge(self) -> None:
        text = board_text("- [ ] **12** fresh (feat)")
        updated = gate.apply_waiting_review(text, "12", 0, "local")
        self.assertIn("- [ ] **12** fresh (feat) review: local", updated)
        self.assertNotIn("merge:", updated.split("fresh", 1)[1])

    def test_green_exit_replaces_send_back(self) -> None:
        text = board_text("- [ ] **12** fresh (fix) send-back:")
        updated = gate.apply_waiting_review(text, "12", 0)
        self.assertIn("review:", updated)
        self.assertNotIn("send-back:", updated)

    def test_link_merge_is_refused(self) -> None:
        text = board_text("- [ ] **12** fresh (feat)")
        with self.assertRaises(gate.GateError) as caught:
            gate.apply_waiting_review(text, "12", 0, "merge:")
        self.assertEqual(caught.exception.reason, "merge-refused")

    def test_id_one_does_not_mark_one_point_one(self) -> None:
        text = board_text("- [ ] **1** parent (feat)\n- [ ] **1.1** child (feat)")
        updated = gate.apply_waiting_review(text, "1", 0)
        self.assertIn("**1** parent (feat) review:", updated)
        self.assertNotIn("**1.1** child (feat) review:", updated)

    def test_dropped_word_is_not_marked(self) -> None:
        text = board_text("- [x] **12** fresh (feat) drop: dropped")
        with self.assertRaises(gate.GateError) as caught:
            gate.apply_waiting_review(text, "12", 0)
        self.assertEqual(caught.exception.reason, "card-closed")
        self.assertIn("/jt-work-queue", gate.COMMAND_FOR.values())
        self.assertNotIn("open-review", gate.ALLOWED_ACTIONS)
        self.assertNotIn("/jt-do-card", gate.COMMAND_FOR.values())
        self.assertIn("/jt-merge", gate.MERGE_ARGV)

    def test_open_question_is_not_marked(self) -> None:
        text = board_text("- [ ] **12** asked (fix) ask:")
        with self.assertRaises(gate.GateError) as caught:
            gate.apply_waiting_review(text, "12", 0)
        self.assertEqual(caught.exception.reason, "question-open")

    def test_cleared_question_replaces_ask_with_review(self) -> None:
        text = board_text("- [ ] **12** asked (fix) ask:")
        updated = gate.apply_waiting_review(text, "12", 0, "local", question_empty=True)
        self.assertIn("- [ ] **12** asked (fix) review: local", updated)
        self.assertNotIn("ask:", updated)


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


def init_repo(repo: Path) -> None:
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Test")


def commit_all(repo: Path, message: str) -> None:
    git(repo, "add", "-A")
    git(repo, "commit", "-m", message)


def run_gate(
    repo: Path, *args: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GATE_PATH), *args, "--root", str(repo)],
        cwd=repo,
        capture_output=True,
        text=True,
        env=env,
    )


def run_gate_env(
    repo: Path, env: dict[str, str], *args: str
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GATE_PATH), *args, "--root", str(repo)],
        cwd=repo,
        capture_output=True,
        text=True,
        env=env,
    )


def run_diff_check(repo: Path, card_id: str = "12") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GATE_PATH), "diff-check", "--root", str(repo), "--id", card_id],
        cwd=repo,
        capture_output=True,
        text=True,
    )


def _git_bin_env(repo: Path, name: str, gh_script: str = "") -> dict[str, str]:
    bin_dir = repo / name
    bin_dir.mkdir()
    git_bin = shutil.which("git")
    assert git_bin
    os.symlink(git_bin, bin_dir / "git")
    if gh_script:
        gh = bin_dir / "gh"
        gh.write_text(gh_script, encoding="utf-8")
        gh.chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = str(bin_dir)
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


class ReachReviewGitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        init_repo(self.repo)
        (self.repo / "card-loop" / "backlog").mkdir(parents=True)
        (self.repo / "check.py").write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
        (self.repo / "card-loop" / "board.md").write_text(
            board_text("- [ ] **12** fresh (feat)"),
            encoding="utf-8",
        )
        (self.repo / "card-loop" / "backlog" / "12.md").write_text(
            card_body(["check.py"]),
            encoding="utf-8",
        )
        commit_all(self.repo, "docs: add the board")
        git(self.repo, "branch", "card-12")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _record_review(self, card_id: str = "12") -> None:
        git(self.repo, "checkout", f"card-{card_id}")
        head = git(self.repo, "rev-parse", "HEAD").stdout.strip()
        plan_dir = self.repo / "card-loop" / "plan"
        plan_dir.mkdir(parents=True, exist_ok=True)
        plan_path = plan_dir / f"{card_id}.md"
        plan_path.write_text(
            f"# Plan {card_id}\n\n## review-diff\n\n- commit: {head}\n- reviewer: reviewer\n- found: pass\n",
            encoding="utf-8",
        )
        commit_all(self.repo, "docs: record review")
        git(self.repo, "checkout", "main")

    def _set_card_check(self, code: str, record_review: bool = True) -> None:
        git(self.repo, "checkout", "card-12")
        (self.repo / "check.py").write_text(
            f"import sys\nsys.exit({code})\n# card\n",
            encoding="utf-8",
        )
        commit_all(self.repo, "test: set the card command")
        git(self.repo, "checkout", "main")
        if record_review:
            self._record_review("12")

    def test_red_command_on_the_card_branch_does_not_reach_review(self) -> None:
        self._set_card_check("1")
        before = (self.repo / "card-loop" / "board.md").read_text(encoding="utf-8")
        result = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        after = (self.repo / "card-loop" / "board.md").read_text(encoding="utf-8")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refused: test-failed", result.stdout)
        self.assertIn("merge: no", result.stdout)
        self.assertIn("next: retry", result.stdout)
        self.assertEqual(after, before)
        self.assertNotIn("review:", after)
        ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor", "card-12", "main"],
            cwd=self.repo,
            capture_output=True,
        )
        self.assertNotEqual(ancestor.returncode, 0)

    def test_test_failed_prints_detail_tail_and_log_without_dirtying_git(self) -> None:
        git(self.repo, "checkout", "card-12")
        (self.repo / "check.py").write_text(
            "import sys\nfor i in range(25):\n    print(f'ERR_LINE_{i}')\nsys.exit(1)\n",
            encoding="utf-8",
        )
        commit_all(self.repo, "test: failing output")
        git(self.repo, "checkout", "main")
        self._record_review("12")
        result = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refused: test-failed", result.stdout)
        self.assertIn("next: retry", result.stdout)
        self.assertIn("detail: ERR_LINE_5", result.stdout)
        self.assertIn("ERR_LINE_24", result.stdout)
        self.assertNotIn("ERR_LINE_0", result.stdout)
        log_lines = [
            line.split(":", 1)[1].strip()
            for line in result.stdout.splitlines()
            if line.startswith("log:")
        ]
        self.assertEqual(len(log_lines), 1)
        log_path = Path(log_lines[0])
        self.assertTrue(log_path.is_file())
        self.assertIn("ERR_LINE_0", log_path.read_text(encoding="utf-8"))
        status = git(self.repo, "status", "--porcelain")
        self.assertEqual(status.stdout.strip(), "")

    def test_green_command_on_the_card_branch_writes_review_without_merging(self) -> None:
        (self.repo / "check.py").write_text("import sys\nsys.exit(1)\n", encoding="utf-8")
        commit_all(self.repo, "test: queue command is red")
        self._set_card_check("0")
        result = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        board = (self.repo / "card-loop" / "board.md").read_text(encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("allowed", result.stdout)
        self.assertIn("review: local", board)
        self.assertNotIn("merge:", board)
        self.assertIn("sys.exit(1)", (self.repo / "check.py").read_text(encoding="utf-8"))
        ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor", "card-12", "main"],
            cwd=self.repo,
            capture_output=True,
        )
        self.assertNotEqual(ancestor.returncode, 0)

    def test_no_suite_is_not_executed(self) -> None:
        board = board_text("- [ ] **12** note (docs)", test=gate.NO_SUITE)
        (self.repo / "card-loop" / "board.md").write_text(board, encoding="utf-8")
        commit_all(self.repo, "docs: clear the test command")
        git(self.repo, "checkout", "card-12")
        git(self.repo, "merge", "main")
        git(self.repo, "checkout", "main")
        result = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        updated = (self.repo / "card-loop" / "board.md").read_text(encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("review: local", updated)

    def test_no_suite_without_card_branch_refuses_card_branch_missing(self) -> None:
        board = board_text("- [ ] **12** note (docs)", test=gate.NO_SUITE)
        (self.repo / "card-loop" / "board.md").write_text(board, encoding="utf-8")
        commit_all(self.repo, "docs: clear the test command")
        git(self.repo, "branch", "-D", "card-12")
        result = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        updated = (self.repo / "card-loop" / "board.md").read_text(encoding="utf-8")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refused: card-branch-missing", result.stdout)
        self.assertNotIn("review:", updated)

    def test_write_off_the_queue_branch_is_refused(self) -> None:
        self._set_card_check("0")
        git(self.repo, "checkout", "card-12")
        before = (self.repo / "card-loop" / "board.md").read_text(encoding="utf-8")
        result = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        after = (self.repo / "card-loop" / "board.md").read_text(encoding="utf-8")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refused: not-on-queue-branch", result.stdout)
        self.assertEqual(after, before)
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=self.repo,
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(status.stdout.strip(), "")

    def test_ask_command_and_question_cleared_to_review_flow(self) -> None:
        first = run_gate(
            self.repo,
            "ask",
            "--id",
            "12",
            "--question",
            "which option?",
            "--refused",
            "related",
        )
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        second = run_gate(
            self.repo,
            "ask",
            "--id",
            "12",
            "--question",
            "updated question?",
            "--refused",
            "test-failed",
        )
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        board = (self.repo / "card-loop" / "board.md").read_text(encoding="utf-8")
        card = (self.repo / "card-loop" / "backlog" / "12.md").read_text(encoding="utf-8")
        self.assertEqual(board.count("ask:"), 1)
        self.assertIn("- [ ] **12** fresh (feat) ask:", board)
        self.assertEqual(card.count("\nask:"), 1)
        self.assertIn("ask: updated question?", card)
        self.assertEqual(card.count("\nrefused:"), 1)
        self.assertIn("refused: test-failed", card)

        refused_while_open = run_gate(
            self.repo, "reach-review", "--id", "12", "--write", "--link", "local"
        )
        self.assertNotEqual(refused_while_open.returncode, 0)
        self.assertIn("refused: question-open", refused_while_open.stdout)

        cleared_card = card.replace("ask: updated question?", "ask:")
        (self.repo / "card-loop" / "backlog" / "12.md").write_text(cleared_card, encoding="utf-8")
        commit_all(self.repo, "docs: human clears ask")

        nxt = run_gate(self.repo, "next")
        self.assertIn("action: do-card", nxt.stdout)
        self.assertIn("reason: question-cleared", nxt.stdout)

        self._set_card_check("0")
        reached = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        self.assertEqual(reached.returncode, 0, reached.stdout + reached.stderr)
        final_board = (self.repo / "card-loop" / "board.md").read_text(encoding="utf-8")
        self.assertIn("- [ ] **12** fresh (feat) review: local", final_board)
        self.assertNotIn("ask:", final_board)

    def test_merge_argument_cannot_merge(self) -> None:
        before = (self.repo / "card-loop" / "board.md").read_text(encoding="utf-8")
        result = run_gate(self.repo, "merge")
        after = (self.repo / "card-loop" / "board.md").read_text(encoding="utf-8")
        self.assertEqual(result.returncode, 2)
        self.assertIn("this gate cannot merge", result.stderr)
        self.assertIn("refused: merge", result.stdout)
        self.assertEqual(after, before)

    def test_next_on_review_waits_with_review_reason_and_ids(self) -> None:
        git(self.repo, "checkout", "card-12")
        (self.repo / "check.py").write_text("CARD_ONLY = True\n", encoding="utf-8")
        plan = self.repo / "card-loop" / "plan"
        plan.mkdir(parents=True)
        (plan / "12.md").write_text(
            "# Plan 12\n\n## evidence\n\n- python3 check.py\n\n"
            "## decisions\n\n| decision | why | evidence |\n|---|---|---|\n"
            "| DECIDE_TOKEN | because | check.py |\n",
            encoding="utf-8",
        )
        commit_all(self.repo, "feat: change the card")
        git(self.repo, "checkout", "main")
        text = board_text("- [ ] **12** fresh (feat) review: local")
        (self.repo / "card-loop" / "board.md").write_text(text, encoding="utf-8")
        before = (self.repo / "card-loop" / "board.md").read_bytes()
        result = run_gate(self.repo, "next")
        after = (self.repo / "card-loop" / "board.md").read_bytes()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("action: wait", result.stdout)
        self.assertIn("reason: review", result.stdout)
        self.assertIn("id: 12", result.stdout)
        self.assertIn("ids: 12", result.stdout)
        self.assertNotIn("action: open-review", result.stdout)
        self.assertNotIn("CARD_ONLY", result.stdout)
        self.assertIn("merge: no", result.stdout)
        self.assertNotIn("action: merge", result.stdout)
        self.assertEqual(after, before)

    def test_next_reads_a_ready_line_as_do_card(self) -> None:
        before = (self.repo / "card-loop" / "board.md").read_bytes()
        result = run_gate(self.repo, "next")
        after = (self.repo / "card-loop" / "board.md").read_bytes()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("action: do-card", result.stdout)
        self.assertIn("command: /jt-work-queue", result.stdout)
        self.assertIn("id: 12", result.stdout)
        self.assertIn("merge: no", result.stdout)
        self.assertEqual(after, before)

    def test_dirty_files_outside_card_loop_stop_the_gate(self) -> None:
        (self.repo / "notes.txt").write_text("dirty\n", encoding="utf-8")
        result = run_gate(self.repo, "next")
        self.assertIn("action: stop", result.stdout)
        self.assertIn("reason: dirty", result.stdout)
        self.assertNotIn("action: do-card", result.stdout)
        self.assertIn("merge: no", result.stdout)

    def test_broken_git_status_stops_with_git_status_failed(self) -> None:
        (self.repo / ".git" / "index").write_bytes(b"corrupt-index-bytes")
        result = run_gate(self.repo, "next")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("action: stop", result.stdout)
        self.assertIn("reason: git-status-failed", result.stdout)
        self.assertNotIn("action: do-card", result.stdout)

    def test_invalid_card_id_from_cli_is_refused(self) -> None:
        for bad_id in ("../../etc/passwd", "1/2", "..", "abc", "../12"):
            for subcmd in ("reach-review", "landed", "diff-check", "screen-check"):
                result = run_gate(self.repo, subcmd, "--id", bad_id)
                self.assertNotEqual(result.returncode, 0, f"{subcmd} {bad_id}")
                self.assertIn("refused: invalid-id", result.stdout, f"{subcmd} {bad_id}")

    def test_board_with_invalid_card_id_does_not_read_outside_backlog_and_stops(self) -> None:
        secret = self.repo / "card-loop" / "secret.md"
        secret.write_text("ask: LEAKED_SECRET\n", encoding="utf-8")
        (self.repo / "card-loop" / "board.md").write_text(
            board_text("- [ ] **../secret** traversal (feat) ask:"),
            encoding="utf-8",
        )
        commit_all(self.repo, "docs: add bad card id")
        self.assertEqual(gate._read_card(self.repo, "../secret"), "")
        result = run_gate(self.repo, "next")
        self.assertIn("action: stop", result.stdout)
        self.assertIn("reason: invalid-id", result.stdout)
        self.assertNotIn("LEAKED_SECRET", result.stdout)

    def _advance_card(self) -> None:
        git(self.repo, "checkout", "card-12")
        git(self.repo, "merge", "main")
        git(self.repo, "checkout", "main")

    def _commit_on_card(self, message: str) -> None:
        git(self.repo, "checkout", "card-12")
        commit_all(self.repo, message)
        git(self.repo, "checkout", "main")

    def test_chore_commit_opens_repo_review(self) -> None:
        (self.repo / "card-loop" / "board.md").write_text(
            board_text("- [ ] **12** note (chore)", test=gate.NO_SUITE),
            encoding="utf-8",
        )
        commit_all(self.repo, "docs: mark the chore")
        self._advance_card()
        (self.repo / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
        self._commit_on_card("chore: touch the script")
        self._record_review("12")
        opened = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        opened_board = (self.repo / "card-loop" / "board.md").read_text(encoding="utf-8")
        self.assertEqual(opened.returncode, 0, opened.stdout + opened.stderr)
        self.assertIn("repo-review: open", opened.stdout)
        self.assertIn("review: local", opened_board)
        self.assertNotIn("merge:", opened_board)

    def test_docs_commit_does_not_open_repo_review(self) -> None:
        (self.repo / "card-loop" / "board.md").write_text(
            board_text("- [ ] **12** note (docs)", test=gate.NO_SUITE),
            encoding="utf-8",
        )
        commit_all(self.repo, "docs: mark the note")
        self._advance_card()
        plan = self.repo / "card-loop" / "plan"
        plan.mkdir(parents=True)
        (plan / "12.md").write_text("a note in the plan, then continue\n", encoding="utf-8")
        self._commit_on_card("docs: note the plan")
        skipped = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        skipped_board = (self.repo / "card-loop" / "board.md").read_text(encoding="utf-8")
        noted = git(self.repo, "show", "card-12:card-loop/plan/12.md")
        self.assertEqual(skipped.returncode, 0, skipped.stdout + skipped.stderr)
        self.assertIn("tier: quick", skipped.stdout)
        self.assertIn("repo-review: skip", skipped.stdout)
        self.assertNotIn("repo-review: open", skipped.stdout)
        self.assertIn("review: local", skipped_board)
        self.assertIn("a note in the plan, then continue", noted.stdout)

    def test_quick_tier_docs_and_style_pass_without_plan(self) -> None:
        (self.repo / "card-loop" / "board.md").write_text(
            board_text("- [ ] **12** readme (docs)", test=gate.NO_SUITE),
            encoding="utf-8",
        )
        commit_all(self.repo, "docs: set docs card")
        self._advance_card()
        git(self.repo, "checkout", "card-12")
        (self.repo / "README.md").write_text("# Docs\n", encoding="utf-8")
        commit_all(self.repo, "docs: add readme")
        git(self.repo, "checkout", "main")
        res_docs = run_gate(self.repo, "reach-review", "--id", "12")
        self.assertEqual(res_docs.returncode, 0, res_docs.stdout + res_docs.stderr)
        self.assertIn("tier: quick", res_docs.stdout)
        self.assertIn("repo-review: skip", res_docs.stdout)

        (self.repo / "card-loop" / "board.md").write_text(
            board_text("- [ ] **12** format (style)", test=gate.NO_SUITE),
            encoding="utf-8",
        )
        commit_all(self.repo, "docs: set style card")
        git(self.repo, "branch", "-D", "card-12")
        git(self.repo, "branch", "card-12")
        git(self.repo, "checkout", "card-12")
        (self.repo / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
        commit_all(self.repo, "style: format app")
        git(self.repo, "checkout", "main")
        res_style = run_gate(self.repo, "reach-review", "--id", "12")
        self.assertEqual(res_style.returncode, 0, res_style.stdout + res_style.stderr)
        self.assertIn("tier: quick", res_style.stdout)
        self.assertIn("repo-review: skip", res_style.stdout)

    def test_adaptive_gate_escalates_to_standard_tier(self) -> None:
        for path in ("requirements.txt", "docs/conf.py"):
            (self.repo / "card-loop" / "board.md").write_text(
                board_text(f"- [ ] **12** note {path} (docs)", test=gate.NO_SUITE),
                encoding="utf-8",
            )
            commit_all(self.repo, f"docs: board for {path}")
            git(self.repo, "branch", "-D", "card-12")
            git(self.repo, "branch", "card-12")
            git(self.repo, "checkout", "card-12")
            target = self.repo / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("x = 1\n", encoding="utf-8")
            commit_all(self.repo, f"docs: touch {path}")
            git(self.repo, "checkout", "main")
            res = run_gate(self.repo, "reach-review", "--id", "12")
            self.assertNotEqual(res.returncode, 0, path)
            self.assertIn("refused: review-diff", res.stdout, path)

        # feat card with docs: commit -> Standard and refused: review-diff without review
        (self.repo / "card-loop" / "board.md").write_text(
            board_text("- [ ] **12** feature (feat)", test=gate.NO_SUITE),
            encoding="utf-8",
        )
        commit_all(self.repo, "docs: set feat card")
        git(self.repo, "branch", "-D", "card-12")
        git(self.repo, "branch", "card-12")
        git(self.repo, "checkout", "card-12")
        (self.repo / "README.md").write_text("# Sneaky\n", encoding="utf-8")
        commit_all(self.repo, "docs: sneaky commit on feat card")
        git(self.repo, "checkout", "main")
        res_feat_docs = run_gate(self.repo, "reach-review", "--id", "12")
        self.assertNotEqual(res_feat_docs.returncode, 0)
        self.assertIn("refused: review-diff", res_feat_docs.stdout)

        # feat card modified to (style) after branching -> still Standard
        (self.repo / "card-loop" / "board.md").write_text(
            board_text("- [ ] **12** feature two (feat)", test=gate.NO_SUITE),
            encoding="utf-8",
        )
        commit_all(self.repo, "docs: feat at branch point")
        git(self.repo, "branch", "-D", "card-12")
        git(self.repo, "branch", "card-12")
        git(self.repo, "checkout", "card-12")
        (self.repo / "app.py").write_text("X = 2\n", encoding="utf-8")
        commit_all(self.repo, "style: try to downgrade tier")
        git(self.repo, "checkout", "main")
        (self.repo / "card-loop" / "board.md").write_text(
            board_text("- [ ] **12** feature two (style)", test=gate.NO_SUITE),
            encoding="utf-8",
        )
        res_mutated = run_gate(self.repo, "reach-review", "--id", "12")
        self.assertNotEqual(res_mutated.returncode, 0)
        self.assertIn("refused: review-diff", res_mutated.stdout)

        # docs card with screen: yes -> Standard
        (self.repo / "card-loop" / "board.md").write_text(
            board_text("- [ ] **12** docs screen (docs)", test=gate.NO_SUITE),
            encoding="utf-8",
        )
        (self.repo / "card-loop" / "backlog" / "12.md").write_text(
            card_body(["README.md"], kind="docs", screen=True),
            encoding="utf-8",
        )
        commit_all(self.repo, "docs: docs card with screen")
        git(self.repo, "branch", "-D", "card-12")
        git(self.repo, "branch", "card-12")
        git(self.repo, "checkout", "card-12")
        (self.repo / "README.md").write_text("# Screen Docs\n", encoding="utf-8")
        commit_all(self.repo, "docs: update readme")
        git(self.repo, "checkout", "main")
        self.assertEqual(
            gate.card_tier(
                self.repo,
                "main",
                "12",
                (self.repo / "card-loop" / "backlog" / "12.md").read_text(encoding="utf-8"),
            ),
            "standard",
        )
        res_screen_docs = run_gate(self.repo, "reach-review", "--id", "12")
        self.assertNotEqual(res_screen_docs.returncode, 0)
        self.assertIn("refused: review-diff", res_screen_docs.stdout)

    def test_outside_files_and_style_changes_are_reported_without_refusal(self) -> None:
        # 1. Card touching file outside files: still passes and prints outside-files:
        (self.repo / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
        (self.repo / "card-loop" / "board.md").write_text(
            board_text("- [ ] **12** format (style)", test=gate.NO_SUITE),
            encoding="utf-8",
        )
        (self.repo / "card-loop" / "backlog" / "12.md").write_text(
            card_body(["app.py"], kind="style"),
            encoding="utf-8",
        )
        commit_all(self.repo, "docs: setup style card")
        git(self.repo, "branch", "-D", "card-12")
        git(self.repo, "branch", "card-12")
        git(self.repo, "checkout", "card-12")
        # Change only whitespace in app.py
        (self.repo / "app.py").write_text("VALUE = 1   \n\n", encoding="utf-8")
        commit_all(self.repo, "style: whitespace only")
        git(self.repo, "checkout", "main")
        res_ws = run_gate(self.repo, "reach-review", "--id", "12")
        self.assertEqual(res_ws.returncode, 0, res_ws.stdout + res_ws.stderr)
        self.assertIn("allowed", res_ws.stdout)
        self.assertNotIn("outside-files:", res_ws.stdout)
        self.assertNotIn("style-changes:", res_ws.stdout)

        # 2. Style card changing logic and touching extra.py outside files:
        git(self.repo, "checkout", "card-12")
        (self.repo / "app.py").write_text("VALUE = 2\n", encoding="utf-8")
        (self.repo / "extra.py").write_text("EXTRA = True\n", encoding="utf-8")
        commit_all(self.repo, "style: touch logic and extra")
        git(self.repo, "checkout", "main")
        res_logic = run_gate(self.repo, "reach-review", "--id", "12")
        self.assertEqual(res_logic.returncode, 0, res_logic.stdout + res_logic.stderr)
        self.assertIn("allowed", res_logic.stdout)
        self.assertIn("outside-files: extra.py", res_logic.stdout)
        self.assertIn("style-changes: app.py, extra.py", res_logic.stdout)

        # 3. Empty files: does not print outside-files:
        (self.repo / "card-loop" / "backlog" / "12.md").write_text(
            card_body([], kind="style"),
            encoding="utf-8",
        )
        res_empty = run_gate(self.repo, "reach-review", "--id", "12")
        self.assertEqual(res_empty.returncode, 0, res_empty.stdout + res_empty.stderr)
        self.assertNotIn("outside-files:", res_empty.stdout)

    def test_plan_note_on_a_code_commit_cannot_reach_review(self) -> None:
        (self.repo / "card-loop" / "board.md").write_text(
            board_text("- [ ] **12** note (chore)", test=gate.NO_SUITE),
            encoding="utf-8",
        )
        commit_all(self.repo, "docs: mark the chore")
        self._advance_card()
        plan = self.repo / "card-loop" / "plan"
        plan.mkdir(parents=True)
        (plan / "12.md").write_text("a note in the plan, then continue\n", encoding="utf-8")
        self._commit_on_card("chore: note the plan")
        before = (self.repo / "card-loop" / "board.md").read_text(encoding="utf-8")
        result = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        after = (self.repo / "card-loop" / "board.md").read_text(encoding="utf-8")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refused: review-diff", result.stdout)
        self.assertIn("merge: no", result.stdout)
        self.assertEqual(after, before)
        self.assertNotIn("review:", after)
        noted = git(self.repo, "show", "card-12:card-loop/plan/12.md")
        self.assertIn("a note in the plan, then continue", noted.stdout)

    def _screen(self, kind: str, browser: str, start: str, port: str, click: str) -> None:
        (self.repo / "card-loop" / "board.md").write_text(
            board_text(f"- [ ] **12** screen ({kind})", browser=browser),
            encoding="utf-8",
        )
        (self.repo / "card-loop" / "backlog" / "12.md").write_text(
            card_body(
                ["app.py"],
                kind=kind,
                screen=True,
                start=start,
                port=port,
                click=click,
            ),
            encoding="utf-8",
        )
        commit_all(self.repo, "docs: describe the screen")
        self._advance_card()
        (self.repo / "app.py").write_text("BUTTON = True\n", encoding="utf-8")
        self._commit_on_card(f"{kind}: move the button")
        self._record_review("12")

    def test_screen_work_without_a_browser_cannot_reach_review(self) -> None:
        self._screen("style", "", "python3 -c 'import sys; sys.exit(1)'", "9", "python3 -c 'print(1)'")
        before = (self.repo / "card-loop" / "board.md").read_text(encoding="utf-8")
        result = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        after = (self.repo / "card-loop" / "board.md").read_text(encoding="utf-8")
        loop = (REPO / "skills" / "jt-work-queue" / "references" / "contract.md").read_text(encoding="utf-8")
        source = GATE_PATH.read_text(encoding="utf-8")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refused: browser-empty", result.stdout)
        self.assertIn("next: ask", result.stdout)
        self.assertIn("merge: no", result.stdout)
        self.assertEqual(after, before)
        self.assertNotIn("review:", after)
        self.assertIn("(style)", after)
        self.assertIn("browser-empty", source)
        self.assertNotIn("browser-empty", loop)
        self.assertNotIn("playwright", loop.lower())
        self.assertNotIn("start:", loop)
        self.assertNotIn("port:", loop)
        self.assertNotIn("click:", loop)

    def test_screen_start_that_does_not_come_up_cannot_reach_review(self) -> None:
        self._screen(
            "build",
            "playwright",
            "python3 -c 'import sys; sys.exit(1)'",
            str(free_port()),
            "python3 -c \"print('HEADER_TOKEN')\"",
        )
        before = (self.repo / "card-loop" / "board.md").read_text(encoding="utf-8")
        result = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        after = (self.repo / "card-loop" / "board.md").read_text(encoding="utf-8")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refused: start-down", result.stdout)
        self.assertIn("next: ask", result.stdout)
        self.assertEqual(after, before)
        self.assertNotIn("review:", after)
        self.assertIn("start-down", GATE_PATH.read_text(encoding="utf-8"))
        loop = (REPO / "skills" / "jt-work-queue" / "references" / "contract.md").read_text(encoding="utf-8")
        self.assertNotIn("start-down", loop)

    def test_screen_click_that_misses_the_header_cannot_reach_review(self) -> None:
        port = free_port()
        self._screen(
            "refactor",
            "playwright",
            f"python3 -m http.server {port}",
            str(port),
            "python3 -c 'import sys; sys.exit(1)'",
        )
        before = (self.repo / "card-loop" / "board.md").read_text(encoding="utf-8")
        result = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        after = (self.repo / "card-loop" / "board.md").read_text(encoding="utf-8")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("refused: click-mismatch", result.stdout)
        self.assertIn("next: ask", result.stdout)
        self.assertEqual(after, before)
        self.assertNotIn("review:", after)
        self.assertIn("click-mismatch", GATE_PATH.read_text(encoding="utf-8"))
        loop = (REPO / "skills" / "jt-work-queue" / "references" / "contract.md").read_text(encoding="utf-8")
        self.assertNotIn("click-mismatch", loop)
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and port_open(port):
            time.sleep(0.05)
        self.assertFalse(port_open(port))

    def test_screen_click_that_matches_the_header_can_reach_review(self) -> None:
        port = free_port()
        self._screen(
            "perf",
            "playwright",
            f"python3 -m http.server {port}",
            str(port),
            "python3 -c \"print('HEADER_TOKEN')\"",
        )
        result = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        board = (self.repo / "card-loop" / "board.md").read_text(encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("repo-review: open", result.stdout)
        self.assertIn("allowed", result.stdout)
        self.assertIn("review: local", board)
        self.assertNotIn("merge:", board)
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and port_open(port):
            time.sleep(0.05)
        self.assertFalse(port_open(port))

    def test_setup_failure_refuses_reach_review(self) -> None:
        (self.repo / "card-loop" / "board.md").write_text(
            board_text("- [ ] **12** fresh (feat)", setup="python3 -c 'import sys; sys.exit(1)'"),
            encoding="utf-8",
        )
        commit_all(self.repo, "docs: add setup cmd")
        self._set_card_check("0")
        result = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refused: setup-failed", result.stdout)

    def test_test_cmd_timeout_refuses_and_kills_spawned_child_processes(self) -> None:
        pid_file = self.repo / "child.pid"
        test_cmd = (
            f"python3 -c \"import os, signal, subprocess, time; "
            f"p = subprocess.Popen(['python3', '-c', 'import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(60)']); "
            f"open('{pid_file}', 'w').write(str(p.pid)); "
            f"time.sleep(60)\""
        )
        (self.repo / "card-loop" / "board.md").write_text(
            board_text("- [ ] **12** fresh (feat)", test=test_cmd),
            encoding="utf-8",
        )
        commit_all(self.repo, "docs: add hanging test cmd")
        self._set_card_check("0")
        env = os.environ.copy()
        env["JT_TEST_TIMEOUT"] = "0.3"
        result = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local", env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refused: test-timeout", result.stdout)
        self.assertTrue(pid_file.is_file())
        child_pid = int(pid_file.read_text(encoding="utf-8").strip())
        deadline = time.monotonic() + 2.0
        alive = True
        while time.monotonic() < deadline:
            try:
                os.kill(child_pid, 0)
            except ProcessLookupError:
                alive = False
                break
            time.sleep(0.05)
        self.assertFalse(alive, f"child process {child_pid} still running")

    def test_test_cmd_timeout_does_not_duplicate_output_and_invalid_timeout_env_falls_back(self) -> None:
        test_cmd = "python3 -c 'import sys, time; print(\"START\", flush=True); time.sleep(60)'"
        (self.repo / "card-loop" / "board.md").write_text(
            board_text("- [ ] **12** fresh (feat)", test=test_cmd),
            encoding="utf-8",
        )
        commit_all(self.repo, "docs: add printing timeout cmd")
        self._set_card_check("0")
        env = os.environ.copy()
        env["JT_TEST_TIMEOUT"] = "0.2"
        result = run_gate(self.repo, "reach-review", "--id", "12", env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refused: test-timeout", result.stdout)
        log_lines = [
            line.split(":", 1)[1].strip()
            for line in result.stdout.splitlines()
            if line.startswith("log:")
        ]
        self.assertEqual(len(log_lines), 1)
        log_content = Path(log_lines[0]).read_text(encoding="utf-8")
        self.assertEqual(log_content, "START\n")

        # Invalid JT_TEST_TIMEOUT falls back to default instead of raising ValueError
        os.environ["JT_TEST_TIMEOUT"] = "not-a-number"
        try:
            self.assertEqual(gate._env_timeout("JT_TEST_TIMEOUT", 300.0), 300.0)
        finally:
            os.environ.pop("JT_TEST_TIMEOUT", None)

    def test_setup_command_creates_prerequisite_in_worktree(self) -> None:
        (self.repo / "card-loop" / "board.md").write_text(
            board_text(
                "- [ ] **12** fresh (feat)",
                test="python3 -c 'import os, sys; sys.exit(0 if os.path.exists(\"dep.txt\") else 1)'",
                setup="python3 -c 'open(\"dep.txt\", \"w\").write(\"ok\")'",
            ),
            encoding="utf-8",
        )
        commit_all(self.repo, "docs: add setup cmd")
        self._record_review("12")
        result = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("allowed", result.stdout)

    def test_node_modules_bin_in_path_in_worktree(self) -> None:
        git(self.repo, "checkout", "card-12")
        bin_dir = self.repo / "node_modules" / ".bin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        tool = bin_dir / "my-checker"
        tool.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        tool.chmod(0o755)
        commit_all(self.repo, "chore: add bin tool")
        git(self.repo, "checkout", "main")
        (self.repo / "card-loop" / "board.md").write_text(
            board_text("- [ ] **12** fresh (feat)", test="my-checker"),
            encoding="utf-8",
        )
        commit_all(self.repo, "docs: add test cmd")
        self._record_review("12")
        result = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("allowed", result.stdout)

    def test_no_review_section_refuses_reach_review(self) -> None:
        git(self.repo, "checkout", "card-12")
        (self.repo / "check.py").write_text("import sys\nsys.exit(0)\n# new code\n", encoding="utf-8")
        commit_all(self.repo, "feat: implement feature")
        git(self.repo, "checkout", "main")
        result = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refused: review-diff", result.stdout)
        self.assertIn("detail: no-review", result.stdout)

    def test_stale_review_section_refuses_reach_review(self) -> None:
        git(self.repo, "checkout", "card-12")
        (self.repo / "check.py").write_text("import sys\nsys.exit(0)\n# first\n", encoding="utf-8")
        commit_all(self.repo, "feat: first change")
        git(self.repo, "checkout", "main")
        self._record_review("12")
        git(self.repo, "checkout", "card-12")
        (self.repo / "check.py").write_text("import sys\nsys.exit(0)\n# second\n", encoding="utf-8")
        commit_all(self.repo, "feat: second change")
        git(self.repo, "checkout", "main")
        result = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refused: review-diff", result.stdout)
        self.assertIn("detail: stale-review", result.stdout)

    def _write_plan(self, card_id: str, sha: str, decision: str = "") -> None:
        git(self.repo, "checkout", f"card-{card_id}")
        plan_dir = self.repo / "card-loop" / "plan"
        plan_dir.mkdir(parents=True, exist_ok=True)
        row = ""
        if decision:
            row = (
                "\n## decisions\n\n| decision | why | evidence |\n|---|---|---|\n"
                f"| {decision} |\n"
            )
        (plan_dir / f"{card_id}.md").write_text(
            f"# Plan {card_id}\n\n## review-diff\n\n- commit: {sha}\n"
            f"- reviewer: reviewer\n- found: pass\n{row}",
            encoding="utf-8",
        )
        commit_all(self.repo, "docs: record review")
        git(self.repo, "checkout", "main")

    def _topic_cards(self, refs: list[str] | None) -> None:
        (self.repo / "card-loop" / "board.md").write_text(
            board_text("- [ ] **12** one (fix)\n- [ ] **13** two (fix)"),
            encoding="utf-8",
        )
        (self.repo / "card-loop" / "backlog" / "12.md").write_text(
            card_body(["app.py"], topic="login", refs=refs),
            encoding="utf-8",
        )
        (self.repo / "card-loop" / "backlog" / "13.md").write_text(
            card_body(["src/b.py"], topic="login", refs=["12"] if refs else None),
            encoding="utf-8",
        )
        commit_all(self.repo, "docs: add the related cards")

    def test_added_checker_the_card_did_not_ask_for_cannot_reach_review(self) -> None:
        git(self.repo, "checkout", "card-12")
        (self.repo / "check_once.py").write_text("print('once')\n", encoding="utf-8")
        commit_all(self.repo, "fix: add a one-off checker")
        sha = git(self.repo, "rev-parse", "HEAD").stdout.strip()
        git(self.repo, "checkout", "main")
        self._write_plan("12", sha)
        before = (self.repo / "card-loop" / "board.md").read_text(encoding="utf-8")
        result = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        after = (self.repo / "card-loop" / "board.md").read_text(encoding="utf-8")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refused: one-off-checker", result.stdout)
        self.assertIn("merge: no", result.stdout)
        self.assertNotIn("next: ask", result.stdout)
        self.assertEqual(after, before)
        self.assertNotIn("review:", after)

    def test_checker_the_card_asked_for_can_reach_review(self) -> None:
        (self.repo / "card-loop" / "backlog" / "12.md").write_text(
            card_body(["check_once.py"], do="create check_once.py"),
            encoding="utf-8",
        )
        commit_all(self.repo, "docs: the card asks for the checker")
        git(self.repo, "checkout", "card-12")
        git(self.repo, "merge", "main")
        (self.repo / "check_once.py").write_text("print('once')\n", encoding="utf-8")
        commit_all(self.repo, "fix: add the checker the card asked for")
        sha = git(self.repo, "rev-parse", "HEAD").stdout.strip()
        git(self.repo, "checkout", "main")
        self._write_plan("12", sha)
        result = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        board = (self.repo / "card-loop" / "board.md").read_text(encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("review: local", board)
        self.assertNotIn("merge:", board)

    def test_checkout_module_is_not_a_one_off_checker(self) -> None:
        git(self.repo, "checkout", "card-12")
        (self.repo / "checkout.py").write_text("VALUE = 1\n", encoding="utf-8")
        commit_all(self.repo, "feat: add checkout")
        sha = git(self.repo, "rev-parse", "HEAD").stdout.strip()
        git(self.repo, "checkout", "main")
        self._write_plan("12", sha)
        result = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("allowed", result.stdout)

    def test_unlinked_same_topic_cannot_reach_review(self) -> None:
        self._topic_cards(None)
        before = (self.repo / "card-loop" / "board.md").read_text(encoding="utf-8")
        result = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        after = (self.repo / "card-loop" / "board.md").read_text(encoding="utf-8")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refused: related", result.stdout)
        self.assertIn("next: ask", result.stdout)
        self.assertIn("merge: no", result.stdout)
        self.assertEqual(after, before)
        self.assertNotIn("review:", after)

    def test_same_topic_linked_cards_can_reach_review_without_rule_update(self) -> None:
        self._topic_cards(["13"])
        git(self.repo, "checkout", "card-12")
        git(self.repo, "merge", "main")
        (self.repo / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
        commit_all(self.repo, "fix: patch only this card")
        sha = git(self.repo, "rev-parse", "HEAD").stdout.strip()
        git(self.repo, "checkout", "main")
        self._write_plan("12", sha)
        result = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        board = (self.repo / "card-loop" / "board.md").read_text(encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("allowed", result.stdout)
        self.assertIn("review: local", board)
        self.assertNotIn("merge:", board)

    def test_a_single_topic_can_patch_code_without_a_rule_row(self) -> None:
        (self.repo / "card-loop" / "backlog" / "12.md").write_text(
            card_body(["check.py"], topic="login"),
            encoding="utf-8",
        )
        commit_all(self.repo, "docs: classify the only card")
        self._set_card_check("0")
        result = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        board = (self.repo / "card-loop" / "board.md").read_text(encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("review: local", board)

    def test_multi_port_screen_check(self) -> None:
        port1 = free_port()
        port2 = free_port()
        self._screen(
            "perf",
            "playwright",
            f"python3 -m http.server {port1} & python3 -m http.server {port2}",
            f"{port1}, {port2}",
            f"python3 -c 'import urllib.request; urllib.request.urlopen(\"http://127.0.0.1:{port1}\"); urllib.request.urlopen(\"http://127.0.0.1:{port2}\")'",
        )
        result = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("allowed", result.stdout)
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and (port_open(port1) or port_open(port2)):
            time.sleep(0.05)
        self.assertFalse(port_open(port1))
        self.assertFalse(port_open(port2))


CODE_KINDS = (
    "feat",
    "fix",
    "style",
    "refactor",
    "perf",
    "test",
    "build",
    "ci",
    "chore",
    "revert",
)


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def port_open(port: int) -> bool:
    with socket.socket() as sock:
        sock.settimeout(0.2)
        return sock.connect_ex(("127.0.0.1", port)) == 0


class DraftPrReachTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        init_repo(self.repo)
        (self.repo / "card-loop" / "backlog").mkdir(parents=True)
        (self.repo / "check.py").write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
        (self.repo / "card-loop" / "board.md").write_text(
            board_text("- [ ] **12** fresh (feat)"),
            encoding="utf-8",
        )
        (self.repo / "card-loop" / "backlog" / "12.md").write_text(
            card_body(["check.py"]),
            encoding="utf-8",
        )
        commit_all(self.repo, "docs: add the board")
        git(self.repo, "branch", "card-12")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _record_review(self) -> None:
        git(self.repo, "checkout", "card-12")
        head = git(self.repo, "rev-parse", "HEAD").stdout.strip()
        plan_dir = self.repo / "card-loop" / "plan"
        plan_dir.mkdir(parents=True, exist_ok=True)
        (plan_dir / "12.md").write_text(
            f"# Plan 12\n\n## review-diff\n\n- commit: {head}\n- reviewer: reviewer\n- found: pass\n",
            encoding="utf-8",
        )
        commit_all(self.repo, "docs: record review")
        git(self.repo, "checkout", "main")

    def _commit_check(self, code: str) -> None:
        git(self.repo, "checkout", "card-12")
        (self.repo / "check.py").write_text(
            f"import sys\nsys.exit({code})\n# card\n",
            encoding="utf-8",
        )
        commit_all(self.repo, "test: set the card command")
        git(self.repo, "checkout", "main")
        self._record_review()

    def _origin(self) -> None:
        git(self.repo, "remote", "add", "origin", "https://example.invalid/repo.git")

    def _gh(self, body: str) -> dict[str, str]:
        bin_dir = self.repo / "fake-bin"
        bin_dir.mkdir(exist_ok=True)
        path = bin_dir / "gh"
        path.write_text(f"#!/bin/sh\n{body}", encoding="utf-8")
        path.chmod(0o755)
        env = os.environ.copy()
        env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
        return env

    def _json_gh(self, payload: str) -> dict[str, str]:
        return self._gh(f"printf '%s\\n' '{payload}'\n")

    def _no_gh(self) -> dict[str, str]:
        bin_dir = self.repo / "only-git"
        bin_dir.mkdir(exist_ok=True)
        for name in ("git", "python3"):
            dest = bin_dir / name
            if dest.exists():
                continue
            found = shutil.which(name)
            if found:
                dest.symlink_to(found)
        env = os.environ.copy()
        env["PATH"] = str(bin_dir)
        return env

    def _board(self) -> str:
        return (self.repo / "card-loop" / "board.md").read_text(encoding="utf-8")

    def test_classify_open_prs_names_the_draft_or_the_refusal(self) -> None:
        head = "card-12"
        base = "main"
        url = "https://example.invalid/pull/7"
        draft = {
            "url": url,
            "isDraft": True,
            "headRefName": head,
            "baseRefName": base,
        }
        self.assertEqual(gate.classify_open_prs([], head, base), ("ask", "pr-missing"))
        self.assertEqual(gate.classify_open_prs([draft], head, base), ("ok", url))
        ready = {**draft, "isDraft": False}
        self.assertEqual(gate.classify_open_prs([ready], head, base), ("ask", "pr-not-draft"))
        other_base = {**draft, "baseRefName": "dev"}
        self.assertEqual(gate.classify_open_prs([other_base], head, base), ("ask", "pr-base"))
        self.assertEqual(
            gate.classify_open_prs([draft, dict(draft)], head, base),
            ("ask", "pr-duplicate"),
        )
        blank = {**draft, "url": " "}
        self.assertEqual(gate.classify_open_prs([blank], head, base), ("ask", "pr-missing"))
        other_head = {**draft, "headRefName": "card-9"}
        self.assertEqual(
            gate.classify_open_prs([other_head], head, base),
            ("ask", "pr-missing"),
        )

    def test_no_remote_writes_local_without_calling_gh(self) -> None:
        self._commit_check("0")
        marker = self.repo / "gh-called"
        env = self._gh(f"touch {marker}\nexit 1\n")
        result = run_gate(
            self.repo, "reach-review", "--id", "12", "--write", "--link", "local", env=env
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("review: local", self._board())
        self.assertFalse(marker.exists())

    def test_dry_run_with_a_remote_stays_allowed_before_the_pull_request(self) -> None:
        self._commit_check("0")
        self._origin()
        before = self._board()
        result = run_gate(self.repo, "reach-review", "--id", "12", env=self._json_gh("[]"))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("allowed", result.stdout)
        self.assertNotIn("pr-missing", result.stdout)
        self.assertEqual(self._board(), before)

    def test_remote_without_a_draft_refuses_and_leaves_the_line(self) -> None:
        self._commit_check("0")
        self._origin()
        before = self._board()
        result = run_gate(
            self.repo,
            "reach-review",
            "--id",
            "12",
            "--write",
            "--link",
            "local",
            env=self._json_gh("[]"),
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refused: pr-missing", result.stdout)
        self.assertIn("next: ask", result.stdout)
        self.assertIn("merge: no", result.stdout)
        self.assertEqual(self._board(), before)
        self.assertNotIn("review:", self._board())

    def test_open_draft_into_the_queue_branch_writes_the_url(self) -> None:
        self._commit_check("0")
        self._origin()
        payload = (
            '[{"url":"https://example.invalid/pull/7","isDraft":true,'
            '"headRefName":"card-12","baseRefName":"main"}]'
        )
        result = run_gate(
            self.repo,
            "reach-review",
            "--id",
            "12",
            "--write",
            "--link",
            "local",
            env=self._json_gh(payload),
        )
        board = self._board()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("review: https://example.invalid/pull/7", board)
        self.assertNotIn("review: local", board)
        self.assertNotIn("merge:", board)

    def test_ready_pull_request_is_not_review(self) -> None:
        self._commit_check("0")
        self._origin()
        payload = (
            '[{"url":"https://example.invalid/pull/7","isDraft":false,'
            '"headRefName":"card-12","baseRefName":"main"}]'
        )
        result = run_gate(
            self.repo,
            "reach-review",
            "--id",
            "12",
            "--write",
            "--link",
            "local",
            env=self._json_gh(payload),
        )
        self.assertIn("refused: pr-not-draft", result.stdout)
        self.assertIn("next: ask", result.stdout)
        self.assertNotIn("review:", self._board())

    def test_two_open_pull_requests_do_not_write_review(self) -> None:
        self._commit_check("0")
        self._origin()
        one = (
            '{"url":"https://example.invalid/pull/7","isDraft":true,'
            '"headRefName":"card-12","baseRefName":"main"}'
        )
        result = run_gate(
            self.repo,
            "reach-review",
            "--id",
            "12",
            "--write",
            "--link",
            "local",
            env=self._json_gh(f"[{one},{one}]"),
        )
        self.assertIn("refused: pr-duplicate", result.stdout)
        self.assertIn("next: ask", result.stdout)
        self.assertNotIn("review:", self._board())

    def test_gh_failure_and_a_missing_binary_ask_instead_of_review(self) -> None:
        self._commit_check("0")
        self._origin()
        failed = run_gate(
            self.repo,
            "reach-review",
            "--id",
            "12",
            "--write",
            "--link",
            "local",
            env=self._gh("exit 1\n"),
        )
        self.assertIn("refused: pr-failed", failed.stdout)
        self.assertIn("next: ask", failed.stdout)
        self.assertNotIn("review:", self._board())
        missing = run_gate(
            self.repo,
            "reach-review",
            "--id",
            "12",
            "--write",
            "--link",
            "local",
            env=self._no_gh(),
        )
        self.assertIn("refused: gh-missing", missing.stdout)
        self.assertIn("next: ask", missing.stdout)
        self.assertNotIn("review:", self._board())

    def test_a_red_command_still_refuses_before_the_pull_request(self) -> None:
        self._commit_check("1")
        self._origin()
        result = run_gate(
            self.repo,
            "reach-review",
            "--id",
            "12",
            "--write",
            "--link",
            "local",
            env=self._json_gh("[]"),
        )
        self.assertIn("refused: test-failed", result.stdout)
        self.assertNotIn("pr-missing", result.stdout)
        self.assertNotIn("review:", self._board())


class RepoReviewTests(unittest.TestCase):
    def test_code_touching_type_opens_repo_review_and_docs_does_not(self) -> None:
        self.assertEqual(gate.CODE_KINDS, frozenset(CODE_KINDS))
        for kind in CODE_KINDS:
            self.assertTrue(gate.opens_repo_review(kind))
        self.assertFalse(gate.opens_repo_review("docs"))
        self.assertNotIn("TEK_SKILLS", GATE_PATH.read_text(encoding="utf-8"))


class V20FeatureTests(unittest.TestCase):
    def test_path_overlaps_containment(self) -> None:
        self.assertTrue(gate._path_overlaps("src/app", "src/app/utils.py"))
        self.assertTrue(gate._path_overlaps("src/app/utils.py", "src/app"))
        self.assertTrue(gate._path_overlaps("src/app", "src/app"))
        self.assertFalse(gate._path_overlaps("src/app", "src/apple"))
        self.assertTrue(gate._overlaps(("src/app",), ("src/app/sub.py",)))
        self.assertFalse(gate._overlaps(("src/app",), ("src/other.py",)))

    def test_complete_token_stops_as_unknown_status(self) -> None:
        text = board_text("- [ ] **1** legacy (feat) complete:")
        decision = decide_board(text, {"1": card_body(["src/a.py"])})
        self.assertEqual(decision.action, "stop")
        self.assertEqual(decision.reason, "unknown-status")
        self.assertEqual(decision.id, "1")

    def test_dotted_card_ids_work_as_normal_cards_without_parent(self) -> None:
        text = board_text("- [ ] **1.1** first (feat)\n- [ ] **1.2** second (feat)")
        decision = decide_board(
            text,
            {"1.1": card_body(["src/a.py"]), "1.2": card_body(["src/b.py"])},
        )
        self.assertEqual(decision.action, "do-card")
        self.assertEqual(decision.id, "1.1")
        self.assertEqual(decision.reason, "ready")

    def test_status_token_parsed_after_kind_suffix(self) -> None:
        text = board_text(
            "- [ ] **1** item (feat) merge:\n"
            "- [ ] **2** item (fix) send-back:\n"
            "- [ ] **3** item (chore) ask:\n"
            "- [ ] **4** item (feat) review: local"
        )
        parsed = gate.parse_board(text)
        self.assertEqual(parsed.cards[0].status, "merge:")
        self.assertEqual(parsed.cards[1].status, "send-back:")
        self.assertEqual(parsed.cards[2].status, "ask:")
        self.assertEqual(parsed.cards[3].status, "review:")


class LandedTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        init_repo(self.repo)
        (self.repo / "card-loop" / "backlog").mkdir(parents=True)
        (self.repo / "check.py").write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
        (self.repo / "card-loop" / "board.md").write_text(
            board_text("- [ ] **12** fresh (feat) review: local"),
            encoding="utf-8",
        )
        (self.repo / "card-loop" / "backlog" / "12.md").write_text(
            card_body(["app.py"]),
            encoding="utf-8",
        )
        commit_all(self.repo, "docs: add the board")
        git(self.repo, "branch", "card-12")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _diverge(self) -> None:
        git(self.repo, "checkout", "card-12")
        (self.repo / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
        commit_all(self.repo, "feat: card work")
        git(self.repo, "checkout", "main")

    def test_squash_merged_pr_is_landed_when_not_ancestor(self) -> None:
        self._diverge()
        ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor", "card-12", "main"],
            cwd=self.repo,
            capture_output=True,
        )
        self.assertNotEqual(ancestor.returncode, 0)
        before = (self.repo / "card-loop" / "board.md").read_text(encoding="utf-8")
        env = _git_bin_env(
            self.repo,
            "bin-squash",
            "#!/bin/sh\nprintf '%s\\n' '{\"state\":\"MERGED\",\"headRefName\":\"card-12\"}'\n",
        )
        result = run_gate_env(self.repo, env, "landed", "--id", "12")
        after = (self.repo / "card-loop" / "board.md").read_text(encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("landed: squash", result.stdout)
        self.assertIn("merge: no", result.stdout)
        self.assertNotIn("landed: ancestor", result.stdout)
        self.assertEqual(after, before)

    def test_open_pr_is_not_landed(self) -> None:
        self._diverge()
        env = _git_bin_env(
            self.repo,
            "bin-open",
            "#!/bin/sh\nprintf '%s\\n' '{\"state\":\"OPEN\",\"headRefName\":\"card-12\"}'\n",
        )
        result = run_gate_env(self.repo, env, "landed", "--id", "12")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refused: not-landed", result.stdout)
        self.assertIn("detail: pr-open", result.stdout)
        self.assertIn("merge: no", result.stdout)

    def test_ancestor_lands_without_calling_gh(self) -> None:
        self._diverge()
        git(self.repo, "merge", "--no-ff", "card-12", "-m", "merge card")
        result = run_gate_env(
            self.repo, _git_bin_env(self.repo, "bin-ancestor"), "landed", "--id", "12"
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("landed: ancestor", result.stdout)
        self.assertNotIn("landed: squash", result.stdout)
        self.assertIn("merge: no", result.stdout)

    def test_missing_pr_is_not_landed(self) -> None:
        self._diverge()
        result = run_gate_env(
            self.repo, _git_bin_env(self.repo, "bin-missing"), "landed", "--id", "12"
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refused: not-landed", result.stdout)
        self.assertIn("detail: pr-missing", result.stdout)
        self.assertIn("merge: no", result.stdout)

    def test_merged_pr_for_a_different_head_is_not_landed(self) -> None:
        self._diverge()
        env = _git_bin_env(
            self.repo,
            "bin-other",
            "#!/bin/sh\nprintf '%s\\n' '{\"state\":\"MERGED\",\"headRefName\":\"other\"}'\n",
        )
        result = run_gate_env(self.repo, env, "landed", "--id", "12")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refused: not-landed", result.stdout)
        self.assertIn("detail: pr-missing", result.stdout)

    def test_pr_list_covers_squash_when_view_fails(self) -> None:
        self._diverge()
        script = """#!/bin/sh
if [ "$2" = "view" ]; then
  exit 1
fi
printf '%s\\n' '[{"state":"MERGED","headRefName":"card-12"}]'
exit 0
"""
        result = run_gate_env(
            self.repo, _git_bin_env(self.repo, "bin-list", script), "landed", "--id", "12"
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("landed: squash", result.stdout)
        self.assertIn("merge: no", result.stdout)

    def test_next_reports_landed_waiting_for_merged_review_cards(self) -> None:
        self._diverge()
        # 1. Unmerged review: card -> no landed-waiting:
        unmerged = run_gate(self.repo, "next")
        self.assertEqual(unmerged.returncode, 0, unmerged.stdout + unmerged.stderr)
        self.assertNotIn("landed-waiting:", unmerged.stdout)

        # 2. Hanging gh with remote -> next still succeeds without failing
        git(self.repo, "remote", "add", "origin", "https://example.com/repo.git")
        hang_env = _git_bin_env(
            self.repo,
            "card-loop/bin-hang",
            "#!/bin/sh\n/bin/sleep 5\n",
        )
        hang_env["JT_GH_TIMEOUT"] = "0.2"
        hung = run_gate_env(self.repo, hang_env, "next")
        self.assertEqual(hung.returncode, 0, hung.stdout + hung.stderr)
        self.assertIn("action: wait", hung.stdout)
        self.assertIn("reason: review", hung.stdout)
        self.assertNotIn("landed-waiting:", hung.stdout)

        # 3. Ancestor merged -> next prints landed-waiting: 12 and does not modify board.md
        git(self.repo, "merge", "--no-ff", "card-12", "-m", "merge card-12")
        before = (self.repo / "card-loop" / "board.md").read_text(encoding="utf-8")
        merged = run_gate(self.repo, "next")
        after = (self.repo / "card-loop" / "board.md").read_text(encoding="utf-8")
        self.assertEqual(merged.returncode, 0, merged.stdout + merged.stderr)
        self.assertIn("landed-waiting: 12", merged.stdout)
        self.assertEqual(after, before)

    def test_next_reports_landed_waiting_for_squash_merged_pr(self) -> None:
        self._diverge()
        git(self.repo, "remote", "add", "origin", "https://example.com/repo.git")
        script = """#!/bin/sh
case "$*" in
  *"--state merged"*"--limit"*)
    printf '%s\\n' '[{"state":"MERGED","headRefName":"card-12"}]' ;;
  *) printf '%s\\n' '[]' ;;
esac
exit 0
"""
        env = _git_bin_env(self.repo, "card-loop/bin-squash", script)
        result = run_gate_env(self.repo, env, "next")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("landed-waiting: 12", result.stdout)


class DiffCheckTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        init_repo(self.repo)
        (self.repo / "card-loop" / "backlog").mkdir(parents=True)
        (self.repo / "check.py").write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
        (self.repo / "card-loop" / "board.md").write_text(
            board_text("- [ ] **12** fresh (feat)", test=gate.NO_SUITE),
            encoding="utf-8",
        )
        (self.repo / "card-loop" / "backlog" / "12.md").write_text(
            card_body(["app.py"]),
            encoding="utf-8",
        )
        commit_all(self.repo, "docs: add the board")
        git(self.repo, "branch", "card-12")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _commit_code(self) -> str:
        git(self.repo, "checkout", "card-12")
        (self.repo / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
        commit_all(self.repo, "feat: card work")
        sha = git(self.repo, "rev-parse", "HEAD").stdout.strip()
        git(self.repo, "checkout", "main")
        return sha

    def _write_plan(self, body: str) -> None:
        git(self.repo, "checkout", "card-12")
        plan = self.repo / "card-loop" / "plan"
        plan.mkdir(parents=True, exist_ok=True)
        (plan / "12.md").write_text(body, encoding="utf-8")
        commit_all(self.repo, "docs: record review")
        git(self.repo, "checkout", "main")

    def test_docs_only_range_skips(self) -> None:
        result = run_diff_check(self.repo)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("diff-check: skip", result.stdout)

    def test_matching_sha_exits_zero(self) -> None:
        sha = self._commit_code()
        self._write_plan(
            f"# Plan 12\n\n## review-diff\n\n- commit: {sha}\n- reviewer: reviewer\n- found: pass\n"
        )
        result = run_diff_check(self.repo)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(), "diff-check: ok")

    def test_missing_section_exits_nonzero(self) -> None:
        self._commit_code()
        result = run_diff_check(self.repo)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("diff-check: no-review", result.stdout)

    def test_section_without_a_sha_exits_nonzero(self) -> None:
        self._commit_code()
        self._write_plan("# Plan 12\n\n## review-diff\n\nnote only\n")
        result = run_diff_check(self.repo)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("diff-check: no-sha", result.stdout)

    def test_wrong_sha_exits_nonzero(self) -> None:
        self._commit_code()
        self._write_plan(
            "# Plan 12\n\n## review-diff\n\n- commit: "
            "0123456789abcdef0123456789abcdef01234567\n"
        )
        result = run_diff_check(self.repo)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("diff-check: stale-review", result.stdout)

    def test_dirty_card_worktree_exits_nonzero(self) -> None:
        sha = self._commit_code()
        self._write_plan(
            f"# Plan 12\n\n## review-diff\n\n- commit: {sha}\n- reviewer: reviewer\n- found: pass\n"
        )
        git(self.repo, "checkout", "card-12")
        (self.repo / "app.py").write_text("VALUE = 2\n", encoding="utf-8")
        result = run_diff_check(self.repo)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("diff-check: stale-review", result.stdout)

    def test_heading_alone_cannot_reach_review(self) -> None:
        self._commit_code()
        self._write_plan("# Plan 12\n\n## review-diff\n\nnote only\n")
        before = (self.repo / "card-loop" / "board.md").read_text(encoding="utf-8")
        result = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        after = (self.repo / "card-loop" / "board.md").read_text(encoding="utf-8")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refused: review-diff", result.stdout)
        self.assertIn("detail: no-sha", result.stdout)
        self.assertIn("merge: no", result.stdout)
        self.assertEqual(after, before)
        self.assertNotIn("review:", after)

    def test_copied_skill_folder_without_root_scripts_passes_reach_review(self) -> None:
        sha = self._commit_code()
        self._write_plan(
            f"# Plan 12\n\n## review-diff\n\n- commit: {sha}\n- reviewer: reviewer\n- found: pass\n"
        )
        with tempfile.TemporaryDirectory() as isolated_tmp:
            skill_dir = GATE_PATH.parent.parent
            copied_skill = Path(isolated_tmp) / "skills" / skill_dir.name
            shutil.copytree(skill_dir, copied_skill)
            copied_gate = copied_skill / "scripts" / GATE_PATH.name
            result = subprocess.run(
                [
                    sys.executable,
                    str(copied_gate),
                    "reach-review",
                    "--root",
                    str(self.repo),
                    "--id",
                    "12",
                    "--write",
                    "--link",
                    "local",
                ],
                cwd=self.repo,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("allowed", result.stdout)
            board = (self.repo / "card-loop" / "board.md").read_text(encoding="utf-8")
            self.assertIn("review: local", board)


class StatusBoundaryTests(unittest.TestCase):
    def test_unknown_status_stops_instead_of_starting_work(self) -> None:
        for token in ("wip:", "reveiw:", "รอรีวิว:", "ปิด:", "closed:"):
            text = board_text(f"- [ ] **13** bad (feat) {token}")
            decision = decide_board(text, {"13": card_body(["src/b.py"])})
            self.assertEqual(decision.action, "stop", token)
            self.assertEqual(decision.reason, "unknown-status", token)
            self.assertEqual(decision.id, "13", token)
            self.assertEqual(decision.command, "", token)
            self.assertNotEqual(decision.reason, "ready", token)
            with self.assertRaises(gate.GateError) as caught:
                gate.apply_waiting_review(text, "13", 0, "local")
            self.assertEqual(caught.exception.reason, "unknown-status", token)

    def test_unknown_status_blocks_a_sibling_card(self) -> None:
        text = board_text("- [ ] **12** fresh (feat)\n- [ ] **13** bad (feat) wip:")
        decision = decide_board(
            text,
            {"12": card_body(["src/a.py"]), "13": card_body(["src/b.py"])},
        )
        self.assertEqual(decision.action, "stop")
        self.assertEqual(decision.reason, "unknown-status")
        self.assertEqual(decision.id, "13")
        self.assertNotEqual(decision.action, "do-card")

    def test_title_colon_words_stay_ready_and_can_be_marked_review(self) -> None:
        for name in ("task: login", "backdrop: night", "incomplete: form", "mask: login"):
            line = f"- [ ] **12** {name} (feat)"
            text = board_text(line)
            parsed = gate.parse_board(text)
            self.assertEqual(len(parsed.cards), 1, name)
            self.assertIsNone(parsed.cards[0].status, name)
            decision = decide_board(text, {"12": card_body(["src/a.py"])})
            self.assertEqual(decision.action, "do-card", name)
            self.assertEqual(decision.id, "12", name)
            self.assertEqual(decision.reason, "ready", name)
            updated = gate.apply_waiting_review(text, "12", 0, "local")
            self.assertIn(f"{name} (feat) review: local", updated)

    def test_send_back_in_the_title_is_not_replaced(self) -> None:
        text = board_text("- [ ] **12** send-back: title (feat)")
        parsed = gate.parse_board(text)
        self.assertIsNone(parsed.cards[0].status)
        updated = gate.apply_waiting_review(text, "12", 0, "local")
        self.assertIn("- [ ] **12** send-back: title (feat) review: local", updated)

    def test_note_with_review_keeps_the_real_status(self) -> None:
        text = board_text("- [ ] **12** fresh (fix) send-back: review: the diff")
        parsed = gate.parse_board(text)
        self.assertEqual(parsed.cards[0].status, "send-back:")
        decision = decide_board(text, {"12": card_body(["src/a.py"])})
        self.assertEqual(decision.action, "do-card")
        self.assertEqual(decision.id, "12")
        self.assertEqual(decision.reason, "send-back")
        updated = gate.apply_waiting_review(text, "12", 0, "local")
        self.assertIn("fresh (fix) review: local review: the diff", updated)
        self.assertNotIn("send-back:", updated)

        asked = board_text("- [ ] **13** fresh (fix) ask: review: please look")
        parsed_ask = gate.parse_board(asked)
        self.assertEqual(parsed_ask.cards[0].status, "ask:")
        decision_ask = decide_board(
            asked,
            {"13": card_body(["src/a.py"], question="which?")},
        )
        self.assertEqual(decision_ask.action, "wait")
        self.assertEqual(decision_ask.question, "which?")
        with self.assertRaises(gate.GateError) as caught:
            gate.apply_waiting_review(asked, "13", 0, "local")
        self.assertEqual(caught.exception.reason, "question-open")

    def test_parent_review_ask_or_complete_is_not_do_card(self) -> None:
        bodies = {"1": card_body(["src/a.py"]), "1.1": card_body(["src/b.py"])}
        review = board_text(
            "- [ ] **1** parent (feat) review: local\n- [x] **1.1** child (feat) merge:"
        )
        decision = decide_board(review, bodies)
        self.assertEqual(decision.action, "wait")
        self.assertEqual(decision.id, "1")
        self.assertEqual(decision.ids, ("1",))
        self.assertEqual(decision.reason, "review")

        asked = board_text(
            "- [ ] **1** parent (feat) ask:\n- [x] **1.1** child (feat) merge:"
        )
        decision = decide_board(
            asked,
            {
                "1": card_body(["src/a.py"], question="which?"),
                "1.1": card_body(["src/b.py"]),
            },
        )
        self.assertEqual(decision.action, "wait")
        self.assertEqual(decision.question, "which?")

        done = board_text(
            "- [ ] **1** parent (feat) complete:\n- [x] **1.1** child (feat) merge:"
        )
        decision = decide_board(done, bodies)
        self.assertEqual(decision.action, "stop")
        self.assertEqual(decision.reason, "unknown-status")
        self.assertNotEqual(decision.action, "do-card")

    def test_review_link_may_contain_merge_colon(self) -> None:
        text = board_text("- [ ] **12** fresh (feat)")
        link = "https://example.com/merge:1"
        updated = gate.apply_waiting_review(text, "12", 0, link)
        self.assertIn("review: https://example.com/merge:1", updated)

    def test_capitalized_section_heading_is_still_the_queue(self) -> None:
        text = board_text("- [ ] **12** fresh (feat)").replace("## first\n", "## First\n", 1)
        decision = decide_board(text, {"12": card_body(["src/a.py"])})
        self.assertEqual(decision.action, "do-card")
        self.assertEqual(decision.id, "12")
        self.assertEqual(decision.reason, "ready")

    def test_legacy_board_with_pair_line_is_ignored(self) -> None:
        text = board_text("- [ ] **12** mask: login · side-repo (feat)", pair="side-repo")
        decision = decide_board(text, {"12": card_body(["src/a.py"])})
        self.assertEqual(decision.action, "do-card")
        self.assertEqual(decision.id, "12")

    def test_cargo_and_go_repos_have_setup_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Cargo.toml").write_text(
                "[package]\nname = \"a\"\nversion = \"0.1.0\"\n",
                encoding="utf-8",
            )
            self.assertEqual(gate.repo_setup_cmd(root), "cargo build")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "go.mod").write_text("module example.com/a\n\ngo 1.22\n", encoding="utf-8")
            self.assertEqual(gate.repo_setup_cmd(root), "go mod download")


class GateSourceTests(unittest.TestCase):
    def test_gate_source_has_no_merge_and_no_skill_name_check(self) -> None:
        source = GATE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("git merge", source)
        self.assertNotIn('["merge"]', source)
        self.assertNotIn("REPO_SKILLS", source)
        self.assertNotIn("TEK_SKILLS", source)
        self.assertIn("one-off-checker", source)
        self.assertNotIn("repeat-patch", source)
        self.assertIn('reason="related"', source)
        self.assertIn("pr-missing", source)
        self.assertNotIn("pr create", source)

    def test_every_refusal_token_is_in_next_for(self) -> None:
        import re as _re

        source = GATE_PATH.read_text(encoding="utf-8")
        found = set()
        found.update(_re.findall(r'_refuse\("([a-z0-9-]+)"', source))
        found.update(_re.findall(r'GateError\("([a-z0-9-]+)"', source))
        found.update(_re.findall(r'return \("ask", "([a-z0-9-]+)"\)', source))
        found.update(_re.findall(r'screen-check: ([a-z0-9-]+)', source))
        found.update(_re.findall(r'return "(start-down|click-mismatch|browser-failed)"', source))
        excluded = {"not-landed", "ok"}
        for token in sorted(found - excluded):
            self.assertIn(token, gate.NEXT_FOR, f"missing NEXT_FOR entry for {token}")
            self.assertIn(gate.NEXT_FOR[token], {"retry", "ask", "stop"})


if __name__ == "__main__":
    unittest.main()
