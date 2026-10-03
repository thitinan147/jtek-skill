import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GATE_PATH = REPO / "skills" / "tek-gate" / "gate.py"


def load_gate():
    spec = importlib.util.spec_from_file_location("tek_gate", GATE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["tek_gate"] = module
    spec.loader.exec_module(module)
    return module


gate = load_gate()


def board_text(cards: str, test: str = "python3 check.py", stack: str = "py · none · test · ban") -> str:
    return (
        "# Board — app\n\n"
        "สาขาคิว: main\n\n"
        "| ค่า | ใน repo นี้ |\n"
        "|---|---|\n"
        f"| `<TEST_CMD>` | {test} |\n"
        "| `<TYPECHECK_CMD>` | |\n"
        "| `<LINT_CMD>` | |\n"
        "| `<BROWSER_TOOL>` | |\n"
        f"| `<STACK_LOCK>` | {stack} |\n"
        "| `<TEK_SKILLS>` | grill |\n"
        "| `<REPO_SKILLS>` | review-skill |\n\n"
        "## ทำก่อน\n\n"
        f"{cards}\n\n"
        "## งานหลัก\n\n"
        "ไม่มีข้อ\n\n"
        "## เก็บเล็ก\n\n"
        "ไม่มีข้อ\n"
    )


def card_body(files: list[str], question: str = "", header: str = "HEADER_TOKEN") -> str:
    listed = "\n".join(f"- {name}" for name in files) if files else "-"
    question_line = "ถาม:" if not question else f"ถาม: {question}"
    return (
        "# 12 — title\n\n"
        "ชนิด: feat\n\n"
        "ทำ:\n"
        "- something\n\n"
        "ไม่ทำ:\n"
        "- other\n\n"
        "ตรวจผ่านเมื่อ:\n"
        f"- {header}\n\n"
        "ทางที่เลือกแล้ว:\n"
        "- ไม่มีสองทาง\n\n"
        "ไฟล์ที่แตะได้:\n"
        f"{listed}\n\n"
        "อ้างอิง:\n"
        "- \n\n"
        f"{question_line}\n"
    )


def decide_board(text: str, bodies: dict[str, str | None], brief: bool = False):
    board = gate.hydrate(gate.parse_board(text), bodies)
    return gate.decide(board, brief_exists=brief, dirty=False, is_git=True)


class DecideTests(unittest.TestCase):
    def test_send_back_comes_before_a_fresh_card(self) -> None:
        text = board_text(
            "- [ ] **12** fresh (feat)\n- [ ] **13** back (fix) ส่งกลับ:"
        )
        decision = decide_board(
            text,
            {"12": card_body(["src/a.py"]), "13": card_body(["src/b.py"])},
        )
        self.assertEqual(decision.action, "do-card")
        self.assertEqual(decision.id, "13")
        self.assertEqual(decision.reason, "send-back")
        self.assertEqual(decision.command, "/tek-do-card")
        self.assertNotEqual(decision.action, "merge")

    def test_cleared_question_comes_before_a_fresh_card(self) -> None:
        text = board_text(
            "- [ ] **12** fresh (feat)\n- [ ] **13** asked (fix) ถาม:"
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
        text = board_text("- [ ] **12** asked (fix) ถาม:")
        decision = decide_board(text, {"12": card_body(["src/a.py"], question="จะลบไหม")})
        self.assertEqual(decision.action, "wait")
        self.assertEqual(decision.question, "จะลบไหม")
        self.assertEqual(decision.command, "")

    def test_small_section_waits_while_a_higher_line_is_open(self) -> None:
        text = (
            "# Board — app\n\nสาขาคิว: main\n\n"
            "| ค่า | ใน repo นี้ |\n|---|---|\n"
            "| `<TEST_CMD>` | python3 check.py |\n"
            "| `<TYPECHECK_CMD>` | |\n| `<LINT_CMD>` | |\n| `<BROWSER_TOOL>` | |\n"
            "| `<STACK_LOCK>` | py · none · test · ban |\n"
            "| `<TEK_SKILLS>` | |\n| `<REPO_SKILLS>` | |\n\n"
            "## ทำก่อน\n\n- [ ] **12** waiting (feat) รอรีวิว: local\n\n"
            "## งานหลัก\n\nไม่มีข้อ\n\n"
            "## เก็บเล็ก\n\n- [ ] **13** later (chore)\n"
        )
        decision = decide_board(
            text,
            {"12": card_body(["src/a.py"]), "13": card_body(["src/b.py"])},
        )
        self.assertEqual(decision.action, "open-review")
        self.assertEqual(decision.id, "12")

    def test_overlap_with_review_does_not_start_work(self) -> None:
        text = board_text(
            "- [ ] **12** waiting (feat) รอรีวิว: local\n- [ ] **13** next (feat)"
        )
        decision = decide_board(
            text,
            {"12": card_body(["src/a.py"]), "13": card_body(["src/a.py"])},
        )
        self.assertEqual(decision.action, "open-review")
        self.assertEqual(decision.id, "12")

    def test_two_reviews_ask_for_an_id(self) -> None:
        text = board_text(
            "- [ ] **12** one (feat) รอรีวิว: local\n- [ ] **13** two (fix) รอรีวิว: local"
        )
        decision = decide_board(
            text,
            {"12": card_body(["src/a.py"]), "13": card_body(["src/b.py"])},
        )
        self.assertEqual(decision.reason, "need-id")
        self.assertEqual(decision.id, "")
        self.assertEqual(decision.ids, ("12", "13"))
        self.assertEqual(decision.command, "")

    def test_missing_board_is_setup_and_empty_queue_is_brief_then_add(self) -> None:
        setup = gate.decide(None, brief_exists=False, dirty=False, is_git=True)
        self.assertEqual(setup.action, "setup-board")
        empty = decide_board(board_text("ไม่มีข้อ"), {})
        self.assertEqual(empty.action, "brief")
        with_brief = decide_board(board_text("ไม่มีข้อ"), {}, brief=True)
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


class ApplyReviewTests(unittest.TestCase):
    def test_red_exit_does_not_write_review(self) -> None:
        text = board_text("- [ ] **12** fresh (feat)")
        with self.assertRaises(gate.GateError) as caught:
            gate.apply_waiting_review(text, "12", 1)
        self.assertEqual(caught.exception.reason, "test-failed")
        self.assertNotIn("รอรีวิว:", text)

    def test_green_exit_writes_review_and_not_merge(self) -> None:
        text = board_text("- [ ] **12** fresh (feat)")
        updated = gate.apply_waiting_review(text, "12", 0, "local")
        self.assertIn("- [ ] **12** fresh (feat) รอรีวิว: local", updated)
        self.assertNotIn("merge:", updated.split("fresh", 1)[1])

    def test_green_exit_replaces_send_back(self) -> None:
        text = board_text("- [ ] **12** fresh (fix) ส่งกลับ:")
        updated = gate.apply_waiting_review(text, "12", 0)
        self.assertIn("รอรีวิว:", updated)
        self.assertNotIn("ส่งกลับ:", updated)

    def test_link_merge_is_refused(self) -> None:
        text = board_text("- [ ] **12** fresh (feat)")
        with self.assertRaises(gate.GateError) as caught:
            gate.apply_waiting_review(text, "12", 0, "merge:")
        self.assertEqual(caught.exception.reason, "merge-refused")

    def test_id_one_does_not_mark_one_point_one(self) -> None:
        text = board_text("- [ ] **1** parent (feat)\n- [ ] **1.1** child (feat)")
        updated = gate.apply_waiting_review(text, "1", 0)
        self.assertIn("**1** parent (feat) รอรีวิว:", updated)
        self.assertNotIn("**1.1** child (feat) รอรีวิว:", updated)

    def test_open_question_is_not_marked(self) -> None:
        text = board_text("- [ ] **12** asked (fix) ถาม:")
        with self.assertRaises(gate.GateError) as caught:
            gate.apply_waiting_review(text, "12", 0)
        self.assertEqual(caught.exception.reason, "question-open")


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


def run_gate(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GATE_PATH), *args, "--root", str(repo)],
        cwd=repo,
        capture_output=True,
        text=True,
    )


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

    def _set_card_check(self, code: str) -> None:
        git(self.repo, "checkout", "card-12")
        (self.repo / "check.py").write_text(
            f"import sys\nsys.exit({code})\n# card\n",
            encoding="utf-8",
        )
        commit_all(self.repo, "test: set the card command")
        git(self.repo, "checkout", "main")

    def test_red_command_on_the_card_branch_does_not_reach_review(self) -> None:
        self._set_card_check("1")
        before = (self.repo / "card-loop" / "board.md").read_text(encoding="utf-8")
        result = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        after = (self.repo / "card-loop" / "board.md").read_text(encoding="utf-8")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refused: test-failed", result.stdout)
        self.assertIn("merge: no", result.stdout)
        self.assertEqual(after, before)
        self.assertNotIn("รอรีวิว:", after)
        ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor", "card-12", "main"],
            cwd=self.repo,
            capture_output=True,
        )
        self.assertNotEqual(ancestor.returncode, 0)

    def test_green_command_on_the_card_branch_writes_review_without_merging(self) -> None:
        (self.repo / "check.py").write_text("import sys\nsys.exit(1)\n", encoding="utf-8")
        commit_all(self.repo, "test: queue command is red")
        self._set_card_check("0")
        result = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        board = (self.repo / "card-loop" / "board.md").read_text(encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("allowed", result.stdout)
        self.assertIn("รอรีวิว: local", board)
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
        self.assertIn("รอรีวิว: local", updated)

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

    def test_merge_argument_cannot_merge(self) -> None:
        before = (self.repo / "card-loop" / "board.md").read_text(encoding="utf-8")
        result = run_gate(self.repo, "merge")
        after = (self.repo / "card-loop" / "board.md").read_text(encoding="utf-8")
        self.assertEqual(result.returncode, 2)
        self.assertIn("เกตนี้ merge ไม่ได้", result.stderr)
        self.assertIn("refused: merge", result.stdout)
        self.assertEqual(after, before)

    def test_next_on_review_compares_the_header_with_the_diff(self) -> None:
        git(self.repo, "checkout", "card-12")
        (self.repo / "check.py").write_text("CARD_ONLY = True\n", encoding="utf-8")
        plan = self.repo / "card-loop" / "plan"
        plan.mkdir(parents=True)
        (plan / "12.md").write_text(
            "# Plan 12\n\n## หลักฐานก่อนเปิดของให้ review\n\n- python3 check.py\n\n"
            "## การตัดสินใจ\n\n| ตัดสิน | ทำไม | หลักฐาน |\n|---|---|---|\n"
            "| DECIDE_TOKEN | because | check.py |\n",
            encoding="utf-8",
        )
        commit_all(self.repo, "feat: change the card")
        git(self.repo, "checkout", "main")
        text = board_text("- [ ] **12** fresh (feat) รอรีวิว: local")
        (self.repo / "card-loop" / "board.md").write_text(text, encoding="utf-8")
        before = (self.repo / "card-loop" / "board.md").read_bytes()
        result = run_gate(self.repo, "next")
        after = (self.repo / "card-loop" / "board.md").read_bytes()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("action: open-review", result.stdout)
        self.assertIn("command: /tek-open-review", result.stdout)
        self.assertIn("HEADER_TOKEN", result.stdout)
        self.assertIn("DECIDE_TOKEN", result.stdout)
        self.assertIn("CARD_ONLY", result.stdout)
        self.assertIn("compared: ตรวจผ่านเมื่อ diff", result.stdout)
        self.assertIn("merge: no", result.stdout)
        self.assertNotIn("action: merge", result.stdout)
        self.assertEqual(after, before)

    def test_next_reads_a_ready_line_as_do_card(self) -> None:
        before = (self.repo / "card-loop" / "board.md").read_bytes()
        result = run_gate(self.repo, "next")
        after = (self.repo / "card-loop" / "board.md").read_bytes()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("action: do-card", result.stdout)
        self.assertIn("command: /tek-do-card", result.stdout)
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


class GateSourceTests(unittest.TestCase):
    def test_gate_source_has_no_merge_and_no_skill_name_check(self) -> None:
        source = GATE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("git merge", source)
        self.assertNotIn('["merge"]', source)
        self.assertNotIn("REPO_SKILLS", source)
        self.assertNotIn("TEK_SKILLS", source)


if __name__ == "__main__":
    unittest.main()
