import importlib.util
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GATE_PATH = REPO / "skills" / "jt-next-step" / "gate.py"


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
) -> str:
    return (
        "# Board — app\n\n"
        "สาขาคิว: main\n\n"
        "| ค่า | ใน repo นี้ |\n"
        "|---|---|\n"
        f"| `<TEST_CMD>` | {test} |\n"
        "| `<TYPECHECK_CMD>` | |\n"
        "| `<LINT_CMD>` | |\n"
        f"| `<BROWSER_TOOL>` | {browser} |\n"
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


def card_body(
    files: list[str],
    question: str = "",
    header: str = "HEADER_TOKEN",
    kind: str = "feat",
    screen: bool = False,
    start: str = "",
    port: str = "",
    click: str = "",
) -> str:
    listed = "\n".join(f"- {name}" for name in files) if files else "-"
    question_line = "ถาม:" if not question else f"ถาม: {question}"
    screen_block = ""
    if screen:
        screen_block = f"เห็นจอ: ใช่\nเริ่ม: {start}\nพอร์ต: {port}\nคลิก: {click}\n\n"
    return (
        "# 12 — title\n\n"
        f"ชนิด: {kind}\n\n"
        f"{screen_block}"
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
        self.assertEqual(decision.command, "/jt-do-work")
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

    def test_dropped_word_is_not_marked(self) -> None:
        text = board_text("- [x] **12** fresh (feat) ไม่เอา: ไม่ทำ")
        with self.assertRaises(gate.GateError) as caught:
            gate.apply_waiting_review(text, "12", 0)
        self.assertEqual(caught.exception.reason, "card-closed")
        self.assertIn("/jt-do-work", gate.COMMAND_FOR.values())
        self.assertNotIn("/jt-do-card", gate.COMMAND_FOR.values())
        self.assertIn("/jt-merge", gate.MERGE_ARGV)

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
        self.assertIn("command: /jt-open-work", result.stdout)
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
        self.assertIn("command: /jt-do-work", result.stdout)
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
        opened = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        opened_board = (self.repo / "card-loop" / "board.md").read_text(encoding="utf-8")
        self.assertEqual(opened.returncode, 0, opened.stdout + opened.stderr)
        self.assertIn("repo-review: open", opened.stdout)
        self.assertIn("รอรีวิว: local", opened_board)
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
        (plan / "12.md").write_text("จดใน plan แล้วเดินต่อ\n", encoding="utf-8")
        self._commit_on_card("docs: note the plan")
        skipped = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        skipped_board = (self.repo / "card-loop" / "board.md").read_text(encoding="utf-8")
        noted = git(self.repo, "show", "card-12:card-loop/plan/12.md")
        self.assertEqual(skipped.returncode, 0, skipped.stdout + skipped.stderr)
        self.assertIn("repo-review: skip", skipped.stdout)
        self.assertNotIn("repo-review: open", skipped.stdout)
        self.assertIn("รอรีวิว: local", skipped_board)
        self.assertIn("จดใน plan แล้วเดินต่อ", noted.stdout)

    def test_plan_note_on_a_code_commit_cannot_reach_review(self) -> None:
        (self.repo / "card-loop" / "board.md").write_text(
            board_text("- [ ] **12** note (chore)", test=gate.NO_SUITE),
            encoding="utf-8",
        )
        commit_all(self.repo, "docs: mark the chore")
        self._advance_card()
        plan = self.repo / "card-loop" / "plan"
        plan.mkdir(parents=True)
        (plan / "12.md").write_text("จดใน plan แล้วเดินต่อ\n", encoding="utf-8")
        self._commit_on_card("chore: note the plan")
        before = (self.repo / "card-loop" / "board.md").read_text(encoding="utf-8")
        result = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        after = (self.repo / "card-loop" / "board.md").read_text(encoding="utf-8")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refused: review-diff", result.stdout)
        self.assertIn("merge: no", result.stdout)
        self.assertEqual(after, before)
        self.assertNotIn("รอรีวิว:", after)
        noted = git(self.repo, "show", "card-12:card-loop/plan/12.md")
        self.assertIn("จดใน plan แล้วเดินต่อ", noted.stdout)

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

    def test_screen_work_without_a_browser_cannot_reach_review(self) -> None:
        self._screen("style", "", "python3 -c 'import sys; sys.exit(1)'", "9", "python3 -c 'print(1)'")
        before = (self.repo / "card-loop" / "board.md").read_text(encoding="utf-8")
        result = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        after = (self.repo / "card-loop" / "board.md").read_text(encoding="utf-8")
        loop = (REPO / "skills" / "jt-card-gate" / "references" / "loop.md").read_text(encoding="utf-8")
        source = GATE_PATH.read_text(encoding="utf-8")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refused: browser-empty", result.stdout)
        self.assertIn("step: ถาม", result.stdout)
        self.assertIn("merge: no", result.stdout)
        self.assertEqual(after, before)
        self.assertNotIn("รอรีวิว:", after)
        self.assertIn("(style)", after)
        self.assertIn("browser-empty", source)
        self.assertNotIn("browser-empty", loop)
        self.assertNotIn("playwright", loop.lower())
        self.assertNotIn("เริ่ม:", loop)
        self.assertNotIn("พอร์ต:", loop)
        self.assertNotIn("คลิก:", loop)

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
        self.assertIn("step: ถาม", result.stdout)
        self.assertEqual(after, before)
        self.assertNotIn("รอรีวิว:", after)
        self.assertIn("start-down", GATE_PATH.read_text(encoding="utf-8"))
        loop = (REPO / "skills" / "jt-card-gate" / "references" / "loop.md").read_text(encoding="utf-8")
        self.assertNotIn("start-down", loop)

    def test_screen_click_that_misses_the_header_cannot_reach_review(self) -> None:
        port = free_port()
        self._screen(
            "refactor",
            "playwright",
            f"python3 -m http.server {port}",
            str(port),
            "python3 -c 'print(\"nope\")'",
        )
        before = (self.repo / "card-loop" / "board.md").read_text(encoding="utf-8")
        result = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        after = (self.repo / "card-loop" / "board.md").read_text(encoding="utf-8")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("refused: click-mismatch", result.stdout)
        self.assertIn("step: ถาม", result.stdout)
        self.assertEqual(after, before)
        self.assertNotIn("รอรีวิว:", after)
        self.assertIn("click-mismatch", GATE_PATH.read_text(encoding="utf-8"))
        loop = (REPO / "skills" / "jt-card-gate" / "references" / "loop.md").read_text(encoding="utf-8")
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
        self.assertIn("รอรีวิว: local", board)
        self.assertNotIn("merge:", board)
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and port_open(port):
            time.sleep(0.05)
        self.assertFalse(port_open(port))


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


class RepoReviewTests(unittest.TestCase):
    def test_code_touching_type_opens_repo_review_and_docs_does_not(self) -> None:
        self.assertEqual(gate.CODE_KINDS, frozenset(CODE_KINDS))
        for kind in CODE_KINDS:
            self.assertTrue(gate.opens_repo_review(kind))
        self.assertFalse(gate.opens_repo_review("docs"))
        skills = (REPO / "skills" / "jt-card-gate" / "references" / "skills.md").read_text(
            encoding="utf-8"
        )
        do_card = (REPO / "skills" / "jt-do-work" / "SKILL.md").read_text(encoding="utf-8")
        repo = skills.split("## `<REPO_SKILLS>`", 1)[1]
        for kind in CODE_KINDS:
            self.assertIn(f"`{kind}`", repo)
            self.assertIn(f"`{kind}`", do_card)
        self.assertIn("`docs` ไม่เปิด", repo)
        self.assertIn("`docs` ไม่เปิด", do_card)
        self.assertNotIn("ตัวอย่าง", skills)
        self.assertIn("ชื่อจาก `<TEK_SKILLS>` ไม่มาทำรีวิวนี้แทน", repo)
        self.assertIn("ชื่อจาก `<TEK_SKILLS>` ไม่มาทำรีวิวนี้แทน", do_card)
        self.assertNotIn("TEK_SKILLS", GATE_PATH.read_text(encoding="utf-8"))


class GateSourceTests(unittest.TestCase):
    def test_gate_source_has_no_merge_and_no_skill_name_check(self) -> None:
        source = GATE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("git merge", source)
        self.assertNotIn('["merge"]', source)
        self.assertNotIn("REPO_SKILLS", source)
        self.assertNotIn("TEK_SKILLS", source)


if __name__ == "__main__":
    unittest.main()
