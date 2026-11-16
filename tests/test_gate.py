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
GATE_PATH = REPO / "skills" / "jt-work" / "scripts" / "gate.py"


def load_gate():
    prev = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec = importlib.util.spec_from_file_location("tek_gate", GATE_PATH)
        module = importlib.util.module_from_spec(spec)
        sys.modules["tek_gate"] = module
        spec.loader.exec_module(module)
        return module
    finally:
        sys.dont_write_bytecode = prev


gate = load_gate()

AI_REVIEW_BLOCK = "\n## ai-review\n\n- rejected: none — no finding\n"


def with_ai_review(plan: str) -> str:
    if "## ai-review" in plan:
        return plan
    return plan.rstrip() + AI_REVIEW_BLOCK


def board_text(
    cards: str,
    test: str = "python3 check.py",
    stack: str = "py · none · test · ban",
    browser: str = "",
    pair: str | None = None,
    setup: str = "",
    repos: str = "",
    lint: str = "",
    typecheck: str = "",
    diff_limit: str | None = None,
    affected: str | None = None,
    security: str | None = None,
    verify: str | None = None,
    denylist: str | None = None,
) -> str:
    pair_line = "" if pair is None else f"pair: {pair}\n\n"
    repos_block = f"## repos\n\n{repos}\n\n" if repos else ""
    return (
        "# Board - app\n\n"
        "queue: main\n\n"
        f"{pair_line}"
        "| Value | In this repo |\n"
        "|---|---|\n"
        f"| `<SETUP_CMD>` | {setup} |\n"
        f"| `<TEST_CMD>` | {test} |\n"
        f"| `<TYPECHECK_CMD>` | {typecheck} |\n"
        f"| `<LINT_CMD>` | {lint} |\n"
        f"| `<BROWSER_TOOL>` | {browser} |\n"
        f"| `<STACK_LOCK>` | {stack} |\n"
        + ("" if diff_limit is None else f"| `<DIFF_LIMIT>` | {diff_limit} |\n")
        + ("" if affected is None else f"| `<AFFECTED_TEST_CMD>` | {affected} |\n")
        + ("" if security is None else f"| `<SECURITY_CMD>` | {security} |\n")
        + ("" if verify is None else f"| `<VERIFY_CMD>` | {verify} |\n")
        + ("" if denylist is None else f"| `<DENYLIST>` | {denylist} |\n")
        + "| `<TEK_SKILLS>` | grill |\n"
        "| `<REPO_SKILLS>` | review-skill |\n\n"
        f"{repos_block}"
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
    size: str = "",
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
        + (f"size: {size}\n\n" if size else "")
        + f"{topic_line}"
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
        self.assertEqual(decision.action, "do-task")
        self.assertEqual(decision.id, "13")
        self.assertEqual(decision.reason, "send-back")
        self.assertEqual(decision.command, "/jt-work")
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
        self.assertEqual(decision.action, "do-task")
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
        self.assertEqual(with_brief.action, "add-task")
        self.assertEqual(with_brief.reason, "no-task")

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
        self.assertNotEqual(decision.action, "do-task")

    def test_linked_same_topic_does_the_first_card(self) -> None:
        text = board_text("- [ ] **12** one (fix)\n- [ ] **13** two (fix)")
        decision = decide_board(
            text,
            {
                "12": card_body(["src/a.py"], topic="login", refs=["13"]),
                "13": card_body(["src/b.py"], topic="login", refs=["12"]),
            },
        )
        self.assertEqual(decision.action, "do-task")
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
        self.assertEqual(caught.exception.reason, "task-closed")
        self.assertEqual(
            gate.COMMAND_FOR,
            {
                "setup-board": "/jt-setup",
                "brief": "/jt-add-task",
                "add-task": "/jt-add-task",
                "do-task": "/jt-work",
                "wait": "",
                "stop": "",
            },
        )
        self.assertNotIn("open-review", gate.ALLOWED_ACTIONS)
        self.assertNotIn("/jt-do-card", gate.COMMAND_FOR.values())
        self.assertNotIn("/jt-work-queue", gate.COMMAND_FOR.values())
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


def run_gate_raw(
    repo: Path, *args: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    """Run the gate exactly as given, with no simulated human approval."""
    return subprocess.run(
        [sys.executable, str(GATE_PATH), *args, "--root", str(repo)],
        cwd=repo,
        capture_output=True,
        text=True,
        env=env,
    )


def _simulate_human_approval(repo: Path, args: tuple[str, ...], env: dict[str, str] | None) -> None:
    """Most tests are not about approval: act like a human who reviewed the commands."""
    if args and args[0] in ("reach-review", "screen-check") and "--id" in args:
        card_id = args[args.index("--id") + 1]
        run_gate_raw(repo, "approve-commands", "--id", card_id, env=env)


def run_gate(
    repo: Path, *args: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    _simulate_human_approval(repo, args, env)
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
    _simulate_human_approval(repo, args, env)
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
        (self.repo / "jt-queue" / "tasks" / "12").mkdir(parents=True)
        (self.repo / "check.py").write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
        (self.repo / "jt-queue" / "board.md").write_text(
            board_text("- [ ] **12** fresh (feat)"),
            encoding="utf-8",
        )
        (self.repo / "jt-queue" / "tasks" / "12" / "task.md").write_text(
            card_body(["check.py"]),
            encoding="utf-8",
        )
        commit_all(self.repo, "docs: add the board")
        git(self.repo, "branch", "task-12")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_standard_branch_with_zero_commits_does_not_reach_review(self) -> None:
        ahead = git(self.repo, "rev-list", "--count", "main..task-12").stdout.strip()
        self.assertEqual(ahead, "0")
        before = (self.repo / "jt-queue" / "board.md").read_text(encoding="utf-8")
        result = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        after = (self.repo / "jt-queue" / "board.md").read_text(encoding="utf-8")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refused: review-diff", result.stdout)
        self.assertIn("no diff outside jt-queue/ to review", result.stdout)
        self.assertIn("next: retry", result.stdout)
        self.assertNotIn("repo-review: skip", result.stdout)
        self.assertNotIn("\nallowed\n", f"\n{result.stdout}")
        self.assertEqual(after, before)
        self.assertNotIn("review:", after)

    def test_standard_runs_lint_and_typecheck_and_reports_every_gate(self) -> None:
        self._set_card_check("0")
        empty = run_gate(self.repo, "reach-review", "--id", "12")
        self.assertEqual(empty.returncode, 0, empty.stdout + empty.stderr)
        self.assertIn(
            "gates: secret ok · denylist skip · typecheck skip · lint skip · tests ok · "
            "verify skip · screen skip · review-diff open · test-weakening none",
            empty.stdout,
        )
        self.assertNotIn("test-weakening:", empty.stdout)

        lint_marker = self.repo.parent / f"{self.repo.name}-lint"
        type_marker = self.repo.parent / f"{self.repo.name}-type"
        lint_marker.unlink(missing_ok=True)
        type_marker.unlink(missing_ok=True)
        (self.repo / "jt-queue" / "board.md").write_text(
            board_text(
                "- [ ] **12** fresh (feat)",
                lint="python3 -c 'import sys; sys.exit(1)'",
                typecheck=f"touch {type_marker}",
            ),
            encoding="utf-8",
        )
        lint_failed = run_gate(self.repo, "reach-review", "--id", "12")
        self.assertIn("refused: lint-failed", lint_failed.stdout)
        self.assertIn("step: lint", lint_failed.stdout)
        self.assertIn("skipped: tests", lint_failed.stdout)
        self.assertIn("next: retry", lint_failed.stdout)
        self.assertIn("round 1 of 3", lint_failed.stdout)
        self.assertTrue(type_marker.exists())

        (self.repo / "jt-queue" / "board.md").write_text(
            board_text(
                "- [ ] **12** fresh (feat)",
                lint=f"touch {lint_marker}",
                typecheck="python3 -c 'import sys; sys.exit(2)'",
            ),
            encoding="utf-8",
        )
        type_failed = run_gate(self.repo, "reach-review", "--id", "12")
        self.assertFalse(lint_marker.exists())
        self.assertIn("refused: typecheck-failed", type_failed.stdout)
        self.assertIn("step: typecheck", type_failed.stdout)
        self.assertIn("skipped: lint", type_failed.stdout)
        self.assertIn("round 2 of 3", type_failed.stdout)

        lint_marker.unlink(missing_ok=True)
        (self.repo / "jt-queue" / "board.md").write_text(
            board_text(
                "- [ ] **12** fresh (feat)",
                lint=f"touch {lint_marker}",
                typecheck="python3 -c pass",
            ),
            encoding="utf-8",
        )
        passed = run_gate(self.repo, "reach-review", "--id", "12")
        self.assertEqual(passed.returncode, 0, passed.stdout + passed.stderr)
        self.assertIn(
            "gates: secret ok · denylist skip · typecheck ok · lint ok · tests ok · "
            "verify skip · screen skip · review-diff open · test-weakening none",
            passed.stdout,
        )
        self.assertTrue(lint_marker.exists())
        lint_marker.unlink(missing_ok=True)
        type_marker.unlink(missing_ok=True)

    def test_quick_tier_does_not_run_lint_or_typecheck(self) -> None:
        marker = self.repo.parent / f"{self.repo.name}-lint"
        marker.unlink(missing_ok=True)
        (self.repo / "jt-queue" / "board.md").write_text(
            board_text(
                "- [ ] **12** readme (docs)",
                test=gate.NO_SUITE,
                lint=f"touch {marker}",
                typecheck=f"touch {marker}.type",
            ),
            encoding="utf-8",
        )
        commit_all(self.repo, "docs: set docs card")
        self._advance_card()
        git(self.repo, "checkout", "task-12")
        (self.repo / "README.md").write_text("# Docs\n", encoding="utf-8")
        commit_all(self.repo, "docs: add readme")
        git(self.repo, "checkout", "main")
        result = run_gate(self.repo, "reach-review", "--id", "12")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("tier: quick", result.stdout)
        self.assertIn(
            "gates: secret ok · denylist skip · typecheck skip · lint skip · tests skip · "
            "verify skip · screen skip · review-diff skip · test-weakening none",
            result.stdout,
        )
        self.assertFalse(marker.exists())
        self.assertFalse(Path(f"{marker}.type").exists())

    def test_setting_lint_after_approval_needs_reapproval(self) -> None:
        self._set_card_check("0")
        self.assertEqual(run_gate_raw(self.repo, "approve-commands", "--id", "12").returncode, 0)
        marker = self.repo.parent / f"{self.repo.name}-lint"
        marker.unlink(missing_ok=True)
        (self.repo / "jt-queue" / "board.md").write_text(
            board_text("- [ ] **12** fresh (feat)", lint=f"touch {marker}"),
            encoding="utf-8",
        )
        result = run_gate_raw(self.repo, "reach-review", "--id", "12")
        self.assertIn("refused: commands-changed", result.stdout)
        self.assertIn("next: stop", result.stdout)
        self.assertFalse(marker.exists())

    def test_added_secret_file_asks_and_does_not_print_the_value(self) -> None:
        token = "ZZSECRETZZ"
        marker = self.repo.parent / f"{self.repo.name}-ran"
        marker.unlink(missing_ok=True)
        (self.repo / "jt-queue" / "board.md").write_text(
            board_text("- [ ] **12** fresh (feat)", test=f"touch {marker}"),
            encoding="utf-8",
        )
        commit_all(self.repo, "docs: point the test command at a marker")

        def land(rel: str, body: str) -> subprocess.CompletedProcess[str]:
            git(self.repo, "checkout", "-q", "task-12")
            path = self.repo / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
            git(self.repo, "add", "--", rel)
            git(self.repo, "commit", "-m", "feat: add a file")
            git(self.repo, "checkout", "-q", "main")
            result = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
            git(self.repo, "branch", "-D", "task-12")
            git(self.repo, "branch", "task-12")
            marker.unlink(missing_ok=True)
            return result

        env = land(".env", f"TOKEN={token}\n")
        self.assertIn("refused: secret-suspect", env.stdout)
        self.assertIn("step: secret", env.stdout)
        self.assertIn("skipped: denylist", env.stdout)
        self.assertIn("next: ask", env.stdout)
        self.assertIn(".env", env.stdout)
        self.assertNotIn(token, env.stdout)
        self.assertNotIn(token, env.stderr)
        self.assertNotIn("review:", (self.repo / "jt-queue" / "board.md").read_text(encoding="utf-8"))
        self.assertFalse(marker.exists())

        local = land(".env.local", f"TOKEN={token}\n")
        self.assertIn("refused: secret-suspect", local.stdout)
        self.assertIn(".env.local", local.stdout)
        self.assertNotIn(token, local.stdout + local.stderr)

        example = land(".env.example", f"TOKEN={token}\n")
        self.assertNotIn("secret-suspect", example.stdout)
        self.assertIn("refused: review-diff", example.stdout)
        self.assertNotIn(token, example.stdout + example.stderr)

        key = land("id_rsa", token + "\n")
        self.assertIn("refused: secret-suspect", key.stdout)
        self.assertIn("id_rsa", key.stdout)
        self.assertNotIn(token, key.stdout + key.stderr)

        pub = land("id_rsa.pub", token + "\n")
        self.assertNotIn("secret-suspect", pub.stdout)
        self.assertIn("refused: review-diff", pub.stdout)

        pem = land("keys/dev.pem", token + "\n")
        self.assertIn("refused: secret-suspect", pem.stdout)
        self.assertIn("keys/dev.pem", pem.stdout)
        self.assertNotIn(token, pem.stdout + pem.stderr)

        lined = land("app.py", "x = 1\n-----BEGIN RSA PRIVATE KEY-----\n" + token + "\n")
        self.assertIn("refused: secret-suspect", lined.stdout)
        self.assertIn("next: ask", lined.stdout)
        self.assertIn("app.py:", lined.stdout)
        self.assertNotIn(token, lined.stdout + lined.stderr)
        self.assertNotIn("BEGIN", lined.stdout)
        self.assertNotIn("PRIVATE", lined.stdout)

    def test_fail_fast_stops_at_the_first_cheap_step(self) -> None:
        self.assertEqual(
            gate.FAIL_FAST,
            ("secret", "denylist", "typecheck", "lint", "tests", "verify"),
        )
        base = self.repo.parent
        markers = {
            name: base / f"{self.repo.name}-{name}"
            for name in ("type", "lint", "test", "verify")
        }
        for path in markers.values():
            path.unlink(missing_ok=True)
        self._set_card_check("0")

        def write(**kwargs: str) -> None:
            (self.repo / "jt-queue" / "board.md").write_text(
                board_text("- [ ] **12** fresh (feat)", **kwargs),
                encoding="utf-8",
            )

        write(
            typecheck="python3 -c 'import sys; sys.exit(2)'",
            lint=f"touch {markers['lint']}",
            test=f"touch {markers['test']}",
            verify=f"touch {markers['verify']}",
        )
        type_failed = run_gate(self.repo, "reach-review", "--id", "12")
        self.assertIn("refused: typecheck-failed", type_failed.stdout)
        self.assertIn("step: typecheck", type_failed.stdout)
        self.assertIn("skipped: lint", type_failed.stdout)
        self.assertFalse(markers["lint"].exists())
        self.assertFalse(markers["test"].exists())
        self.assertFalse(markers["verify"].exists())

        write(
            typecheck=f"touch {markers['type']}",
            lint="python3 -c 'import sys; sys.exit(2)'",
            test=f"touch {markers['test']}",
            verify=f"touch {markers['verify']}",
        )
        lint_failed = run_gate(self.repo, "reach-review", "--id", "12")
        self.assertIn("refused: lint-failed", lint_failed.stdout)
        self.assertIn("step: lint", lint_failed.stdout)
        self.assertIn("skipped: tests", lint_failed.stdout)
        self.assertTrue(markers["type"].exists())
        self.assertFalse(markers["test"].exists())
        self.assertFalse(markers["verify"].exists())

        for path in markers.values():
            path.unlink(missing_ok=True)
        write(
            typecheck=f"touch {markers['type']}",
            lint=f"touch {markers['lint']}",
            test="python3 -c 'import sys; sys.exit(1)'",
            verify=f"touch {markers['verify']}",
        )
        test_failed = run_gate(self.repo, "reach-review", "--id", "12")
        self.assertIn("refused: test-failed", test_failed.stdout)
        self.assertIn("step: tests", test_failed.stdout)
        self.assertIn("skipped: verify", test_failed.stdout)
        self.assertTrue(markers["type"].exists())
        self.assertTrue(markers["lint"].exists())
        self.assertFalse(markers["verify"].exists())

        for path in markers.values():
            path.unlink(missing_ok=True)
        write(
            typecheck=f"touch {markers['type']}",
            lint=f"touch {markers['lint']}",
            test=f"touch {markers['test']}",
            verify=f"touch {markers['verify']}",
        )
        passed = run_gate(self.repo, "reach-review", "--id", "12")
        self.assertEqual(passed.returncode, 0, passed.stdout + passed.stderr)
        self.assertIn(
            "gates: secret ok · denylist skip · typecheck ok · lint ok · tests ok · "
            "verify ok · screen skip · review-diff open · test-weakening none",
            passed.stdout,
        )
        self.assertTrue(all(path.exists() for path in markers.values()))

        for path in markers.values():
            path.unlink(missing_ok=True)
        write(
            typecheck=f"touch {markers['type']}",
            lint=f"touch {markers['lint']}",
            test=f"touch {markers['test']}",
            verify="python3 -c 'import sys; sys.exit(1)'",
        )
        verify_failed = run_gate(self.repo, "reach-review", "--id", "12")
        self.assertIn("refused: verify-failed", verify_failed.stdout)
        self.assertIn("step: verify", verify_failed.stdout)
        self.assertIn("skipped: none", verify_failed.stdout)
        self.assertTrue(markers["test"].exists())
        for path in markers.values():
            path.unlink(missing_ok=True)

    def test_denylist_hit_names_the_replacement_and_a_miss_does_not(self) -> None:
        secret = "ZZSECRETZZ"
        marker = self.repo.parent / f"{self.repo.name}-after-denylist"
        marker.unlink(missing_ok=True)
        self._set_card_check("0")

        def plant(body: str) -> None:
            git(self.repo, "checkout", "-q", "task-12")
            (self.repo / "app.py").write_text(body, encoding="utf-8")
            commit_all(self.repo, "feat: rename a symbol")
            git(self.repo, "checkout", "-q", "main")
            self._record_review("12")

        def use_slot() -> None:
            (self.repo / "jt-queue" / "board.md").write_text(
                board_text(
                    "- [ ] **12** fresh (feat)",
                    typecheck=f"touch {marker}",
                    denylist="dmedasset -> dmecasset",
                ),
                encoding="utf-8",
            )

        plant(f"name = 'dmedassets'\nrenamed = 'dmecasset'\nnote = '{secret}'\n")
        use_slot()
        missed = run_gate(self.repo, "reach-review", "--id", "12")
        self.assertEqual(missed.returncode, 0, missed.stdout + missed.stderr)
        self.assertIn("denylist ok", missed.stdout)
        self.assertNotIn("deprecated-name", missed.stdout)
        self.assertTrue(marker.exists())
        marker.unlink()

        plant(f"name = 'dmedasset'\nnote = '{secret}'\n")
        use_slot()
        hit = run_gate(self.repo, "reach-review", "--id", "12")
        self.assertIn("refused: deprecated-name", hit.stdout)
        self.assertIn("step: denylist", hit.stdout)
        self.assertIn("skipped: typecheck", hit.stdout)
        self.assertIn("dmedasset -> dmecasset", hit.stdout)
        self.assertIn("app.py:", hit.stdout)
        self.assertNotIn(secret, hit.stdout + hit.stderr)
        self.assertNotIn("dmecasset ->", hit.stdout)
        self.assertFalse(marker.exists())

        (self.repo / "jt-queue" / "denylist.txt").write_text(
            "# retired names\ndmedasset -> dmecasset\n",
            encoding="utf-8",
        )
        (self.repo / "jt-queue" / "board.md").write_text(
            board_text("- [ ] **12** fresh (feat)", typecheck=f"touch {marker}"),
            encoding="utf-8",
        )
        from_file = run_gate(self.repo, "reach-review", "--id", "12")
        self.assertIn("refused: deprecated-name", from_file.stdout)
        self.assertIn("dmecasset", from_file.stdout)
        self.assertNotIn("dmecasset ->", from_file.stdout)
        self.assertNotIn(secret, from_file.stdout + from_file.stderr)
        self.assertFalse(marker.exists())
        marker.unlink(missing_ok=True)

    def test_security_cmd_hides_the_value_and_falls_back_when_missing(self) -> None:
        token = "ZZSECRETZZ"
        later = self.repo.parent / f"{self.repo.name}-after-secret"
        later.unlink(missing_ok=True)
        ran = self.repo.parent / f"{self.repo.name}-scanner-ran"
        ran.unlink(missing_ok=True)
        bin_dir = self.repo.parent / f"{self.repo.name}-bin"
        if bin_dir.exists():
            shutil.rmtree(bin_dir)
        bin_dir.mkdir()
        scanner = bin_dir / "trufflehog"
        scanner.write_text(
            "#!/usr/bin/env python3\n"
            "import pathlib, sys\n"
            f"pathlib.Path({str(ran)!r}).write_text('ran', encoding='utf-8')\n"
            f"sys.stdout.write({token!r} + '\\n')\n"
            "raise SystemExit(3)\n",
            encoding="utf-8",
        )
        scanner.chmod(0o755)
        env = os.environ.copy()
        env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
        self._set_card_check("0")
        (self.repo / "jt-queue" / "board.md").write_text(
            board_text(
                "- [ ] **12** fresh (feat)",
                security="trufflehog filesystem .",
                typecheck=f"touch {later}",
            ),
            encoding="utf-8",
        )
        failed = run_gate(self.repo, "reach-review", "--id", "12", env=env)
        self.assertIn("refused: secret-failed", failed.stdout)
        self.assertIn("step: secret", failed.stdout)
        self.assertIn("skipped: denylist", failed.stdout)
        self.assertNotIn(token, failed.stdout + failed.stderr)
        self.assertTrue(ran.exists())
        self.assertFalse(later.exists())
        log_dir = self.repo / ".git" / "jt-queue" / "logs"
        if log_dir.is_dir():
            for log in log_dir.iterdir():
                self.assertNotIn(token, log.read_text(encoding="utf-8"))
        ran.unlink()

        git(self.repo, "checkout", "-q", "task-12")
        (self.repo / ".env").write_text(f"TOKEN={token}\n", encoding="utf-8")
        commit_all(self.repo, "feat: add env")
        git(self.repo, "checkout", "-q", "main")
        (self.repo / "jt-queue" / "board.md").write_text(
            board_text(
                "- [ ] **12** fresh (feat)",
                security="trufflehog filesystem .",
                typecheck=f"touch {later}",
            ),
            encoding="utf-8",
        )
        fallback = run_gate(self.repo, "reach-review", "--id", "12")
        self.assertIn("refused: secret-suspect", fallback.stdout)
        self.assertIn(".env", fallback.stdout)
        self.assertIn("step: secret", fallback.stdout)
        self.assertIn("skipped: denylist", fallback.stdout)
        self.assertNotIn(token, fallback.stdout + fallback.stderr)
        self.assertFalse(ran.exists())
        self.assertFalse(later.exists())
        later.unlink(missing_ok=True)
        ran.unlink(missing_ok=True)
        shutil.rmtree(bin_dir, ignore_errors=True)

    def test_deleted_test_and_skip_marker_are_reported(self) -> None:
        (self.repo / "tests").mkdir()
        (self.repo / "tests" / "test_old.py").write_text(
            "def test_old():\n    assert True\n", encoding="utf-8"
        )
        commit_all(self.repo, "test: add a test")
        git(self.repo, "branch", "-D", "task-12")
        git(self.repo, "branch", "task-12")
        git(self.repo, "checkout", "task-12")
        (self.repo / "tests" / "test_old.py").unlink()
        (self.repo / "check.py").write_text(
            "import sys\nsys.exit(0)\npytest.skip('nope')\n", encoding="utf-8"
        )
        (self.repo / "web.spec.js").write_text("it.only('x')\nxit('y')\n", encoding="utf-8")
        commit_all(self.repo, "feat: weaken the tests")
        git(self.repo, "checkout", "main")
        self._record_review("12")
        result = run_gate(self.repo, "reach-review", "--id", "12")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("deleted:tests/test_old.py", result.stdout)
        self.assertIn("marker:check.py:", result.stdout)
        self.assertIn("marker:web.spec.js:", result.stdout)
        self.assertIn("test-weakening: ", result.stdout)
        self.assertIn("allowed", result.stdout)
        for sample in (
            ".skip(",
            ".only(",
            "xit(",
            "xdescribe(",  # Jasmine skip marker the gate must still see  # spellchecker:disable-line
            "@skip",
            "@pytest.mark.skip",
            "xfail",
            "unittest.skip",
        ):
            self.assertIsNotNone(gate._SKIP_MARKER.search(sample), sample)
        self.assertIsNone(gate._SKIP_MARKER.search("skip the intro"))
        self.assertIsNone(gate._SKIP_MARKER.search("exit(0)"))

    def _record_review(self, card_id: str = "12") -> None:
        git(self.repo, "checkout", f"task-{card_id}")
        head = git(self.repo, "rev-parse", "HEAD").stdout.strip()
        plan_dir = self.repo / "jt-queue" / "tasks" / card_id
        plan_dir.mkdir(parents=True, exist_ok=True)
        plan_path = plan_dir / "plan.md"
        plan_path.write_text(
            with_ai_review(
                f"# Plan {card_id}\n\n## evidence\n\n| HEADER_TOKEN | check | ok |\n\n## review-diff\n\n- commit: {head}\n- reviewer: reviewer\n- verdict: pass\n- checked: scope\n"
            ),
            encoding="utf-8",
        )
        commit_all(self.repo, "docs: record review")
        git(self.repo, "checkout", "main")

    def _set_card_check(self, code: str, record_review: bool = True) -> None:
        git(self.repo, "checkout", "task-12")
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
        before = (self.repo / "jt-queue" / "board.md").read_text(encoding="utf-8")
        result = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        after = (self.repo / "jt-queue" / "board.md").read_text(encoding="utf-8")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refused: test-failed", result.stdout)
        self.assertIn("merge: no", result.stdout)
        self.assertIn("next: retry", result.stdout)
        self.assertEqual(after, before)
        self.assertNotIn("review:", after)
        ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor", "task-12", "main"],
            cwd=self.repo,
            capture_output=True,
        )
        self.assertNotEqual(ancestor.returncode, 0)

    def test_test_failed_prints_detail_tail_and_log_without_dirtying_git(self) -> None:
        git(self.repo, "checkout", "task-12")
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
        board = (self.repo / "jt-queue" / "board.md").read_text(encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("allowed", result.stdout)
        self.assertIn("review: local", board)
        self.assertNotIn("merge:", board)
        self.assertIn("sys.exit(1)", (self.repo / "check.py").read_text(encoding="utf-8"))
        ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor", "task-12", "main"],
            cwd=self.repo,
            capture_output=True,
        )
        self.assertNotEqual(ancestor.returncode, 0)

    def test_no_suite_is_not_executed(self) -> None:
        board = board_text("- [ ] **12** note (docs)", test=gate.NO_SUITE)
        (self.repo / "jt-queue" / "board.md").write_text(board, encoding="utf-8")
        commit_all(self.repo, "docs: clear the test command")
        git(self.repo, "checkout", "task-12")
        git(self.repo, "merge", "main")
        git(self.repo, "checkout", "main")
        result = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        updated = (self.repo / "jt-queue" / "board.md").read_text(encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("review: local", updated)

    def test_no_suite_without_card_branch_refuses_card_branch_missing(self) -> None:
        board = board_text("- [ ] **12** note (docs)", test=gate.NO_SUITE)
        (self.repo / "jt-queue" / "board.md").write_text(board, encoding="utf-8")
        commit_all(self.repo, "docs: clear the test command")
        git(self.repo, "branch", "-D", "task-12")
        result = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        updated = (self.repo / "jt-queue" / "board.md").read_text(encoding="utf-8")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refused: task-branch-missing", result.stdout)
        self.assertNotIn("review:", updated)

    def test_slug_branch_reaches_review(self) -> None:
        self._set_card_check("0")
        git(self.repo, "branch", "-m", "task-12", "task-12-fresh-start")
        result = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        board = (self.repo / "jt-queue" / "board.md").read_text(encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("allowed", result.stdout)
        self.assertIn("review: local", board)

    def test_two_branches_for_one_task_are_refused(self) -> None:
        self._set_card_check("0")
        git(self.repo, "branch", "task-12-fresh-start", "task-12")
        result = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        board = (self.repo / "jt-queue" / "board.md").read_text(encoding="utf-8")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refused: task-branch-missing", result.stdout)
        self.assertIn("task-12, task-12-fresh-start", result.stdout)
        self.assertNotIn("review:", board)

    def test_write_off_the_queue_branch_is_refused(self) -> None:
        self._set_card_check("0")
        git(self.repo, "checkout", "task-12")
        before = (self.repo / "jt-queue" / "board.md").read_text(encoding="utf-8")
        result = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        after = (self.repo / "jt-queue" / "board.md").read_text(encoding="utf-8")
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
        board = (self.repo / "jt-queue" / "board.md").read_text(encoding="utf-8")
        card = (self.repo / "jt-queue" / "tasks" / "12" / "task.md").read_text(encoding="utf-8")
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
        (self.repo / "jt-queue" / "tasks" / "12" / "task.md").write_text(cleared_card, encoding="utf-8")
        commit_all(self.repo, "docs: human clears ask")

        nxt = run_gate(self.repo, "next")
        self.assertIn("action: do-task", nxt.stdout)
        self.assertIn("reason: question-cleared", nxt.stdout)

        self._set_card_check("0")
        reached = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        self.assertEqual(reached.returncode, 0, reached.stdout + reached.stderr)
        final_board = (self.repo / "jt-queue" / "board.md").read_text(encoding="utf-8")
        self.assertIn("- [ ] **12** fresh (feat) review: local", final_board)
        self.assertNotIn("ask:", final_board)

    def test_merge_argument_cannot_merge(self) -> None:
        before = (self.repo / "jt-queue" / "board.md").read_text(encoding="utf-8")
        result = run_gate(self.repo, "merge")
        after = (self.repo / "jt-queue" / "board.md").read_text(encoding="utf-8")
        self.assertEqual(result.returncode, 2)
        self.assertIn("this gate cannot merge", result.stderr)
        self.assertIn("refused: merge", result.stdout)
        self.assertEqual(after, before)

    def test_next_on_review_waits_with_review_reason_and_ids(self) -> None:
        git(self.repo, "checkout", "task-12")
        (self.repo / "check.py").write_text("CARD_ONLY = True\n", encoding="utf-8")
        plan = self.repo / "jt-queue" / "tasks" / "12"
        plan.mkdir(parents=True, exist_ok=True)
        (plan / "plan.md").write_text(
            "# Plan 12\n\n## evidence\n\n- python3 check.py\n\n"
            "## decisions\n\n| decision | why | evidence |\n|---|---|---|\n"
            "| DECIDE_TOKEN | because | check.py |\n",
            encoding="utf-8",
        )
        commit_all(self.repo, "feat: change the card")
        git(self.repo, "checkout", "main")
        text = board_text("- [ ] **12** fresh (feat) review: local")
        (self.repo / "jt-queue" / "board.md").write_text(text, encoding="utf-8")
        before = (self.repo / "jt-queue" / "board.md").read_bytes()
        result = run_gate(self.repo, "next")
        after = (self.repo / "jt-queue" / "board.md").read_bytes()
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
        before = (self.repo / "jt-queue" / "board.md").read_bytes()
        result = run_gate(self.repo, "next")
        after = (self.repo / "jt-queue" / "board.md").read_bytes()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("action: do-task", result.stdout)
        self.assertIn("command: /jt-work", result.stdout)
        self.assertIn("id: 12", result.stdout)
        self.assertIn("merge: no", result.stdout)
        self.assertEqual(after, before)

    def test_dirty_files_outside_card_loop_stop_the_gate(self) -> None:
        (self.repo / "notes.txt").write_text("dirty\n", encoding="utf-8")
        result = run_gate(self.repo, "next")
        self.assertIn("action: stop", result.stdout)
        self.assertIn("reason: dirty", result.stdout)
        self.assertNotIn("action: do-task", result.stdout)
        self.assertIn("merge: no", result.stdout)

    def test_broken_git_status_stops_with_git_status_failed(self) -> None:
        (self.repo / ".git" / "index").write_bytes(b"corrupt-index-bytes")
        result = run_gate(self.repo, "next")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("action: stop", result.stdout)
        self.assertIn("reason: git-status-failed", result.stdout)
        self.assertNotIn("action: do-task", result.stdout)

    def test_invalid_card_id_from_cli_is_refused(self) -> None:
        for bad_id in ("../../etc/passwd", "1/2", "..", "abc", "../12"):
            for subcmd in ("reach-review", "landed", "diff-check", "screen-check"):
                result = run_gate(self.repo, subcmd, "--id", bad_id)
                self.assertNotEqual(result.returncode, 0, f"{subcmd} {bad_id}")
                self.assertIn("refused: invalid-id", result.stdout, f"{subcmd} {bad_id}")

    def test_board_with_invalid_card_id_does_not_read_outside_backlog_and_stops(self) -> None:
        secret = self.repo / "jt-queue" / "secret.md"
        secret.write_text("ask: LEAKED_SECRET\n", encoding="utf-8")
        (self.repo / "jt-queue" / "board.md").write_text(
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
        git(self.repo, "checkout", "task-12")
        git(self.repo, "merge", "main")
        git(self.repo, "checkout", "main")

    def _commit_on_card(self, message: str) -> None:
        git(self.repo, "checkout", "task-12")
        commit_all(self.repo, message)
        git(self.repo, "checkout", "main")

    def test_chore_commit_opens_repo_review(self) -> None:
        (self.repo / "jt-queue" / "board.md").write_text(
            board_text("- [ ] **12** note (chore)", test=gate.NO_SUITE),
            encoding="utf-8",
        )
        commit_all(self.repo, "docs: mark the chore")
        self._advance_card()
        (self.repo / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
        self._commit_on_card("chore: touch the script")
        self._record_review("12")
        opened = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        opened_board = (self.repo / "jt-queue" / "board.md").read_text(encoding="utf-8")
        self.assertEqual(opened.returncode, 0, opened.stdout + opened.stderr)
        self.assertIn("repo-review: open", opened.stdout)
        self.assertIn("review: local", opened_board)
        self.assertNotIn("merge:", opened_board)

    def test_docs_commit_does_not_open_repo_review(self) -> None:
        (self.repo / "jt-queue" / "board.md").write_text(
            board_text("- [ ] **12** note (docs)", test=gate.NO_SUITE),
            encoding="utf-8",
        )
        commit_all(self.repo, "docs: mark the note")
        self._advance_card()
        plan = self.repo / "jt-queue" / "tasks" / "12"
        plan.mkdir(parents=True, exist_ok=True)
        (plan / "plan.md").write_text("a note in the plan, then continue\n", encoding="utf-8")
        self._commit_on_card("docs: note the plan")
        skipped = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        skipped_board = (self.repo / "jt-queue" / "board.md").read_text(encoding="utf-8")
        noted = git(self.repo, "show", "task-12:jt-queue/tasks/12/plan.md")
        self.assertEqual(skipped.returncode, 0, skipped.stdout + skipped.stderr)
        self.assertIn("tier: quick", skipped.stdout)
        self.assertIn("repo-review: skip", skipped.stdout)
        self.assertNotIn("repo-review: open", skipped.stdout)
        self.assertIn("review: local", skipped_board)
        self.assertIn("a note in the plan, then continue", noted.stdout)

    def test_quick_tier_docs_and_style_pass_without_plan(self) -> None:
        (self.repo / "jt-queue" / "board.md").write_text(
            board_text("- [ ] **12** readme (docs)", test=gate.NO_SUITE),
            encoding="utf-8",
        )
        commit_all(self.repo, "docs: set docs card")
        self._advance_card()
        git(self.repo, "checkout", "task-12")
        (self.repo / "README.md").write_text("# Docs\n", encoding="utf-8")
        commit_all(self.repo, "docs: add readme")
        git(self.repo, "checkout", "main")
        res_docs = run_gate(self.repo, "reach-review", "--id", "12")
        self.assertEqual(res_docs.returncode, 0, res_docs.stdout + res_docs.stderr)
        self.assertIn("tier: quick", res_docs.stdout)
        self.assertIn("repo-review: skip", res_docs.stdout)
        self.assertIn("size: medium", res_docs.stdout)
        self.assertIn("ai-review: skip", res_docs.stdout)

        (self.repo / "jt-queue" / "board.md").write_text(
            board_text("- [ ] **12** format (style)", test=gate.NO_SUITE),
            encoding="utf-8",
        )
        commit_all(self.repo, "docs: set style card")
        git(self.repo, "branch", "-D", "task-12")
        git(self.repo, "branch", "task-12")
        git(self.repo, "checkout", "task-12")
        (self.repo / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
        commit_all(self.repo, "style: format app")
        git(self.repo, "checkout", "main")
        res_style = run_gate(self.repo, "reach-review", "--id", "12")
        self.assertEqual(res_style.returncode, 0, res_style.stdout + res_style.stderr)
        self.assertIn("tier: quick", res_style.stdout)
        self.assertIn("repo-review: skip", res_style.stdout)
        self.assertIn("ai-review: skip", res_style.stdout)

    def test_adaptive_gate_escalates_to_standard_tier(self) -> None:
        for path in ("requirements.txt", "docs/conf.py"):
            (self.repo / "jt-queue" / "board.md").write_text(
                board_text(f"- [ ] **12** note {path} (docs)", test=gate.NO_SUITE),
                encoding="utf-8",
            )
            commit_all(self.repo, f"docs: board for {path}")
            git(self.repo, "branch", "-D", "task-12")
            git(self.repo, "branch", "task-12")
            git(self.repo, "checkout", "task-12")
            target = self.repo / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("x = 1\n", encoding="utf-8")
            commit_all(self.repo, f"docs: touch {path}")
            git(self.repo, "checkout", "main")
            res = run_gate(self.repo, "reach-review", "--id", "12")
            self.assertNotEqual(res.returncode, 0, path)
            self.assertIn("refused: review-diff", res.stdout, path)

        # feat card with docs: commit -> Standard and refused: review-diff without review
        (self.repo / "jt-queue" / "board.md").write_text(
            board_text("- [ ] **12** feature (feat)", test=gate.NO_SUITE),
            encoding="utf-8",
        )
        commit_all(self.repo, "docs: set feat card")
        git(self.repo, "branch", "-D", "task-12")
        git(self.repo, "branch", "task-12")
        git(self.repo, "checkout", "task-12")
        (self.repo / "README.md").write_text("# Sneaky\n", encoding="utf-8")
        commit_all(self.repo, "docs: sneaky commit on feat card")
        git(self.repo, "checkout", "main")
        res_feat_docs = run_gate(self.repo, "reach-review", "--id", "12")
        self.assertNotEqual(res_feat_docs.returncode, 0)
        self.assertIn("refused: review-diff", res_feat_docs.stdout)

        # feat card modified to (style) after branching -> still Standard
        (self.repo / "jt-queue" / "board.md").write_text(
            board_text("- [ ] **12** feature two (feat)", test=gate.NO_SUITE),
            encoding="utf-8",
        )
        commit_all(self.repo, "docs: feat at branch point")
        git(self.repo, "branch", "-D", "task-12")
        git(self.repo, "branch", "task-12")
        git(self.repo, "checkout", "task-12")
        (self.repo / "app.py").write_text("X = 2\n", encoding="utf-8")
        commit_all(self.repo, "style: try to downgrade tier")
        git(self.repo, "checkout", "main")
        (self.repo / "jt-queue" / "board.md").write_text(
            board_text("- [ ] **12** feature two (style)", test=gate.NO_SUITE),
            encoding="utf-8",
        )
        res_mutated = run_gate(self.repo, "reach-review", "--id", "12")
        self.assertNotEqual(res_mutated.returncode, 0)
        self.assertIn("refused: review-diff", res_mutated.stdout)

        # docs card with screen: yes -> Standard
        (self.repo / "jt-queue" / "board.md").write_text(
            board_text("- [ ] **12** docs screen (docs)", test=gate.NO_SUITE),
            encoding="utf-8",
        )
        (self.repo / "jt-queue" / "tasks" / "12" / "task.md").write_text(
            card_body(["README.md"], kind="docs", screen=True),
            encoding="utf-8",
        )
        commit_all(self.repo, "docs: docs card with screen")
        git(self.repo, "branch", "-D", "task-12")
        git(self.repo, "branch", "task-12")
        git(self.repo, "checkout", "task-12")
        (self.repo / "README.md").write_text("# Screen Docs\n", encoding="utf-8")
        commit_all(self.repo, "docs: update readme")
        git(self.repo, "checkout", "main")
        self.assertEqual(
            gate.card_tier(
                self.repo,
                "main",
                "12",
                (self.repo / "jt-queue" / "tasks" / "12" / "task.md").read_text(encoding="utf-8"),
            ),
            "standard",
        )
        res_screen_docs = run_gate(self.repo, "reach-review", "--id", "12")
        self.assertNotEqual(res_screen_docs.returncode, 0)
        self.assertIn("refused: review-diff", res_screen_docs.stdout)

    def test_outside_files_and_style_changes_are_reported_without_refusal(self) -> None:
        # 1. Card touching file outside files: still passes and prints outside-files:
        (self.repo / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
        (self.repo / "jt-queue" / "board.md").write_text(
            board_text("- [ ] **12** format (style)", test=gate.NO_SUITE),
            encoding="utf-8",
        )
        (self.repo / "jt-queue" / "tasks" / "12" / "task.md").write_text(
            card_body(["app.py"], kind="style"),
            encoding="utf-8",
        )
        commit_all(self.repo, "docs: setup style card")
        git(self.repo, "branch", "-D", "task-12")
        git(self.repo, "branch", "task-12")
        git(self.repo, "checkout", "task-12")
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
        git(self.repo, "checkout", "task-12")
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
        (self.repo / "jt-queue" / "tasks" / "12" / "task.md").write_text(
            card_body([], kind="style"),
            encoding="utf-8",
        )
        res_empty = run_gate(self.repo, "reach-review", "--id", "12")
        self.assertEqual(res_empty.returncode, 0, res_empty.stdout + res_empty.stderr)
        self.assertNotIn("outside-files:", res_empty.stdout)

    def test_plan_note_on_a_code_commit_cannot_reach_review(self) -> None:
        (self.repo / "jt-queue" / "board.md").write_text(
            board_text("- [ ] **12** note (chore)", test=gate.NO_SUITE),
            encoding="utf-8",
        )
        commit_all(self.repo, "docs: mark the chore")
        self._advance_card()
        plan = self.repo / "jt-queue" / "tasks" / "12"
        plan.mkdir(parents=True, exist_ok=True)
        (plan / "plan.md").write_text("a note in the plan, then continue\n", encoding="utf-8")
        self._commit_on_card("chore: note the plan")
        before = (self.repo / "jt-queue" / "board.md").read_text(encoding="utf-8")
        result = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        after = (self.repo / "jt-queue" / "board.md").read_text(encoding="utf-8")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refused: review-diff", result.stdout)
        self.assertIn("merge: no", result.stdout)
        self.assertEqual(after, before)
        self.assertNotIn("review:", after)
        noted = git(self.repo, "show", "task-12:jt-queue/tasks/12/plan.md")
        self.assertIn("a note in the plan, then continue", noted.stdout)

    def _screen(self, kind: str, browser: str, start: str, port: str, click: str) -> None:
        (self.repo / "jt-queue" / "board.md").write_text(
            board_text(f"- [ ] **12** screen ({kind})", browser=browser),
            encoding="utf-8",
        )
        (self.repo / "jt-queue" / "tasks" / "12" / "task.md").write_text(
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
        before = (self.repo / "jt-queue" / "board.md").read_text(encoding="utf-8")
        result = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        after = (self.repo / "jt-queue" / "board.md").read_text(encoding="utf-8")
        loop = (REPO / "skills" / "jt-work" / "references" / "contract.md").read_text(encoding="utf-8")
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
        before = (self.repo / "jt-queue" / "board.md").read_text(encoding="utf-8")
        result = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        after = (self.repo / "jt-queue" / "board.md").read_text(encoding="utf-8")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refused: start-down", result.stdout)
        self.assertIn("next: ask", result.stdout)
        self.assertEqual(after, before)
        self.assertNotIn("review:", after)
        self.assertIn("start-down", GATE_PATH.read_text(encoding="utf-8"))
        loop = (REPO / "skills" / "jt-work" / "references" / "contract.md").read_text(encoding="utf-8")
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
        before = (self.repo / "jt-queue" / "board.md").read_text(encoding="utf-8")
        result = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        after = (self.repo / "jt-queue" / "board.md").read_text(encoding="utf-8")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("refused: click-mismatch", result.stdout)
        self.assertIn("next: ask", result.stdout)
        self.assertEqual(after, before)
        self.assertNotIn("review:", after)
        self.assertIn("click-mismatch", GATE_PATH.read_text(encoding="utf-8"))
        loop = (REPO / "skills" / "jt-work" / "references" / "contract.md").read_text(encoding="utf-8")
        self.assertNotIn("click-mismatch", loop)
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and port_open(port):
            time.sleep(0.05)
        self.assertFalse(port_open(port))

    def test_screen_start_failure_keeps_its_output_in_a_log(self) -> None:
        self._screen(
            "build",
            "playwright",
            "python3 -c 'import sys; print(\"BOOM_START\"); sys.exit(3)'",
            str(free_port()),
            "python3 -c 'print(1)'",
        )
        result = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        self.assertIn("refused: start-down", result.stdout)
        self.assertIn("start exited with code 3", result.stdout)
        self.assertIn("BOOM_START", result.stdout)
        self.assertIn("hint:", result.stdout)
        log_line = next(line for line in result.stdout.splitlines() if line.startswith("log: "))
        self.assertIn("BOOM_START", Path(log_line[len("log: "):]).read_text(encoding="utf-8"))

    def test_screen_click_failure_keeps_its_output_in_a_log(self) -> None:
        port = free_port()
        self._screen(
            "refactor",
            "playwright",
            f"python3 -m http.server {port}",
            str(port),
            "python3 -c 'import sys; print(\"BOOM_CLICK\"); sys.exit(1)'",
        )
        result = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        self.assertIn("refused: click-mismatch", result.stdout)
        self.assertIn("BOOM_CLICK", result.stdout)
        self.assertIn("click exited with code 1", result.stdout)
        self.assertIn("hint:", result.stdout)
        log_line = next(line for line in result.stdout.splitlines() if line.startswith("log: "))
        self.assertIn("BOOM_CLICK", Path(log_line[len("log: "):]).read_text(encoding="utf-8"))

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
        board = (self.repo / "jt-queue" / "board.md").read_text(encoding="utf-8")
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
        (self.repo / "jt-queue" / "board.md").write_text(
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
        (self.repo / "jt-queue" / "board.md").write_text(
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
        (self.repo / "jt-queue" / "board.md").write_text(
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
        (self.repo / "jt-queue" / "board.md").write_text(
            board_text(
                "- [ ] **12** fresh (feat)",
                test="python3 -c 'import os, sys; sys.exit(0 if os.path.exists(\"dep.txt\") else 1)'",
                setup="python3 -c 'open(\"dep.txt\", \"w\").write(\"ok\")'",
            ),
            encoding="utf-8",
        )
        commit_all(self.repo, "docs: add setup cmd")
        git(self.repo, "checkout", "task-12")
        (self.repo / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
        commit_all(self.repo, "feat: add the app")
        git(self.repo, "checkout", "main")
        self._record_review("12")
        result = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("allowed", result.stdout)

    def test_node_modules_bin_in_path_in_worktree(self) -> None:
        git(self.repo, "checkout", "task-12")
        bin_dir = self.repo / "node_modules" / ".bin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        tool = bin_dir / "my-checker"
        tool.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        tool.chmod(0o755)
        commit_all(self.repo, "chore: add bin tool")
        git(self.repo, "checkout", "main")
        (self.repo / "jt-queue" / "board.md").write_text(
            board_text("- [ ] **12** fresh (feat)", test="my-checker"),
            encoding="utf-8",
        )
        commit_all(self.repo, "docs: add test cmd")
        self._record_review("12")
        result = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("allowed", result.stdout)

    def test_no_review_section_refuses_reach_review(self) -> None:
        git(self.repo, "checkout", "task-12")
        (self.repo / "check.py").write_text("import sys\nsys.exit(0)\n# new code\n", encoding="utf-8")
        commit_all(self.repo, "feat: implement feature")
        git(self.repo, "checkout", "main")
        result = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refused: review-diff", result.stdout)
        self.assertIn("detail: no-review", result.stdout)

    def test_stale_review_section_refuses_reach_review(self) -> None:
        git(self.repo, "checkout", "task-12")
        (self.repo / "check.py").write_text("import sys\nsys.exit(0)\n# first\n", encoding="utf-8")
        commit_all(self.repo, "feat: first change")
        git(self.repo, "checkout", "main")
        self._record_review("12")
        git(self.repo, "checkout", "task-12")
        (self.repo / "check.py").write_text("import sys\nsys.exit(0)\n# second\n", encoding="utf-8")
        commit_all(self.repo, "feat: second change")
        git(self.repo, "checkout", "main")
        result = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refused: review-diff", result.stdout)
        self.assertIn("detail: stale-review", result.stdout)

    def _write_plan(self, card_id: str, sha: str, decision: str = "") -> None:
        git(self.repo, "checkout", f"task-{card_id}")
        plan_dir = self.repo / "jt-queue" / "tasks" / card_id
        plan_dir.mkdir(parents=True, exist_ok=True)
        row = ""
        if decision:
            row = (
                "\n## decisions\n\n| decision | why | evidence |\n|---|---|---|\n"
                f"| {decision} |\n"
            )
        (plan_dir / "plan.md").write_text(
            with_ai_review(
                f"# Plan {card_id}\n\n## evidence\n\n| HEADER_TOKEN | check | ok |\n\n## review-diff\n\n- commit: {sha}\n"
                f"- reviewer: reviewer\n- verdict: pass\n- checked: scope\n{row}"
            ),
            encoding="utf-8",
        )
        commit_all(self.repo, "docs: record review")
        git(self.repo, "checkout", "main")

    def _topic_cards(self, refs: list[str] | None) -> None:
        (self.repo / "jt-queue" / "board.md").write_text(
            board_text("- [ ] **12** one (fix)\n- [ ] **13** two (fix)"),
            encoding="utf-8",
        )
        (self.repo / "jt-queue" / "tasks" / "12" / "task.md").write_text(
            card_body(["app.py"], topic="login", refs=refs),
            encoding="utf-8",
        )
        (self.repo / "jt-queue" / "tasks" / "13").mkdir(parents=True, exist_ok=True)
        (self.repo / "jt-queue" / "tasks" / "13" / "task.md").write_text(
            card_body(["src/b.py"], topic="login", refs=["12"] if refs else None),
            encoding="utf-8",
        )
        commit_all(self.repo, "docs: add the related cards")

    def test_added_checker_the_card_did_not_ask_for_cannot_reach_review(self) -> None:
        git(self.repo, "checkout", "task-12")
        (self.repo / "check_once.py").write_text("print('once')\n", encoding="utf-8")
        commit_all(self.repo, "fix: add a one-off checker")
        sha = git(self.repo, "rev-parse", "HEAD").stdout.strip()
        git(self.repo, "checkout", "main")
        self._write_plan("12", sha)
        before = (self.repo / "jt-queue" / "board.md").read_text(encoding="utf-8")
        result = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        after = (self.repo / "jt-queue" / "board.md").read_text(encoding="utf-8")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refused: one-off-checker", result.stdout)
        self.assertIn("merge: no", result.stdout)
        self.assertNotIn("next: ask", result.stdout)
        self.assertEqual(after, before)
        self.assertNotIn("review:", after)

    def test_checker_the_card_asked_for_can_reach_review(self) -> None:
        (self.repo / "jt-queue" / "tasks" / "12" / "task.md").write_text(
            card_body(["check_once.py"], do="create check_once.py"),
            encoding="utf-8",
        )
        commit_all(self.repo, "docs: the card asks for the checker")
        git(self.repo, "checkout", "task-12")
        git(self.repo, "merge", "main")
        (self.repo / "check_once.py").write_text("print('once')\n", encoding="utf-8")
        commit_all(self.repo, "fix: add the checker the card asked for")
        sha = git(self.repo, "rev-parse", "HEAD").stdout.strip()
        git(self.repo, "checkout", "main")
        self._write_plan("12", sha)
        result = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        board = (self.repo / "jt-queue" / "board.md").read_text(encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("review: local", board)
        self.assertNotIn("merge:", board)

    def test_checkout_module_is_not_a_one_off_checker(self) -> None:
        git(self.repo, "checkout", "task-12")
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
        before = (self.repo / "jt-queue" / "board.md").read_text(encoding="utf-8")
        result = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        after = (self.repo / "jt-queue" / "board.md").read_text(encoding="utf-8")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refused: related", result.stdout)
        self.assertIn("next: ask", result.stdout)
        self.assertIn("merge: no", result.stdout)
        self.assertEqual(after, before)
        self.assertNotIn("review:", after)

    def test_same_topic_linked_cards_can_reach_review_without_rule_update(self) -> None:
        self._topic_cards(["13"])
        git(self.repo, "checkout", "task-12")
        git(self.repo, "merge", "main")
        (self.repo / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
        commit_all(self.repo, "fix: patch only this card")
        sha = git(self.repo, "rev-parse", "HEAD").stdout.strip()
        git(self.repo, "checkout", "main")
        self._write_plan("12", sha)
        result = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        board = (self.repo / "jt-queue" / "board.md").read_text(encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("allowed", result.stdout)
        self.assertIn("review: local", board)
        self.assertNotIn("merge:", board)

    def test_a_single_topic_can_patch_code_without_a_rule_row(self) -> None:
        (self.repo / "jt-queue" / "tasks" / "12" / "task.md").write_text(
            card_body(["check.py"], topic="login"),
            encoding="utf-8",
        )
        commit_all(self.repo, "docs: classify the only card")
        self._set_card_check("0")
        result = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        board = (self.repo / "jt-queue" / "board.md").read_text(encoding="utf-8")
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
        (self.repo / "jt-queue" / "tasks" / "12").mkdir(parents=True)
        (self.repo / "check.py").write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
        (self.repo / "jt-queue" / "board.md").write_text(
            board_text("- [ ] **12** fresh (feat)"),
            encoding="utf-8",
        )
        (self.repo / "jt-queue" / "tasks" / "12" / "task.md").write_text(
            card_body(["check.py"]),
            encoding="utf-8",
        )
        commit_all(self.repo, "docs: add the board")
        git(self.repo, "branch", "task-12")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _record_review(self) -> None:
        git(self.repo, "checkout", "task-12")
        head = git(self.repo, "rev-parse", "HEAD").stdout.strip()
        plan_dir = self.repo / "jt-queue" / "tasks" / "12"
        plan_dir.mkdir(parents=True, exist_ok=True)
        (plan_dir / "plan.md").write_text(
            with_ai_review(
                f"# Plan 12\n\n## evidence\n\n| HEADER_TOKEN | check | ok |\n\n## review-diff\n\n- commit: {head}\n- reviewer: reviewer\n- verdict: pass\n- checked: scope\n"
            ),
            encoding="utf-8",
        )
        commit_all(self.repo, "docs: record review")
        git(self.repo, "checkout", "main")

    def _commit_check(self, code: str) -> None:
        git(self.repo, "checkout", "task-12")
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
        return (self.repo / "jt-queue" / "board.md").read_text(encoding="utf-8")

    def test_classify_open_prs_names_the_draft_or_the_refusal(self) -> None:
        head = "task-12"
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
        other_head = {**draft, "headRefName": "task-9"}
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
            '"headRefName":"task-12","baseRefName":"main"}]'
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

    def test_slug_branch_draft_writes_the_url(self) -> None:
        self._commit_check("0")
        git(self.repo, "branch", "-m", "task-12", "task-12-fresh-start")
        self._origin()
        payload = (
            '[{"url":"https://example.invalid/pull/8","isDraft":true,'
            '"headRefName":"task-12-fresh-start","baseRefName":"main"}]'
        )
        result = run_gate(self.repo, "reach-review", "--id", "12", "--write", env=self._json_gh(payload))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("review: https://example.invalid/pull/8", self._board())

    def test_ready_pull_request_is_not_review(self) -> None:
        self._commit_check("0")
        self._origin()
        payload = (
            '[{"url":"https://example.invalid/pull/7","isDraft":false,'
            '"headRefName":"task-12","baseRefName":"main"}]'
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
            '"headRefName":"task-12","baseRefName":"main"}'
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
        self.assertEqual(decision.action, "do-task")
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
        (self.repo / "jt-queue" / "tasks" / "12").mkdir(parents=True)
        (self.repo / "check.py").write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
        (self.repo / "jt-queue" / "board.md").write_text(
            board_text("- [ ] **12** fresh (feat) review: local"),
            encoding="utf-8",
        )
        (self.repo / "jt-queue" / "tasks" / "12" / "task.md").write_text(
            card_body(["app.py"]),
            encoding="utf-8",
        )
        commit_all(self.repo, "docs: add the board")
        git(self.repo, "branch", "task-12")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _diverge(self) -> None:
        git(self.repo, "checkout", "task-12")
        (self.repo / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
        commit_all(self.repo, "feat: card work")
        git(self.repo, "checkout", "main")

    def test_squash_merged_pr_is_landed_when_not_ancestor(self) -> None:
        self._diverge()
        ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor", "task-12", "main"],
            cwd=self.repo,
            capture_output=True,
        )
        self.assertNotEqual(ancestor.returncode, 0)
        before = (self.repo / "jt-queue" / "board.md").read_text(encoding="utf-8")
        env = _git_bin_env(
            self.repo,
            "bin-squash",
            "#!/bin/sh\nprintf '%s\\n' '{\"state\":\"MERGED\",\"headRefName\":\"task-12\"}'\n",
        )
        result = run_gate_env(self.repo, env, "landed", "--id", "12")
        after = (self.repo / "jt-queue" / "board.md").read_text(encoding="utf-8")
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
            "#!/bin/sh\nprintf '%s\\n' '{\"state\":\"OPEN\",\"headRefName\":\"task-12\"}'\n",
        )
        result = run_gate_env(self.repo, env, "landed", "--id", "12")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refused: not-landed", result.stdout)
        self.assertIn("detail: pr-open", result.stdout)
        self.assertIn("merge: no", result.stdout)

    def test_ancestor_lands_without_calling_gh(self) -> None:
        self._diverge()
        git(self.repo, "merge", "--no-ff", "task-12", "-m", "merge card")
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
printf '%s\\n' '[{"state":"MERGED","headRefName":"task-12"}]'
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
            "jt-queue/bin-hang",
            "#!/bin/sh\n/bin/sleep 5\n",
        )
        hang_env["JT_GH_TIMEOUT"] = "0.2"
        hung = run_gate_env(self.repo, hang_env, "next")
        self.assertEqual(hung.returncode, 0, hung.stdout + hung.stderr)
        self.assertIn("action: wait", hung.stdout)
        self.assertIn("reason: review", hung.stdout)
        self.assertNotIn("landed-waiting:", hung.stdout)

        # 3. Ancestor merged -> next prints landed-waiting: 12 and does not modify board.md
        git(self.repo, "merge", "--no-ff", "task-12", "-m", "merge task-12")
        before = (self.repo / "jt-queue" / "board.md").read_text(encoding="utf-8")
        merged = run_gate(self.repo, "next")
        after = (self.repo / "jt-queue" / "board.md").read_text(encoding="utf-8")
        self.assertEqual(merged.returncode, 0, merged.stdout + merged.stderr)
        self.assertIn("landed-waiting: 12", merged.stdout)
        self.assertEqual(after, before)

    def test_next_reports_landed_waiting_for_squash_merged_pr(self) -> None:
        self._diverge()
        git(self.repo, "remote", "add", "origin", "https://example.com/repo.git")
        script = """#!/bin/sh
case "$*" in
  *"--state merged"*"--limit"*)
    printf '%s\\n' '[{"state":"MERGED","headRefName":"task-12"}]' ;;
  *) printf '%s\\n' '[]' ;;
esac
exit 0
"""
        env = _git_bin_env(self.repo, "jt-queue/bin-squash", script)
        result = run_gate_env(self.repo, env, "next")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("landed-waiting: 12", result.stdout)


class DiffCheckTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        init_repo(self.repo)
        (self.repo / "jt-queue" / "tasks" / "12").mkdir(parents=True)
        (self.repo / "check.py").write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
        (self.repo / "jt-queue" / "board.md").write_text(
            board_text("- [ ] **12** fresh (feat)", test=gate.NO_SUITE),
            encoding="utf-8",
        )
        (self.repo / "jt-queue" / "tasks" / "12" / "task.md").write_text(
            card_body(["app.py"]),
            encoding="utf-8",
        )
        commit_all(self.repo, "docs: add the board")
        git(self.repo, "branch", "task-12")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _commit_code(self) -> str:
        git(self.repo, "checkout", "task-12")
        (self.repo / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
        commit_all(self.repo, "feat: card work")
        sha = git(self.repo, "rev-parse", "HEAD").stdout.strip()
        git(self.repo, "checkout", "main")
        return sha

    def _write_plan(self, body: str) -> None:
        git(self.repo, "checkout", "task-12")
        plan = self.repo / "jt-queue" / "tasks" / "12"
        plan.mkdir(parents=True, exist_ok=True)
        (plan / "plan.md").write_text(with_ai_review(body), encoding="utf-8")
        commit_all(self.repo, "docs: record review")
        git(self.repo, "checkout", "main")

    def test_docs_only_range_skips(self) -> None:
        result = run_diff_check(self.repo)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("diff-check: skip", result.stdout)

    def test_matching_sha_exits_zero(self) -> None:
        sha = self._commit_code()
        self._write_plan(
            f"# Plan 12\n\n## evidence\n\n| HEADER_TOKEN | check | ok |\n\n## review-diff\n\n- commit: {sha}\n- reviewer: reviewer\n- verdict: pass\n- checked: scope\n"
        )
        result = run_diff_check(self.repo)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(), "diff-check: ok")

    def _plan_with(self, sha: str, review: str, evidence: str = "| HEADER_TOKEN | check | ok |") -> None:
        self._write_plan(
            f"# Plan 12\n\n## evidence\n\n{evidence}\n\n## review-diff\n\nsha: {sha}\n{review}"
        )

    def test_review_needs_a_pass_verdict_and_a_checked_line(self) -> None:
        sha = self._commit_code()
        cases = {
            "no-verdict": "checked: scope\n",
            "review-fix-needed": "verdict: fix-needed\nchecked: scope\n",
            "no-checked": "verdict: pass\n",
        }
        for status, review in cases.items():
            with self.subTest(status):
                self._plan_with(sha, review)
                result = run_diff_check(self.repo)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(f"diff-check: {status}", result.stdout)

    def test_the_unfilled_template_verdict_does_not_pass(self) -> None:
        sha = self._commit_code()
        self._plan_with(sha, "verdict: pass | fix-needed\nchecked: scope\n")
        result = run_diff_check(self.repo)
        self.assertIn("diff-check: no-verdict", result.stdout)

    def test_every_pass_line_needs_an_evidence_row(self) -> None:
        sha = self._commit_code()
        self._plan_with(sha, "verdict: pass\nchecked: scope\n", evidence="| something else | x | ok |")
        result = run_diff_check(self.repo)
        self.assertIn("diff-check: evidence-missing", result.stdout)
        refused = run_gate(self.repo, "reach-review", "--id", "12")
        self.assertIn("refused: review-diff", refused.stdout)
        self.assertIn("evidence-missing", refused.stdout)
        self.assertIn("HEADER_TOKEN", refused.stdout)
        hint = next(line for line in refused.stdout.splitlines() if line.startswith("hint:"))
        self.assertIn("## evidence", hint)
        self._plan_with(sha, "verdict: pass\nchecked: scope\n", evidence="| `header_token` | run | ok |")
        self.assertEqual(run_diff_check(self.repo).returncode, 0)

    def test_evidence_must_be_a_filled_table_row_quoting_the_pass_line(self) -> None:
        sha = self._commit_code()
        review = "verdict: pass\nchecked: scope\n"
        bad = {
            "prose only": "HEADER_TOKEN passed, trust me",
            "empty cells": "| HEADER_TOKEN | | |",
            "wrong column": "| note | HEADER_TOKEN | ok |",
        }
        for name, evidence in bad.items():
            with self.subTest(name):
                self._plan_with(sha, review, evidence=evidence)
                self.assertIn("diff-check: evidence-missing", run_diff_check(self.repo).stdout)

    def test_pass_line_with_a_pipe_matches_when_the_pipe_is_escaped(self) -> None:
        (self.repo / "jt-queue" / "tasks" / "12" / "task.md").write_text(
            card_body(["app.py"], header="a | b works"), encoding="utf-8"
        )
        commit_all(self.repo, "docs: a pass line with a pipe")
        sha = self._commit_code()
        self._plan_with(sha, "verdict: pass\nchecked: scope\n", evidence="| a \\| b works | run | ok |")
        self.assertEqual(run_diff_check(self.repo).returncode, 0)

    def test_template_verdict_line_is_ignored_next_to_a_real_one(self) -> None:
        sha = self._commit_code()
        self._plan_with(sha, "verdict: pass | fix-needed\nverdict: pass.\nchecked: scope\n")
        self.assertEqual(run_diff_check(self.repo).returncode, 0)

    def test_no_verdict_refusal_shows_what_was_found(self) -> None:
        sha = self._commit_code()
        self._plan_with(sha, "verdict: looks good\nchecked: scope\n")
        refused = run_gate(self.repo, "reach-review", "--id", "12")
        self.assertIn("no-verdict", refused.stdout)
        self.assertIn("'looks good'", refused.stdout)

    def test_needs_is_printed_but_never_blocks_review(self) -> None:
        (self.repo / "jt-queue" / "tasks" / "12" / "task.md").write_text(
            card_body(["app.py"]).replace(
                "refs:\n", "needs:\n- be-repo POST /login merged\n- be-repo schema v2\n\nrefs:\n"
            ),
            encoding="utf-8",
        )
        commit_all(self.repo, "docs: the task needs the backend")
        sha = self._commit_code()
        self._plan_with(sha, "verdict: pass\nchecked: scope\n")
        self.assertEqual(gate.parse_needs((self.repo / "jt-queue/tasks/12/task.md").read_text(encoding="utf-8")),
                         ["be-repo POST /login merged", "be-repo schema v2"])
        result = run_gate(self.repo, "reach-review", "--id", "12")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("needs: be-repo POST /login merged; be-repo schema v2", result.stdout)

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
            "# Plan 12\n\n## evidence\n\n| HEADER_TOKEN | check | ok |\n\n## review-diff\n\n- commit: "
            "0123456789abcdef0123456789abcdef01234567\n"
        )
        result = run_diff_check(self.repo)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("diff-check: stale-review", result.stdout)

    def test_dirty_card_worktree_exits_nonzero(self) -> None:
        sha = self._commit_code()
        self._write_plan(
            f"# Plan 12\n\n## evidence\n\n| HEADER_TOKEN | check | ok |\n\n## review-diff\n\n- commit: {sha}\n- reviewer: reviewer\n- verdict: pass\n- checked: scope\n"
        )
        git(self.repo, "checkout", "task-12")
        (self.repo / "app.py").write_text("VALUE = 2\n", encoding="utf-8")
        result = run_diff_check(self.repo)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("diff-check: stale-review", result.stdout)

    def test_heading_alone_cannot_reach_review(self) -> None:
        self._commit_code()
        self._write_plan("# Plan 12\n\n## review-diff\n\nnote only\n")
        before = (self.repo / "jt-queue" / "board.md").read_text(encoding="utf-8")
        result = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        after = (self.repo / "jt-queue" / "board.md").read_text(encoding="utf-8")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refused: review-diff", result.stdout)
        self.assertIn("detail: no-sha", result.stdout)
        self.assertIn("merge: no", result.stdout)
        self.assertEqual(after, before)
        self.assertNotIn("review:", after)

    def test_copied_skill_folder_without_root_scripts_passes_reach_review(self) -> None:
        sha = self._commit_code()
        self._write_plan(
            f"# Plan 12\n\n## evidence\n\n| HEADER_TOKEN | check | ok |\n\n## review-diff\n\n- commit: {sha}\n- reviewer: reviewer\n- verdict: pass\n- checked: scope\n"
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
            board = (self.repo / "jt-queue" / "board.md").read_text(encoding="utf-8")
            self.assertIn("review: local", board)


class StatusBoundaryTests(unittest.TestCase):
    def test_unknown_status_stops_instead_of_starting_work(self) -> None:
        # The second token is not a status word. It stays misspelled so the gate rejects it.
        for token in ("wip:", "reveiw:", "รอรีวิว:", "ปิด:", "closed:"):  # spellchecker:disable-line
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
        self.assertNotEqual(decision.action, "do-task")

    def test_title_colon_words_stay_ready_and_can_be_marked_review(self) -> None:
        for name in ("task: login", "backdrop: night", "incomplete: form", "mask: login"):
            line = f"- [ ] **12** {name} (feat)"
            text = board_text(line)
            parsed = gate.parse_board(text)
            self.assertEqual(len(parsed.cards), 1, name)
            self.assertIsNone(parsed.cards[0].status, name)
            decision = decide_board(text, {"12": card_body(["src/a.py"])})
            self.assertEqual(decision.action, "do-task", name)
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
        self.assertEqual(decision.action, "do-task")
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
        self.assertNotEqual(decision.action, "do-task")

    def test_review_link_may_contain_merge_colon(self) -> None:
        text = board_text("- [ ] **12** fresh (feat)")
        link = "https://example.com/merge:1"
        updated = gate.apply_waiting_review(text, "12", 0, link)
        self.assertIn("review: https://example.com/merge:1", updated)

    def test_capitalized_section_heading_is_still_the_queue(self) -> None:
        text = board_text("- [ ] **12** fresh (feat)").replace("## first\n", "## First\n", 1)
        decision = decide_board(text, {"12": card_body(["src/a.py"])})
        self.assertEqual(decision.action, "do-task")
        self.assertEqual(decision.id, "12")
        self.assertEqual(decision.reason, "ready")

    def test_legacy_board_with_pair_line_is_ignored(self) -> None:
        text = board_text("- [ ] **12** mask: login · side-repo (feat)", pair="side-repo")
        decision = decide_board(text, {"12": card_body(["src/a.py"])})
        self.assertEqual(decision.action, "do-task")
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


class RoundCounterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        init_repo(self.repo)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_every_failure_counts_and_reset_starts_over(self) -> None:
        self.assertEqual([gate.count_round(self.repo, "7") for _ in range(3)], [1, 2, 3])
        gate.reset_rounds(self.repo, "7")
        self.assertEqual(gate.count_round(self.repo, "7"), 1)

    def test_next_forgets_tasks_closed_on_the_board(self) -> None:
        gate.count_round(self.repo, "7")
        gate.count_round(self.repo, "8")
        (self.repo / "jt-queue").mkdir(exist_ok=True)
        (self.repo / "jt-queue" / "board.md").write_text(
            board_text("- [x] **7** done (feat) merge:\n- [ ] **8** open (feat)"), encoding="utf-8"
        )
        run_gate_raw(self.repo, "next")
        self.assertEqual(sorted(gate._load_attempts(self.repo)), ["8"])

    def test_parallel_failures_do_not_lose_counts(self) -> None:
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(8) as pool:
            list(pool.map(lambda _: gate.count_round(self.repo, "7"), range(24)))
        self.assertEqual(gate._load_attempts(self.repo)["7"]["count"], 24)


class DetectTests(unittest.TestCase):
    def test_detect_reports_commands_with_their_source_and_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                '{"scripts": {"test": "vitest run"}, "devDependencies": {"vitest": "1"}}',
                encoding="utf-8",
            )
            (root / "pnpm-lock.yaml").write_text("lockfileVersion: 9\n", encoding="utf-8")
            result = run_gate_raw(root, "detect")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("TEST_CMD = vitest run  [source: package.json scripts.test]", result.stdout)
            self.assertIn("SETUP_CMD = pnpm install --frozen-lockfile  [source: pnpm-lock.yaml]", result.stdout)
            self.assertIn("merge: no", result.stdout)
            self.assertEqual(
                sorted(p.name for p in root.iterdir()), ["package.json", "pnpm-lock.yaml"]
            )

    def test_detect_falls_back_to_no_suite_and_an_empty_setup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run_gate_raw(Path(tmp), "detect")
            self.assertIn("TEST_CMD = no-suite", result.stdout)
            self.assertIn("SETUP_CMD = (empty)", result.stdout)


class CommandApprovalTests(unittest.TestCase):
    """A human must approve board/card shell commands; later edits must not run silently."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        self.marker = self.repo.parent / f"{self.repo.name}-marker"
        init_repo(self.repo)
        (self.repo / "jt-queue" / "tasks" / "12").mkdir(parents=True)
        (self.repo / "README.md").write_text("hello\n", encoding="utf-8")
        self.board = self.repo / "jt-queue" / "board.md"
        self.board.write_text(
            board_text("- [ ] **12** doc (docs)", test="python3 -c pass"), encoding="utf-8"
        )
        (self.repo / "jt-queue" / "tasks" / "12" / "task.md").write_text(
            card_body(["README.md"], kind="docs"), encoding="utf-8"
        )
        commit_all(self.repo, "docs: board")
        git(self.repo, "branch", "task-12")
        git(self.repo, "checkout", "task-12")
        (self.repo / "README.md").write_text("hello world\n", encoding="utf-8")
        commit_all(self.repo, "docs: card")
        git(self.repo, "checkout", "main")

    def tearDown(self) -> None:
        self.marker.unlink(missing_ok=True)
        self.tmp.cleanup()

    def _tamper(self, commit: bool) -> None:
        self.board.write_text(
            self.board.read_text(encoding="utf-8").replace(
                "python3 -c pass", f"touch {self.marker}"
            ),
            encoding="utf-8",
        )
        if commit:
            commit_all(self.repo, "docs: sneaky board edit")

    def test_unapproved_commands_are_refused_and_not_run(self) -> None:
        self._tamper(commit=False)
        result = run_gate_raw(self.repo, "reach-review", "--id", "12")
        self.assertIn("refused: commands-unapproved", result.stdout)
        self.assertIn("next: stop", result.stdout)
        self.assertFalse(self.marker.exists())

    def test_approved_commands_run(self) -> None:
        self.assertEqual(run_gate_raw(self.repo, "approve-commands", "--id", "12").returncode, 0)
        result = run_gate_raw(self.repo, "reach-review", "--id", "12")
        self.assertIn("allowed", result.stdout, result.stdout + result.stderr)

    def test_edit_after_approval_is_refused_whether_committed_or_not(self) -> None:
        for commit in (False, True):
            with self.subTest(committed=commit):
                git(self.repo, "checkout", "-q", "--", ".")
                run_gate_raw(self.repo, "approve-commands", "--id", "12")
                self._tamper(commit=commit)
                result = run_gate_raw(self.repo, "reach-review", "--id", "12")
                self.assertIn("refused: commands-changed", result.stdout)
                self.assertFalse(self.marker.exists())
                if commit:
                    git(self.repo, "reset", "-q", "--hard", "HEAD~1")

    def test_approval_is_stored_in_git_dir_not_in_the_tree(self) -> None:
        run_gate_raw(self.repo, "approve-commands", "--id", "12")
        self.assertTrue((self.repo / ".git" / "jt-queue" / "approved-commands.json").is_file())
        tracked = git(self.repo, "ls-files").stdout
        self.assertNotIn("approved-commands", tracked)
        self.assertEqual(git(self.repo, "status", "--porcelain").stdout.strip(), "")

    def test_changed_card_screen_commands_are_refused(self) -> None:
        card = self.repo / "jt-queue" / "tasks" / "12" / "task.md"
        card.write_text(
            card_body(["README.md"], kind="docs", screen=True, start="true", port="1", click="true"),
            encoding="utf-8",
        )
        commit_all(self.repo, "docs: screen card")
        run_gate_raw(self.repo, "approve-commands", "--id", "12")
        card.write_text(
            card.read_text(encoding="utf-8").replace("start: true", f"start: touch {self.marker}"),
            encoding="utf-8",
        )
        result = run_gate_raw(self.repo, "screen-check", "--id", "12")
        self.assertIn("refused: commands-changed", result.stdout)
        self.assertFalse(self.marker.exists())

    def test_screen_check_refuses_unapproved_start_even_without_screen_yes_or_via_cli_override(self) -> None:
        card = self.repo / "jt-queue" / "tasks" / "12" / "task.md"
        card.write_text(
            card.read_text(encoding="utf-8") + f"\nstart: touch {self.marker}\nport: 1\n",
            encoding="utf-8",
        )
        res_no_screen_yes = run_gate_raw(self.repo, "screen-check", "--id", "12")
        self.assertIn("refused: commands-unapproved", res_no_screen_yes.stdout)
        self.assertFalse(self.marker.exists())

        run_gate_raw(self.repo, "approve-commands", "--id", "12")
        res_cli_override = run_gate_raw(
            self.repo, "screen-check", "--id", "12", "--start", f"touch {self.marker}.cli"
        )
        self.assertIn("refused: commands-changed", res_cli_override.stdout)
        self.assertFalse((self.marker.parent / f"{self.marker.name}.cli").exists())

    def test_invalid_card_id_is_refused_by_approve(self) -> None:
        result = run_gate_raw(self.repo, "approve-commands", "--id", "../x")
        self.assertIn("refused: invalid-id", result.stdout)


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

    def test_every_refusal_token_has_a_hint_and_every_hint_a_refusal(self) -> None:
        self.assertEqual(set(gate.HINT_FOR), set(gate.NEXT_FOR))
        for token, hint in gate.HINT_FOR.items():
            self.assertTrue(hint.strip(), token)
            self.assertNotIn("\n", hint, token)

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


class IgnoredQueueTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        init_repo(self.repo)
        (self.repo / ".gitignore").write_text("jt-queue/\n", encoding="utf-8")
        (self.repo / "check.py").write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
        commit_all(self.repo, "chore: add the checker")
        git(self.repo, "checkout", "-b", "task-12")
        (self.repo / "check.py").write_text("import sys\nsys.exit(0)\n# card\n", encoding="utf-8")
        commit_all(self.repo, "feat: change the checker")
        self.sha = git(self.repo, "rev-parse", "HEAD").stdout.strip()
        git(self.repo, "checkout", "main")
        queue = self.repo / "jt-queue"
        task = queue / "tasks" / "12"
        task.mkdir(parents=True)
        (queue / "board.md").write_text(
            board_text("- [ ] **12** fresh (feat)", test=gate.NO_SUITE),
            encoding="utf-8",
        )
        (queue / "brief.md").write_text("# Brief\n\nship the checker\n", encoding="utf-8")
        (task / "task.md").write_text(card_body(["check.py"]), encoding="utf-8")
        (task / "plan.md").write_text(
            with_ai_review(
                f"# Plan 12\n\n## evidence\n\n| HEADER_TOKEN | check | ok |\n\n## review-diff\n\n- commit: {self.sha}\n- reviewer: reviewer\n- verdict: pass\n- checked: scope\n"
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_ignored_queue_is_read_from_disk_and_stays_untracked(self) -> None:
        listed = git(self.repo, "status", "--porcelain")
        self.assertNotIn("jt-queue/", listed.stdout)
        nxt = run_gate(self.repo, "next")
        self.assertEqual(nxt.returncode, 0, nxt.stdout + nxt.stderr)
        self.assertIn("action: do-task", nxt.stdout)
        self.assertIn("id: 12", nxt.stdout)
        checked = run_diff_check(self.repo)
        self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
        self.assertIn("diff-check: ok", checked.stdout)
        opened = run_gate(self.repo, "reach-review", "--id", "12", "--write", "--link", "local")
        self.assertEqual(opened.returncode, 0, opened.stdout + opened.stderr)
        self.assertIn("review: local", (self.repo / "jt-queue" / "board.md").read_text(encoding="utf-8"))
        listed_after = git(self.repo, "status", "--porcelain")
        self.assertNotIn("jt-queue/", listed_after.stdout)


def repo_block(name: str, path: str, queue: str = "main", test: str = "npm test", setup: str = "",
               stack: str = "node · express · jest · no ORM", lint: str = "", typecheck: str = "") -> str:
    if path == ".":
        return f"### {name}\npath: .\n"
    return (
        f"### {name}\npath: {path}\nqueue: {queue}\n\n"
        "| Value | In this repo |\n|---|---|\n"
        f"| `<TEST_CMD>` | {test} |\n| `<SETUP_CMD>` | {setup} |\n"
        f"| `<TYPECHECK_CMD>` | {typecheck} |\n| `<LINT_CMD>` | {lint} |\n"
        f"| `<STACK_LOCK>` | {stack} |\n"
    )


TWO_REPOS = repo_block("fe", ".") + "\n" + repo_block("be", "../be")


class ReposParseTests(unittest.TestCase):
    """`## repos` is opt-in; it must never leak into the home repo's fields."""

    def test_blocks_parse_and_keep_pipes_in_commands(self) -> None:
        text = board_text("no items", repos=repo_block("fe", ".") + "\n" + repo_block(
            "be", "../be", test="npm ci || npm test"))
        repos = gate.parse_repos(text)
        self.assertEqual([r.name for r in repos], ["fe", "be"])
        self.assertTrue(repos[0].is_home)
        self.assertEqual(repos[1].path, "../be")
        self.assertEqual(repos[1].queue, "main")
        self.assertEqual(repos[1].values["TEST_CMD"], "npm ci || npm test")

    def test_repos_block_before_home_table_does_not_replace_home_fields(self) -> None:
        repos = repo_block("fe", ".") + repo_block("be", "../be", queue="develop", test="npm test")
        text = "## repos\n\n" + repos + "\n## home\n\n" + board_text("no items")
        board = gate.parse_board(text)
        self.assertEqual(board.queue_branch, "main")
        self.assertEqual(board.test_cmd, "python3 check.py")
        self.assertEqual(board.stack_lock, "py · none · test · ban")

    def test_board_without_repos_keeps_the_v22_command_digest(self) -> None:
        text = board_text("no items", setup="npm ci")
        self.assertEqual(
            gate._board_commands(text), {"TEST_CMD": "python3 check.py", "SETUP_CMD": "npm ci"}
        )
        v22 = gate._digest({"TEST_CMD": "python3 check.py", "SETUP_CMD": "npm ci"})
        self.assertEqual(gate._digest(gate._board_commands(text)), v22)

    def test_nonempty_lint_and_typecheck_join_the_approval_digest(self) -> None:
        plain = board_text("no items", setup="npm ci")
        cmds = gate._board_commands(plain)
        self.assertNotIn("LINT_CMD", cmds)
        self.assertNotIn("TYPECHECK_CMD", cmds)
        with_cmds = board_text("no items", setup="npm ci", lint="ruff check", typecheck="tsc --noEmit")
        hashed = gate._board_commands(with_cmds)
        self.assertEqual(hashed["LINT_CMD"], "ruff check")
        self.assertEqual(hashed["TYPECHECK_CMD"], "tsc --noEmit")
        self.assertNotEqual(gate._digest(hashed), gate._digest(cmds))
        repos = repo_block("fe", ".") + repo_block("be", "../be", lint="ruff check")
        self.assertEqual(
            gate._board_commands(board_text("no items", repos=repos))["repo:be:LINT_CMD"],
            "ruff check",
        )
        lint_only = board_text("no items", test="no-suite", lint="ruff check")
        self.assertTrue(gate._board_runs_commands(gate._board_commands(lint_only)))

    def test_repo_commands_need_approval_even_when_home_runs_nothing(self) -> None:
        text = board_text("no items", test="no-suite", repos=TWO_REPOS)
        self.assertTrue(gate._board_runs_commands(gate._board_commands(text)))

    def test_shape_problems_stop_the_queue(self) -> None:
        cases = {
            "no home": (repo_block("be", "../be") + repo_block("api", "../api"), "home"),
            "only home": (repo_block("fe", "."), "repos"),
            "duplicate": (repo_block("fe", ".") + repo_block("be", "../be") + repo_block("be", "../b2"), "be.duplicate"),
            "bad name": (repo_block("fe", ".") + repo_block("Be", "../be"), "Be.name"),
            "absolute": (repo_block("fe", ".") + repo_block("be", "/srv/be"), "be.path"),
            "home values": (repo_block("fe", ".") + "queue: main\n\n" + repo_block("be", "../be"), "fe.home-values"),
            "status name": (repo_block("fe", ".") + repo_block("merge", "../be"), "merge.name"),
        }
        for label, (repos, field) in cases.items():
            with self.subTest(label):
                decision = decide_board(board_text("no items", repos=repos), {})
                self.assertEqual((decision.action, decision.reason), ("stop", "repo-invalid"))
                self.assertIn(field, decision.fields)

    def test_missing_repo_fields_are_not_ready(self) -> None:
        repos = repo_block("fe", ".") + repo_block("be", "../be", queue="", test="")
        decision = decide_board(board_text("no items", repos=repos), {})
        self.assertEqual(decision.reason, "not-ready")
        self.assertEqual(decision.fields, ("be.queue", "be.TEST_CMD"))

    def test_valid_repos_do_not_change_the_decision(self) -> None:
        decision = decide_board(board_text("no items", repos=TWO_REPOS), {}, brief=True)
        self.assertEqual((decision.action, decision.reason), ("add-task", "no-task"))


class ReposGitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.home = base / "fe"
        self.other = base / "be"
        for repo in (self.home, self.other):
            repo.mkdir()
            init_repo(repo)
            (repo / "README.md").write_text("x\n", encoding="utf-8")
            commit_all(repo, "docs: init")
        (self.home / ".gitignore").write_text("jt-queue/\n", encoding="utf-8")
        commit_all(self.home, "chore: ignore queue")
        (self.home / "jt-queue").mkdir()
        (self.home / "jt-queue" / "brief.md").write_text("# Brief\n", encoding="utf-8")
        self.board = self.home / "jt-queue" / "board.md"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _next(self, repos: str) -> str:
        self.board.write_text(board_text("no items", repos=repos), encoding="utf-8")
        result = run_gate_raw(self.home, "next")
        return result.stdout + result.stderr

    def test_present_repo_lets_the_queue_continue(self) -> None:
        out = self._next(TWO_REPOS)
        self.assertIn("action: add-task", out)

    def test_missing_repo_stops_with_its_name(self) -> None:
        out = self._next(repo_block("fe", ".") + repo_block("be", "../nowhere"))
        self.assertIn("action: stop", out)
        self.assertIn("reason: repo-missing", out)
        self.assertIn("fields: be", out)

    def test_path_into_home_or_a_subfolder_is_invalid(self) -> None:
        (self.other / "sub").mkdir()
        for path in ("../fe", "../be/sub"):
            with self.subTest(path):
                out = self._next(repo_block("fe", ".") + repo_block("be", path))
                self.assertIn("reason: repo-invalid", out)
                self.assertIn("fields: be.path", out)

    def test_two_rows_for_one_repo_are_invalid(self) -> None:
        out = self._next(TWO_REPOS + repo_block("api", "../fe/../be"))
        self.assertIn("reason: repo-invalid", out)
        self.assertIn("api.path", out)

    def test_paths_resolve_from_the_main_worktree(self) -> None:
        git(self.home, "worktree", "add", "-q", "-b", "side", str(self.home.parent / "wt" / "side"))
        linked = self.home.parent / "wt" / "side"
        (linked / "jt-queue").mkdir()
        (linked / "jt-queue" / "brief.md").write_text("# Brief\n", encoding="utf-8")
        (linked / "jt-queue" / "board.md").write_text(board_text("no items", repos=TWO_REPOS), encoding="utf-8")
        out = run_gate_raw(linked, "next").stdout
        self.assertIn("action: add-task", out)

    def test_repo_commands_are_approved_and_a_path_edit_is_refused(self) -> None:
        self.board.write_text(board_text("- [ ] **12** doc (docs)", test="no-suite", repos=TWO_REPOS), encoding="utf-8")
        card = gate._card_commands("")
        text = self.board.read_text(encoding="utf-8")
        self.assertEqual(gate._commands_refusal(self.home, text, "12", "")[0], "commands-unapproved")
        self.assertEqual(run_gate_raw(self.home, "approve-commands", "--id", "12").returncode, 0)
        self.assertIsNone(gate._commands_refusal(self.home, text, "12", ""))
        moved = text.replace("path: ../be", "path: ../elsewhere")
        self.assertEqual(gate._commands_refusal(self.home, moved, "12", "")[0], "commands-changed")
        self.assertEqual(card["start"], "")


class MultiRepoFixture(unittest.TestCase):
    """Two sibling repos, fe (home, holds the board) and be, each with work on task-12."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.fe = base / "fe"
        self.be = base / "be"
        for repo in (self.fe, self.be):
            repo.mkdir()
            init_repo(repo)
            (repo / "README.md").write_text("x\n", encoding="utf-8")
            (repo / ".gitignore").write_text("jt-queue/\n", encoding="utf-8")
            commit_all(repo, "docs: init")
        self.marker = base / "be-test-ran"
        self.write_board(be_test=f"touch {self.marker}")
        self.card_dir = self.fe / "jt-queue" / "tasks" / "12"
        self.card_dir.mkdir(parents=True)
        self.write_card(["fe:app.txt", "be:api.txt"])
        self.fe_sha = self.commit_on_task(self.fe, "app.txt")
        self.be_sha = self.commit_on_task(self.be, "api.txt")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write_board(
        self,
        be_test: str = "python3 -c pass",
        line: str = "- [ ] **12** login (feat)",
        be_lint: str = "",
        be_type: str = "",
    ) -> None:
        repos = repo_block("fe", ".") + "\n" + repo_block(
            "be", "../be", test=be_test, lint=be_lint, typecheck=be_type
        )
        (self.fe / "jt-queue").mkdir(exist_ok=True)
        (self.fe / "jt-queue" / "board.md").write_text(
            board_text(line, test="python3 -c pass", repos=repos), encoding="utf-8"
        )

    def write_card(self, files: list[str], repos: str = "fe, be") -> None:
        (self.card_dir / "task.md").write_text(
            card_body(files) + f"\nrepos: {repos}\n", encoding="utf-8"
        )

    def commit_on_task(self, repo: Path, name: str) -> str:
        git(repo, "checkout", "-q", "-b", "task-12")
        (repo / name).write_text("new\n", encoding="utf-8")
        commit_all(repo, f"feat: add {name}")
        sha = git(repo, "rev-parse", "HEAD").stdout.strip()
        git(repo, "checkout", "-q", "main")
        return sha

    def write_plan(self, fe_sha: str | None = None, be_sha: str | None = None) -> None:
        fe_sha = fe_sha or self.fe_sha
        be_sha = be_sha or self.be_sha
        (self.card_dir / "plan.md").write_text(
            with_ai_review(
                "# Plan 12\n\n## evidence\n\n| HEADER_TOKEN | check | ok |\n\n## review-diff\n\n"
                f"- fe: {fe_sha[:9]}\n- be: {be_sha[:9]}\n- verdict: pass\n- checked: both sides\n"
            ),
            encoding="utf-8",
        )



class MultiRepoReachReviewTests(MultiRepoFixture):
    """A task with repos: fe, be reaches review only when both repos pass."""

    def test_both_repos_green_reach_review_and_run_each_test(self) -> None:
        self.write_plan()
        result = run_gate(self.fe, "reach-review", "--id", "12")
        self.assertIn("allowed", result.stdout, result.stdout + result.stderr)
        self.assertIn("repos: fe, be", result.stdout)
        self.assertIn(
            "gates: secret ok · denylist skip · typecheck skip · lint skip · tests ok · "
            "verify skip · screen skip · review-diff open · test-weakening none",
            result.stdout,
        )
        self.assertTrue(self.marker.exists(), "be TEST_CMD did not run in be")
        self.assertNotIn("outside-files", result.stdout)

    def test_review_must_cite_each_repo_sha(self) -> None:
        self.write_plan(be_sha="0000000000")
        result = run_gate(self.fe, "reach-review", "--id", "12")
        self.assertIn("refused: review-diff", result.stdout)
        self.assertIn("repo be: no-repo-sha", result.stdout)
        self.assertFalse(self.marker.exists())
        self.assertEqual(gate.diff_review_detail(self.fe, "12"), "no-repo-sha")

    def test_backend_lint_must_pass_and_a_failure_counts_a_round(self) -> None:
        marker = self.fe.parent / "be-lint-ran"
        marker.unlink(missing_ok=True)
        self.write_board(be_lint=f"touch {marker}")
        self.write_plan()
        passed = run_gate(self.fe, "reach-review", "--id", "12")
        self.assertEqual(passed.returncode, 0, passed.stdout + passed.stderr)
        self.assertTrue(marker.exists())
        self.assertIn(
            "gates: secret ok · denylist skip · typecheck skip · lint ok · tests ok · "
            "verify skip · screen skip · review-diff open · test-weakening none",
            passed.stdout,
        )
        marker.unlink()
        self.write_board(be_lint="python3 -c 'import sys; sys.exit(4)'")
        failed = run_gate(self.fe, "reach-review", "--id", "12")
        self.assertIn("refused: lint-failed", failed.stdout)
        self.assertIn("repo be:", failed.stdout)
        self.assertIn("round 1 of 3", failed.stdout)
        self.assertIn("next: retry", failed.stdout)

    def test_added_env_in_one_repo_asks_and_hides_the_value(self) -> None:
        token = "ZZSECRETZZ"
        git(self.be, "checkout", "-q", "task-12")
        (self.be / ".env").write_text(f"TOKEN={token}\n", encoding="utf-8")
        commit_all(self.be, "feat: add env")
        git(self.be, "checkout", "-q", "main")
        result = run_gate(self.fe, "reach-review", "--id", "12")
        self.assertIn("refused: secret-suspect", result.stdout)
        self.assertIn("next: ask", result.stdout)
        self.assertIn("be:.env", result.stdout)
        self.assertNotIn(token, result.stdout + result.stderr)
        self.assertFalse(self.marker.exists())

    def test_red_test_in_one_repo_counts_a_round(self) -> None:
        self.write_board(be_test="python3 -c 'import sys; sys.exit(3)'")
        self.write_plan()
        result = run_gate(self.fe, "reach-review", "--id", "12")
        self.assertIn("refused: test-failed", result.stdout)
        self.assertIn("repo be:", result.stdout)
        self.assertIn("round 1 of 3", result.stdout)

    def test_missing_branch_in_a_listed_repo_is_refused(self) -> None:
        git(self.be, "branch", "-q", "-D", "task-12")
        self.write_plan()
        result = run_gate(self.fe, "reach-review", "--id", "12")
        self.assertIn("refused: task-branch-missing", result.stdout)
        self.assertIn("repo be", result.stdout)

    def test_slug_branches_across_repos_reach_review(self) -> None:
        for repo in (self.fe, self.be):
            git(repo, "branch", "-m", "task-12", "task-12-login")
        self.write_plan()
        result = run_gate(self.fe, "reach-review", "--id", "12")
        self.assertIn("allowed", result.stdout, result.stdout + result.stderr)
        self.assertTrue(self.marker.exists(), "be TEST_CMD did not run in be")

    def test_commits_in_an_unlisted_repo_are_refused(self) -> None:
        self.write_card(["app.txt"], repos="fe")
        self.write_plan()
        result = run_gate(self.fe, "reach-review", "--id", "12")
        self.assertIn("refused: repo-undeclared", result.stdout)
        self.assertIn("next: ask", result.stdout)
        self.assertIn("be", result.stdout)

    def test_unknown_repo_name_is_refused(self) -> None:
        self.write_card(["app.txt"], repos="fe, api")
        result = run_gate(self.fe, "reach-review", "--id", "12")
        self.assertIn("refused: repo-invalid", result.stdout)
        self.assertIn("api", result.stdout)

    def test_outside_files_are_reported_per_repo(self) -> None:
        self.write_card(["fe:app.txt", "be:other.txt"])
        self.write_plan()
        result = run_gate(self.fe, "reach-review", "--id", "12")
        self.assertIn("allowed", result.stdout, result.stdout)
        self.assertIn("outside-files: be:api.txt", result.stdout)

    def test_edit_to_another_repo_command_is_refused_after_approval(self) -> None:
        self.write_plan()
        run_gate_raw(self.fe, "approve-commands", "--id", "12")
        self.write_board(be_test=f"touch {self.marker}.sneaky")
        result = run_gate_raw(self.fe, "reach-review", "--id", "12")
        self.assertIn("refused: commands-changed", result.stdout)
        self.assertFalse(Path(f"{self.marker}.sneaky").exists())

    def test_write_records_a_link_per_repo(self) -> None:
        self.write_plan()
        result = run_gate(self.fe, "reach-review", "--id", "12", "--write", "--link", "local")
        self.assertIn("allowed", result.stdout, result.stdout)
        board = (self.fe / "jt-queue" / "board.md").read_text(encoding="utf-8")
        self.assertIn("- [ ] **12** login (feat) review: fe:local be:local", board)
        parsed = gate.parse_board(board)
        self.assertEqual(parsed.cards[0].status, "review:")

    def test_home_only_task_with_repos_board_keeps_the_v22_path(self) -> None:
        git(self.be, "branch", "-q", "-D", "task-12")
        self.write_card(["fe:app.txt"], repos="fe")
        (self.card_dir / "plan.md").write_text(
            with_ai_review(
                "# Plan 12\n\n## evidence\n\n| HEADER_TOKEN | check | ok |\n\n## review-diff\n\n"
                f"- commit: {self.fe_sha}\n- verdict: pass\n- checked: scope\n"
            ),
            encoding="utf-8",
        )
        result = run_gate(self.fe, "reach-review", "--id", "12")
        self.assertIn("allowed", result.stdout, result.stdout)
        self.assertNotIn("repos:", result.stdout)
        self.assertNotIn("outside-files", result.stdout)


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class MultiRepoScreenTests(MultiRepoFixture):
    """screen: yes across repos starts each repo from its own task worktree."""

    def setUp(self) -> None:
        super().setUp()
        self.be_port, self.fe_port = _free_port(), _free_port()
        self.clicked = Path(self.tmp.name) / "clicked"
        repos = repo_block("fe", ".") + "\n" + repo_block("be", "../be", test="python3 -c pass")
        (self.fe / "jt-queue" / "board.md").write_text(
            board_text("- [ ] **12** login (feat)", test="python3 -c pass", browser="playwright", repos=repos),
            encoding="utf-8",
        )
        self.write_plan()

    def screen_card(self, be_start: str | None = None, extra: str = "") -> None:
        be_start = be_start or f"python3 -m http.server {self.be_port} --bind 127.0.0.1"
        click = (
            "fe: python3 -c \"import urllib.request as u; "
            f"u.urlopen('http://127.0.0.1:{self.be_port}/api.txt'); "
            f"u.urlopen('http://127.0.0.1:{self.fe_port}/app.txt'); "
            f"open('{self.clicked}', 'w').write('ok')\""
        )
        (self.card_dir / "task.md").write_text(
            "# 12 - login\n\nkind: feat\n\nscreen: yes\nstart:\n"
            f"- be: {be_start}\n"
            f"- fe: python3 -m http.server {self.fe_port} --bind 127.0.0.1\n{extra}"
            f"port: {self.be_port}, {self.fe_port}\nwait: 20\nclick: {click}\n\n"
            "do:\n- something\n\nout:\n- other\n\npass:\n- HEADER_TOKEN\n\n"
            "files:\n- fe:app.txt\n- be:api.txt\n\nrepos: fe, be\n\nask:\n",
            encoding="utf-8",
        )

    def test_click_reaches_both_task_branches(self) -> None:
        self.screen_card()
        result = run_gate(self.fe, "reach-review", "--id", "12")
        self.assertIn("allowed", result.stdout, result.stdout + result.stderr)
        self.assertTrue(self.clicked.exists(), "click did not reach both servers")
        self.assertFalse(gate._port_open(self.be_port))
        self.assertFalse(gate._port_open(self.fe_port))

    def test_a_start_that_dies_names_its_repo(self) -> None:
        self.screen_card(be_start="python3 -c 'import sys; sys.exit(4)'")
        result = run_gate(self.fe, "reach-review", "--id", "12")
        self.assertIn("refused: start-down", result.stdout)
        self.assertIn("repo be: start exited with code 4", result.stdout)
        self.assertFalse(gate._port_open(self.fe_port))

    def test_start_list_is_part_of_the_task_approval(self) -> None:
        self.screen_card()
        run_gate_raw(self.fe, "approve-commands", "--id", "12")
        self.screen_card(be_start=f"touch {self.clicked}")
        result = run_gate_raw(self.fe, "reach-review", "--id", "12")
        self.assertIn("refused: commands-changed", result.stdout)
        self.assertFalse(self.clicked.exists())

    def test_start_for_an_unlisted_repo_is_refused(self) -> None:
        self.screen_card(extra="- api: python3 -c pass\n")
        result = run_gate(self.fe, "reach-review", "--id", "12")
        self.assertIn("refused: repo-invalid", result.stdout)
        self.assertIn("api", result.stdout)

    def test_moving_a_repo_path_after_approval_stops_screen_check(self) -> None:
        self.screen_card()
        run_gate_raw(self.fe, "approve-commands", "--id", "12")
        elsewhere = Path(self.tmp.name) / "elsewhere"
        elsewhere.mkdir()
        init_repo(elsewhere)
        board = self.fe / "jt-queue" / "board.md"
        board.write_text(board.read_text(encoding="utf-8").replace("path: ../be", "path: ../elsewhere"), encoding="utf-8")
        result = run_gate_raw(self.fe, "screen-check", "--id", "12")
        self.assertIn("refused: commands-changed", result.stdout, result.stdout)
        self.assertFalse(gate._port_open(self.be_port))

    def test_moving_a_path_is_refused_even_when_every_repo_is_no_suite(self) -> None:
        repos = repo_block("fe", ".") + "\n" + repo_block("be", "../be", test="no-suite")
        board = self.fe / "jt-queue" / "board.md"
        board.write_text(board_text("- [ ] **12** login (feat)", test="no-suite", repos=repos), encoding="utf-8")
        self.write_card(["fe:app.txt", "be:api.txt"])
        run_gate_raw(self.fe, "approve-commands", "--id", "12")
        self.assertIn("allowed", run_gate_raw(self.fe, "reach-review", "--id", "12").stdout)
        board.write_text(board.read_text(encoding="utf-8").replace("path: ../be", "path: ../be/"), encoding="utf-8")
        result = run_gate_raw(self.fe, "reach-review", "--id", "12")
        self.assertIn("refused: commands-changed", result.stdout)

    def test_reordering_repos_changes_where_click_runs_and_needs_approval(self) -> None:
        self.screen_card()
        run_gate_raw(self.fe, "approve-commands", "--id", "12")
        card = self.card_dir / "task.md"
        card.write_text(card.read_text(encoding="utf-8").replace("repos: fe, be", "repos: be, fe"), encoding="utf-8")
        result = run_gate_raw(self.fe, "reach-review", "--id", "12")
        self.assertIn("refused: commands-changed", result.stdout)

    def test_v22_card_commands_keep_their_digest_keys(self) -> None:
        commands = gate._card_commands(card_body(["a"], screen=True, start="npm start", port="3000", click="true"))
        self.assertEqual(sorted(commands), ["click", "port", "start", "wait"])

    def test_cli_screen_check_starts_each_repo_from_its_checkout(self) -> None:
        self.screen_card()
        git(self.be, "checkout", "-q", "task-12")
        git(self.fe, "checkout", "-q", "task-12")
        bin_dir = Path(self.tmp.name) / "bin"
        bin_dir.mkdir()
        fake = bin_dir / "playwright"
        fake.write_text(
            "#!/bin/sh\nexec python3 -c \"import urllib.request as u; "
            f"u.urlopen('http://127.0.0.1:{self.be_port}/api.txt'); open('{self.clicked}', 'w')\"\n",
            encoding="utf-8",
        )
        fake.chmod(0o755)
        env = os.environ.copy()
        env["PATH"] = f"{bin_dir}:{env['PATH']}"
        result = run_gate(self.fe, "screen-check", "--id", "12", env=env)
        self.assertIn("screen-check: ok", result.stdout, result.stdout + result.stderr)
        self.assertTrue(self.clicked.exists())


if __name__ == "__main__":
    unittest.main()


class TaskBranchNameTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        init_repo(self.repo)
        (self.repo / "app.py").write_text("VALUE = 0\n", encoding="utf-8")
        commit_all(self.repo, "chore: init")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_task_head_names(self) -> None:
        self.assertTrue(gate.is_task_head("task-12", "12"))
        self.assertTrue(gate.is_task_head("task-12-login-rate-limit", "12"))
        self.assertTrue(gate.is_task_head("task-1.1-split", "1.1"))
        self.assertFalse(gate.is_task_head("task-12-", "12"))
        self.assertFalse(gate.is_task_head("task-12-Login", "12"))
        self.assertFalse(gate.is_task_head("task-12--x", "12"))
        self.assertFalse(gate.is_task_head("task-123", "12"))
        self.assertFalse(gate.is_task_head("task-1.1-split", "1"))
        self.assertFalse(gate.is_task_head("task-12-a/b", "12"))
        self.assertTrue(gate.is_task_head("feat/BOOK-12-room-search", "12", "BOOK-12"))
        self.assertTrue(gate.is_task_head("feat/BOOK-12", "12", "BOOK-12"))
        self.assertTrue(gate.is_task_head("feat/#45-login-fix", "12", "#45"))
        self.assertFalse(gate.is_task_head("feat/BOOK-12-room-search", "12", "BOOK-99"))
        self.assertFalse(gate.is_task_head("feat/BOOK-99-room-search", "12", "BOOK-12"))
        self.assertFalse(gate.is_task_head("feat/BOOK-12-room", "12", "BOOK-1"))
        self.assertFalse(gate.is_task_head("feat/BOOK-1-room", "12", "BOOK-12"))
        self.assertFalse(gate.is_task_head("feat/#45-fix", "12", "#4"))
        self.assertFalse(gate.is_task_head("feat/#4-fix", "12", "#45"))
        self.assertTrue(gate.is_task_head("style/BOOK-12-format", "12", "BOOK-12"))

    def test_ticket_id_normalization(self) -> None:
        text = "ticket: 'BOOK-12'  # Jira\n"
        self.assertEqual(gate.ticket_id_in_card(text), "BOOK-12")
        self.assertEqual(gate.ticket_id_in_card('ticket: "#45"\n'), "#45")
        self.assertEqual(gate.ticket_id_in_card("ticket: BOOK-12  # note\n"), "BOOK-12")

    def test_default_branch_uses_board_kind(self) -> None:
        task_dir = self.repo / "jt-queue" / "tasks" / "12"
        task_dir.mkdir(parents=True, exist_ok=True)
        (task_dir / "task.md").write_text("# 12\n\nticket: BOOK-12\n", encoding="utf-8")
        (self.repo / "jt-queue" / "board.md").write_text(
            "# Board\n\nqueue: main\n\n## main\n\n- [ ] **12** format (style)\n",
            encoding="utf-8",
        )
        self.assertEqual(gate.task_branch(self.repo, "12"), "style/BOOK-12")

    def test_branch_deprecated_note_for_legacy_branch(self) -> None:
        git(self.repo, "branch", "task-12-login")
        note = gate.task_branch_deprecation_note(self.repo, "12")
        self.assertIn("branch-deprecated:", note)
        self.assertIn("legacy task-<id>", note)

    def test_ticket_id_in_card(self) -> None:
        self.assertEqual(gate.ticket_id_in_card(""), "")
        self.assertEqual(gate.ticket_id_in_card("do: x\n"), "")

    def test_bare_name_when_no_branch(self) -> None:
        self.assertEqual(gate.task_branch(self.repo, "12"), "task-12")
        self.assertFalse(gate.has_one_task_branch(self.repo, "12"))

    def test_default_conventional_name_when_ticket_present(self) -> None:
        task_dir = self.repo / "jt-queue" / "tasks" / "12"
        task_dir.mkdir(parents=True, exist_ok=True)
        (task_dir / "task.md").write_text(
            "# 12 - x\n\nticket: BOOK-12\n",
            encoding="utf-8",
        )
        self.assertEqual(gate.task_branch(self.repo, "12"), "feat/BOOK-12")

    def test_conventional_branch_is_the_task_branch(self) -> None:
        task_dir = self.repo / "jt-queue" / "tasks" / "12"
        task_dir.mkdir(parents=True, exist_ok=True)
        (task_dir / "task.md").write_text("# 12\n\nticket: BOOK-12\n", encoding="utf-8")
        git(self.repo, "branch", "feat/BOOK-12-room-search")
        git(self.repo, "branch", "task-123-other")
        self.assertEqual(gate.task_branch(self.repo, "12"), "feat/BOOK-12-room-search")
        self.assertTrue(gate.has_one_task_branch(self.repo, "12"))

    def test_one_slug_branch_is_the_task_branch(self) -> None:
        git(self.repo, "branch", "task-12-login")
        git(self.repo, "branch", "task-123-other")
        self.assertEqual(gate.task_branch(self.repo, "12"), "task-12-login")
        self.assertTrue(gate.has_one_task_branch(self.repo, "12"))

    def test_remote_only_branch_is_found(self) -> None:
        head = git(self.repo, "rev-parse", "HEAD").stdout.strip()
        git(self.repo, "update-ref", "refs/remotes/origin/task-12-login", head)
        self.assertEqual(gate.task_branch(self.repo, "12"), "task-12-login")
        self.assertFalse(gate.has_one_task_branch(self.repo, "12"))

    def test_local_branch_wins_over_a_stale_remote(self) -> None:
        head = git(self.repo, "rev-parse", "HEAD").stdout.strip()
        git(self.repo, "update-ref", "refs/remotes/origin/task-12", head)
        git(self.repo, "branch", "task-12-login")
        self.assertEqual(gate.task_branch(self.repo, "12"), "task-12-login")

    def test_bare_head_matches_slug_pull_requests_only_when_fuzzy(self) -> None:
        self.assertTrue(gate._head_matches("task-12-login", "task-12", fuzzy=True))
        self.assertFalse(gate._head_matches("task-12-login", "task-12"))
        self.assertFalse(gate._head_matches("task-12-login", "task-12-other", fuzzy=True))
        self.assertFalse(gate._head_matches("task-123", "task-12", fuzzy=True))
        self.assertTrue(
            gate._head_matches(
                "feat/BOOK-12-room-search",
                "feat/BOOK-12",
                fuzzy=True,
                ticket_id="BOOK-12",
            )
        )


class SizeRuleTests(unittest.TestCase):
    def test_auth_names_match_and_author_does_not(self) -> None:
        self.assertTrue(gate.touches_auth(["src/auth/login.py"]))
        self.assertTrue(gate.touches_auth(["app/authentication.py"]))
        self.assertTrue(gate.touches_auth(["web/oauth_client.py"]))
        self.assertTrue(gate.touches_auth(["password-reset.tsx"]))
        self.assertFalse(gate.touches_auth(["author.py"]))
        self.assertFalse(gate.touches_auth(["src/models.py"]))

    def test_migration_and_sql_match_and_a_model_does_not(self) -> None:
        self.assertTrue(gate.touches_data(["db/migrations/001_users.sql"]))
        self.assertTrue(gate.touches_data(["alembic/versions/a.py"]))
        self.assertTrue(gate.touches_data(["prisma/schema.prisma"]))
        self.assertTrue(gate.touches_data(["scripts/add_migration.py"]))
        self.assertFalse(gate.touches_data(["app/models.py"]))
        self.assertFalse(gate.touches_data(["app/schema.py"]))

    def test_each_trigger_raises_one_step_and_the_ceiling_stays(self) -> None:
        self.assertEqual(gate.raised_size("small", ["auth"]), ("medium", ["auth"]))
        self.assertEqual(gate.raised_size("small", ["migrations"]), ("medium", ["migrations"]))
        self.assertEqual(gate.raised_size("small", ["diff"]), ("medium", ["diff"]))
        self.assertEqual(gate.raised_size("medium", ["auth"]), ("large", ["auth"]))
        self.assertEqual(
            gate.raised_size("small", ["auth", "migrations", "diff"]),
            ("large", ["auth", "migrations", "diff"]),
        )
        self.assertEqual(gate.raised_size("large", ["auth"]), ("large", []))
        self.assertEqual(gate.path_triggers(["app.py"], 5, 5), [])
        self.assertEqual(gate.path_triggers(["app.py"], 6, 5), ["diff"])
        self.assertEqual(gate.path_triggers(["src/auth/login.py"], 1, 400), ["auth"])
        self.assertEqual(gate.path_triggers(["db/migrations/001.sql"], 1, 400), ["migrations"])

    def test_affected_paths_follow_the_changed_source(self) -> None:
        existing = ["app.py", "tests/test_app.py", "tests/test_other.py"]
        self.assertEqual(gate.affected_test_paths(["app.py"], existing), ["tests/test_app.py"])
        self.assertEqual(
            gate.affected_test_paths(["tests/test_app.py"], existing),
            ["tests/test_app.py"],
        )
        self.assertEqual(gate.affected_test_paths(["README.md"], existing), [])

    def test_board_override_replaces_the_assessed_size(self) -> None:
        task = "size: small\n"
        overridden = board_text("- [ ] **12** fresh (feat) size: large")
        self.assertEqual(gate.size_floor(task, overridden, "12"), "large")
        self.assertEqual(gate.size_floor(task, board_text("- [ ] **12** fresh (feat)"), "12"), "small")
        self.assertEqual(gate.size_floor("", board_text("- [ ] **12** fresh (feat)"), "12"), "medium")
        self.assertEqual(gate.diff_limit(board_text("no cards", diff_limit="20")), 20)
        self.assertEqual(gate.diff_limit("queue: main\n"), gate.DEFAULT_DIFF_LIMIT)

    def test_size_on_the_board_line_is_not_a_status(self) -> None:
        text = board_text("- [ ] **12** fresh (feat) size: small")
        decision = decide_board(text, {"12": card_body(["src/a.py"])})
        self.assertEqual(decision.action, "do-task")
        self.assertNotEqual(decision.reason, "unknown-status")
        self.assertIsNone(gate.status_on_line("- [ ] **12** fresh (feat) size: small"))
        self.assertEqual(
            gate.status_on_line("- [ ] **12** fresh (feat) size: small review: local"),
            "review:",
        )
        updated = gate.apply_waiting_review(text, "12", 0, "local")
        self.assertIn("size: small", updated)
        self.assertIn("review: local", updated)

    def test_branch_hints_name_the_task_branch(self) -> None:
        for key in ("test-failed", "lint-failed", "typecheck-failed", "pr-missing", "worktree-failed"):
            hint = gate.HINT_FOR[key]
            self.assertIn("type/<ticket-id>-<slug>", hint)
            self.assertNotIn("task-<id>", hint)

    def test_small_runs_the_full_suite_unless_the_board_says_how(self) -> None:
        full, note = gate.test_command_for("small", "make test", ["tests/test_app.py"])
        self.assertEqual((full, note), ("make test", "none -> full suite"))
        missing, note = gate.test_command_for("small", "pytest {files}", [])
        self.assertEqual((missing, note), ("pytest", "none -> full suite"))
        scoped, note = gate.test_command_for("small", "pytest {files}", ["tests/test_app.py"])
        self.assertEqual((scoped, note), ("pytest tests/test_app.py", "tests/test_app.py"))
        own, note = gate.test_command_for("small", "npm test", ["tests/test_app.py"], "npx vitest --changed")
        self.assertEqual((own, note), ("npx vitest --changed", "command"))
        filled, note = gate.test_command_for(
            "small", "npm test", ["tests/test_app.py"], "npx jest --findRelatedTests {files}"
        )
        self.assertEqual((filled, note), ("npx jest --findRelatedTests tests/test_app.py", "tests/test_app.py"))
        fallback, note = gate.test_command_for("small", "npm test", [], "npx jest --findRelatedTests {files}")
        self.assertEqual((fallback, note), ("npm test", "none -> full suite"))
        none, note = gate.test_command_for("small", gate.NO_SUITE, [])
        self.assertEqual((none, note), (None, "none"))
        medium, note = gate.test_command_for("medium", "make test", ["tests/test_app.py"])
        self.assertEqual((medium, note), ("make test", ""))

    def test_empty_affected_test_cmd_stays_out_of_the_approval(self) -> None:
        plain = gate._board_commands(board_text("no cards"))
        empty = gate._board_commands(board_text("no cards", affected=""))
        self.assertEqual(plain, empty)
        self.assertNotIn("AFFECTED_TEST_CMD", plain)
        filled = gate._board_commands(board_text("no cards", affected="pytest --testmon"))
        self.assertEqual(filled["AFFECTED_TEST_CMD"], "pytest --testmon")


class SizeTierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        init_repo(self.repo)
        (self.repo / "jt-queue" / "tasks" / "12").mkdir(parents=True)
        (self.repo / "check.py").write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
        (self.repo / "tests").mkdir()
        (self.repo / "tests" / "test_other.py").write_text(
            "def test_other():\n    pass\n", encoding="utf-8"
        )
        (self.repo / "jt-queue" / "board.md").write_text(
            board_text("- [ ] **12** fresh (feat)", test=gate.NO_SUITE),
            encoding="utf-8",
        )
        (self.repo / "jt-queue" / "tasks" / "12" / "task.md").write_text(
            card_body(["app.py"]),
            encoding="utf-8",
        )
        commit_all(self.repo, "docs: add the board")
        git(self.repo, "branch", "task-12")
        self.marker = self.repo.parent / f"{self.repo.name}-ran"

    def tearDown(self) -> None:
        self.marker.unlink(missing_ok=True)
        self.tmp.cleanup()

    def _marker_cmd(self) -> str:
        self.marker.unlink(missing_ok=True)
        path = str(self.marker)
        return (
            'python3 -c "import pathlib,sys; pathlib.Path(\''
            + path
            + '\').write_text(\' \'.join(sys.argv[1:]))"'
        )

    def _land(self, files: dict[str, str], *, review: str | None = "rejected") -> None:
        git(self.repo, "checkout", "task-12")
        for name, body in files.items():
            path = self.repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
        commit_all(self.repo, "feat: change the code")
        sha = git(self.repo, "rev-parse", "HEAD").stdout.strip()
        plan = self.repo / "jt-queue" / "tasks" / "12" / "plan.md"
        note = {
            "rejected": "\n## ai-review\n\n- rejected: none — no finding\n",
            "accepted": "\n## ai-review\n\n- accepted: off-by-one — the pass command shows it\n",
            "fallback": "\n## ai-review\n\nfallback: no reviewer skill installed\n",
            "blank": "\n## ai-review\n\nreviewer: interrogate\n",
            None: "",
        }[review]
        plan.write_text(
            "# Plan 12\n\n## evidence\n\n| HEADER_TOKEN | check | ok |\n\n"
            "## review-diff\n\n"
            f"- commit: {sha}\n- reviewer: reviewer\n- verdict: pass\n- checked: scope\n"
            + note,
            encoding="utf-8",
        )
        commit_all(self.repo, "docs: record review")
        git(self.repo, "checkout", "main")

    def _reach(
        self,
        *,
        size: str = "",
        line: str = "- [ ] **12** fresh (feat)",
        test: str | None = None,
        diff_limit: str | None = None,
        affected: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        (self.repo / "jt-queue" / "tasks" / "12" / "task.md").write_text(
            card_body(["app.py"], size=size),
            encoding="utf-8",
        )
        (self.repo / "jt-queue" / "board.md").write_text(
            board_text(
                line,
                test=gate.NO_SUITE if test is None else test,
                diff_limit=diff_limit,
                affected=affected,
            ),
            encoding="utf-8",
        )
        return run_gate(self.repo, "reach-review", "--id", "12")

    def test_assessed_small_runs_affected_tests_only(self) -> None:
        self._land(
            {
                "app.py": "VALUE = 1\n",
                "tests/test_app.py": "def test_app():\n    pass\n",
            }
        )
        result = self._reach(size="small", test=self._marker_cmd() + " {files}")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("size: small", result.stdout)
        self.assertNotIn("escalate:", result.stdout)
        self.assertNotIn("size-from:", result.stdout)
        self.assertIn("affected: tests/test_app.py", result.stdout)
        ran = self.marker.read_text(encoding="utf-8")
        self.assertIn("tests/test_app.py", ran)
        self.assertNotIn("test_other.py", ran)

    def test_medium_runs_the_full_test_command(self) -> None:
        self._land(
            {
                "app.py": "VALUE = 1\n",
                "tests/test_app.py": "def test_app():\n    pass\n",
            }
        )
        result = self._reach(size="medium", test=self._marker_cmd())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("size: medium", result.stdout)
        self.assertNotIn("affected:", result.stdout)
        self.assertNotIn("escalate:", result.stdout)
        self.assertEqual(self.marker.read_text(encoding="utf-8"), "")

    def test_unset_size_stays_medium(self) -> None:
        self._land({"app.py": "VALUE = 1\n"})
        result = self._reach()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("size: medium", result.stdout)
        self.assertNotIn("escalate:", result.stdout)
        self.assertNotIn("size-hooks:", result.stdout)

    def test_board_size_overrides_the_task(self) -> None:
        self._land({"app.py": "VALUE = 1\n"})
        result = self._reach(size="small", line="- [ ] **12** fresh (feat) size: large")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("size: large", result.stdout)
        self.assertNotIn("escalate:", result.stdout)
        self.assertNotIn("size-from:", result.stdout)
        self.assertIn(
            "size-hooks: worktree-rounds, fresh-context-review, high-risk",
            result.stdout,
        )

    def test_gate_does_not_lower_a_large_task(self) -> None:
        self._land({"app.py": "VALUE = 1\n"})
        result = self._reach(size="large")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("size: large", result.stdout)
        self.assertNotIn("escalate:", result.stdout)
        self.assertNotIn("size-from:", result.stdout)

    def test_auth_escalates_a_small_task(self) -> None:
        self._land({"src/auth/login.py": "def login():\n    return True\n"})
        result = self._reach(size="small")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("size: medium", result.stdout)
        self.assertIn("size-from: small", result.stdout)
        self.assertIn("escalate: auth\n", result.stdout)
        self.assertNotIn("size-hooks:", result.stdout)

    def test_migrations_escalate_a_small_task(self) -> None:
        self._land({"db/migrations/001_users.sql": "create table users (id int);\n"})
        result = self._reach(size="small")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("size: medium", result.stdout)
        self.assertIn("size-from: small", result.stdout)
        self.assertIn("escalate: migrations\n", result.stdout)

    def test_a_large_diff_escalates_at_the_board_limit(self) -> None:
        self._land({"app.py": "".join(f"LINE_{i} = {i}\n" for i in range(8))})
        result = self._reach(size="small", diff_limit="5")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("size: medium", result.stdout)
        self.assertIn("size-from: small", result.stdout)
        self.assertIn("escalate: diff\n", result.stdout)

    def test_an_author_file_does_not_escalate(self) -> None:
        self._land({"author.py": "NAME = 'Ada'\n"})
        result = self._reach(size="small")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("size: small", result.stdout)
        self.assertIn("affected: none\n", result.stdout)
        self.assertNotIn("escalate:", result.stdout)

    def test_auth_and_migrations_stack_to_large(self) -> None:
        self._land({"db/migrations/auth_login.sql": "create table sessions (id int);\n"})
        result = self._reach(size="small")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("size: large", result.stdout)
        self.assertIn("escalate: auth, migrations", result.stdout)
        self.assertIn("size-hooks: worktree-rounds, fresh-context-review, high-risk", result.stdout)

    def test_small_with_no_affected_test_runs_the_full_suite(self) -> None:
        self._land({"app.py": "VALUE = 1\n"})
        result = self._reach(size="small", test=self._marker_cmd())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("affected: none -> full suite", result.stdout)
        self.assertIn("tests ok", result.stdout)
        self.assertEqual(self.marker.read_text(encoding="utf-8"), "")

    def test_small_does_not_append_paths_without_a_slot(self) -> None:
        self._land(
            {
                "app.py": "VALUE = 1\n",
                "tests/test_app.py": "def test_app():\n    pass\n",
            }
        )
        result = self._reach(size="small", test=self._marker_cmd())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("affected: none -> full suite", result.stdout)
        self.assertEqual(self.marker.read_text(encoding="utf-8"), "")

    def test_affected_test_cmd_runs_instead_of_the_full_suite(self) -> None:
        self._land(
            {
                "app.py": "VALUE = 1\n",
                "tests/test_app.py": "def test_app():\n    pass\n",
            }
        )
        scoped = self.repo.parent / f"{self.repo.name}-scoped"
        self.addCleanup(scoped.unlink, missing_ok=True)
        scoped_cmd = (
            'python3 -c "import pathlib,sys; pathlib.Path(\''
            + str(scoped)
            + '\').write_text(\' \'.join(sys.argv[1:]))" {files}'
        )
        result = self._reach(size="small", test=self._marker_cmd(), affected=scoped_cmd)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("affected: tests/test_app.py", result.stdout)
        self.assertFalse(self.marker.exists())
        self.assertIn("tests/test_app.py", scoped.read_text(encoding="utf-8"))

    def test_medium_and_large_require_ai_review(self) -> None:
        self._land({"app.py": "VALUE = 1\n"}, review=None)
        medium = self._reach(size="medium")
        self.assertIn("refused: ai-review", medium.stdout)
        self.assertIn("no-ai-review: size medium", medium.stdout)
        self.assertIn("next: retry", medium.stdout)
        self.assertNotIn("step:", medium.stdout)
        self.assertNotIn("round ", medium.stdout)
        self.assertNotIn("\nallowed\n", f"\n{medium.stdout}")
        large = self._reach(size="large")
        self.assertIn("refused: ai-review", large.stdout)
        self.assertIn("no-ai-review: size large", large.stdout)

    def test_small_skips_ai_review(self) -> None:
        self._land({"app.py": "VALUE = 1\n"}, review=None)
        result = self._reach(size="small")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("size: small", result.stdout)
        self.assertIn("ai-review: skip", result.stdout)
        self.assertNotIn("refused: ai-review", result.stdout)

    def test_recorded_ai_review_lets_medium_and_large_pass(self) -> None:
        self._land({"app.py": "VALUE = 1\n"}, review="accepted")
        medium = self._reach(size="medium")
        self.assertEqual(medium.returncode, 0, medium.stdout + medium.stderr)
        self.assertIn("ai-review: open", medium.stdout)
        self.assertIn("size: medium", medium.stdout)
        self._land({"app.py": "VALUE = 2\n"}, review="fallback")
        large = self._reach(size="large")
        self.assertEqual(large.returncode, 0, large.stdout + large.stderr)
        self.assertIn("ai-review: open", large.stdout)
        self.assertIn("size-hooks: worktree-rounds, fresh-context-review, high-risk", large.stdout)

    def test_blank_ai_review_section_does_not_count(self) -> None:
        self._land({"app.py": "VALUE = 1\n"}, review="blank")
        result = self._reach(size="medium")
        self.assertIn("refused: ai-review", result.stdout)
        self.assertIn("no-ai-review", result.stdout)

    def test_escalation_to_medium_requires_ai_review(self) -> None:
        self._land({"src/auth/login.py": "def login():\n    return True\n"}, review=None)
        result = self._reach(size="small")
        self.assertIn("refused: ai-review", result.stdout)
        self.assertIn("no-ai-review: size medium", result.stdout)

    def test_a_failing_test_stops_before_ai_review(self) -> None:
        self._land({"app.py": "VALUE = 1\n"}, review=None)
        result = self._reach(size="medium", test="python3 -c 'import sys; sys.exit(1)'")
        self.assertIn("refused: test-failed", result.stdout)
        self.assertIn("step: tests", result.stdout)
        self.assertNotIn("refused: ai-review", result.stdout)
        self.assertNotIn("no-ai-review", result.stdout)


class AiReviewRecordTests(unittest.TestCase):
    def test_only_a_finding_or_the_fallback_line_counts(self) -> None:
        self.assertTrue(gate.ai_review_recorded("- accepted: off-by-one — pass command shows 86\n"))
        self.assertTrue(gate.ai_review_recorded("- rejected: rename - outside files\n"))
        self.assertTrue(gate.ai_review_recorded("fallback: no reviewer skill installed\n"))
        self.assertFalse(gate.ai_review_recorded(""))
        self.assertFalse(gate.ai_review_recorded("- accepted: <finding> — <reason>\n"))
        self.assertFalse(gate.ai_review_recorded("- accepted: off-by-one\n"))
        self.assertFalse(gate.ai_review_recorded("fallback: skipped the review\n"))
        self.assertFalse(gate.ai_review_recorded("reviewer: interrogate | pr | none\n"))
        self.assertEqual(gate.FAIL_FAST, ("secret", "denylist", "typecheck", "lint", "tests", "verify"))


_SPEC_THEN = "the button is enabled"
_SPEC_EC = "the room is hidden"


def _story_spec(approve: str = "✅ Alex · 2026-11-03", question: str = "| Q1 | Spinner? | UX | later | |",
                guards: bool = True) -> str:
    if guards:
        table = (
            "| # | Given | When | Then | Guards |\n|---|---|---|---|---|\n"
            f"| AC1 | staff | look | {_SPEC_THEN} | |\n"
            f"| EC1 | not admin | open | {_SPEC_EC} | AC1 |\n"
        )
    else:
        table = (
            "| # | Given | When | Then |\n|---|---|---|---|\n"
            f"| AC1 | staff | look | {_SPEC_THEN} |\n"
            f"| EC1 | not admin | open | {_SPEC_EC} |\n"
        )
    return (
        "<!-- scrum-spec -->\n# book\n\n## Acceptance Criteria\n\n"
        f"**approve:** {approve}\n\n{table}\n"
        "## Questions\n\n| # | Question | Ask | Blocks | Answer |\n|---|---|---|---|---|\n"
        f"{question}\n"
    )


def _spec_task(pass_lines: str) -> str:
    body = "\n".join(f"- {line}" for line in pass_lines.splitlines() if line.strip())
    return (
        "# 12 - book\n\nkind: feat\n\nspec: scrum-spec/book/spec.md\n\n"
        "do:\n- book\n\nout:\n- other\n\npass:\n"
        f"{body}\n\nfiles:\n- src/a.py\n\nask:\n"
    )


def _plant_spec(root: Path, spec: str, task: str) -> None:
    spec_path = root / "scrum-spec" / "book" / "spec.md"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(spec, encoding="utf-8")
    task_dir = root / "jt-queue" / "tasks" / "12"
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "task.md").write_text(task, encoding="utf-8")
    (root / "jt-queue" / "board.md").write_text(
        board_text("- [ ] **12** book (feat)", test=gate.NO_SUITE),
        encoding="utf-8",
    )


class SpecPassBridgeTests(unittest.TestCase):
    def test_pass_lines_trace_to_their_ac(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task = _spec_task(f"AC1:   {_SPEC_THEN}\nEC1: {_SPEC_EC}")
            _plant_spec(root, _story_spec(), task)
            traced = gate.trace_spec_pass(root, task)
        self.assertIsInstance(traced, dict)
        self.assertEqual(traced["approval"], "Alex · 2026-11-03")
        self.assertEqual(traced["ids"], ["AC1", "EC1"])

    def test_old_spec_without_guards_still_traces(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task = _spec_task(f"AC1: {_SPEC_THEN}")
            _plant_spec(root, _story_spec(guards=False), task)
            traced = gate.trace_spec_pass(root, task)
        self.assertIsInstance(traced, dict)
        self.assertEqual(traced["ids"], ["AC1"])

    def test_pass_line_that_is_not_the_ac_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task = _spec_task("AC1: something else")
            _plant_spec(root, _story_spec(), task)
            reason, detail = gate.trace_spec_pass(root, task)
            self.assertEqual(reason, "pass-ac")
            self.assertIn("must quote its Then", detail)
            task = _spec_task("AC9: missing")
            _plant_spec(root, _story_spec(), task)
            reason, detail = gate.trace_spec_pass(root, task)
            self.assertEqual(reason, "pass-ac")
            self.assertIn("AC9 is not an AC or EC", detail)
            task = _spec_task("just a command")
            _plant_spec(root, _story_spec(), task)
            reason, detail = gate.trace_spec_pass(root, task)
        self.assertEqual(reason, "pass-ac")
        self.assertIn("does not name an AC id", detail)

    def test_unapproved_or_blocked_spec_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task = _spec_task(f"AC1: {_SPEC_THEN}")
            _plant_spec(root, _story_spec(approve="❌ waiting for PO"), task)
            reason, detail = gate.trace_spec_pass(root, task)
            self.assertEqual(reason, "spec-unapproved")
            self.assertIn("not approved", detail)
            _plant_spec(root, _story_spec(question="| Q2 | API? | BE | dev | |"), task)
            reason, detail = gate.trace_spec_pass(root, task)
            self.assertEqual(reason, "spec-unapproved")
            self.assertIn("approval is blocked while Q2 blocks dev", detail)
            _plant_spec(root, _story_spec(approve="✅ Claude · 2026-11-03"), task)
            reason, detail = gate.trace_spec_pass(root, task)
        self.assertEqual(reason, "spec-unapproved")
        self.assertIn("not an AI", detail)

    def test_task_without_spec_is_unchanged(self) -> None:
        self.assertIsNone(gate.trace_spec_pass(Path("."), card_body(["src/a.py"])))

    def test_spec_outside_the_repo_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "repo"
            root.mkdir()
            (base / "outside-spec.md").write_text("<!-- scrum-spec -->\n", encoding="utf-8")
            task = _spec_task(f"AC1: {_SPEC_THEN}").replace(
                "spec: scrum-spec/book/spec.md", "spec: ../outside-spec.md"
            )
            _plant_spec(root, _story_spec(), task)
            reason, detail = gate.trace_spec_pass(root, task)
        self.assertEqual(reason, "spec-unapproved")
        self.assertIn("inside this repository", detail)

    def test_reach_review_refuses_a_bad_pass_line(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _plant_spec(root, _story_spec(), _spec_task("AC1: not the then"))
            result = run_gate_raw(root, "reach-review", "--id", "12")
        self.assertIn("refused: pass-ac", result.stdout)
        self.assertIn("next: retry", result.stdout)
        self.assertNotIn("commands-unapproved", result.stdout)

    def test_reach_review_accepts_a_traced_spec_before_the_branch_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _plant_spec(root, _story_spec(), _spec_task(f"AC1: {_SPEC_THEN}\nEC1: {_SPEC_EC}"))
            result = run_gate_raw(root, "reach-review", "--id", "12")
        self.assertIn("refused: task-branch-missing", result.stdout)
        self.assertNotIn("refused: pass-ac", result.stdout)
        self.assertNotIn("refused: spec-unapproved", result.stdout)

    def test_reach_review_refuses_a_blocked_spec(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _plant_spec(
                root,
                _story_spec(question="| Q1 | Who? | PO | AC | |"),
                _spec_task(f"AC1: {_SPEC_THEN}"),
            )
            result = run_gate_raw(root, "reach-review", "--id", "12")
        self.assertIn("refused: spec-unapproved", result.stdout)
        self.assertIn("next: stop", result.stdout)
        self.assertIn("Q1 blocks AC", result.stdout)


class QueueContextTests(unittest.TestCase):
    def test_teammate_files_are_committed(self) -> None:
        for rel in (
            "jt-queue/board.md",
            "jt-queue/brief.md",
            "jt-queue/claims.md",
            "jt-queue/tasks/12/task.md",
            "jt-queue/tasks/12.1/plan.md",
        ):
            self.assertEqual(gate.queue_context_class(rel), "commit", rel)

    def test_secrets_and_local_files_stay_out(self) -> None:
        local = {
            "jt-queue/lessons.md": "notes for this agent, not the task",
            ".git/jt-queue/approved-commands.json": "permission to run shell commands",
            ".git/jt-queue/logs/12-test.log": "command output can hold secrets",
            ".git/jt-queue/attempts.json": "this machine's round counter",
            ".git/jt-queue/gate-runs.jsonl": "this machine's gate pass/fail log",
            ".git/jt-queue/worktrees.json": "this machine's worktree paths",
            "jt-queue/.env": "secrets",
            "jt-queue/tasks/12/id_rsa": "private key",
            "jt-queue/secrets/key.pem": "private key",
            "jt-queue/notes.md": "not a resume file",
        }
        for rel in local:
            self.assertEqual(gate.queue_context_class(rel), "local", rel)
        self.assertEqual(gate.queue_context_class("src/app.py"), "outside")


def _hook_yaml(stdout: str) -> str:
    return stdout.split("\n---\n", 1)[1].rsplit("\n---\n", 1)[0]


class PreCommitHookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_proposal_is_pinned_and_writes_nothing(self) -> None:
        result = run_gate_raw(self.repo, "hooks")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("typos = https://github.com/crate-ci/typos @ v1.52.2  [source: spelling]", result.stdout)
        self.assertIn("actionlint = (not added)  [source: no .github/workflows]", result.stdout)
        self.assertIn("zizmor = (not added)  [source: no .github/workflows]", result.stdout)
        self.assertIn("conventional-pre-commit @ v4.5.0", result.stdout)
        self.assertIn("wrote: no", result.stdout)
        self.assertIn("merge: no", result.stdout)
        self.assertIn("hooks-file: .pre-commit-config.yaml  [create]", result.stdout)
        self.assertFalse((self.repo / ".pre-commit-config.yaml").exists())
        yaml = _hook_yaml(result.stdout)
        self.assertIn("rev: v1.52.2", yaml)
        self.assertNotIn("actionlint", yaml)
        self.assertNotIn("zizmor", yaml)
        self.assertIn("stages: [commit-msg]", yaml)

    def test_workflows_and_cheap_board_commands_are_proposed(self) -> None:
        (self.repo / ".github" / "workflows").mkdir(parents=True)
        (self.repo / ".github" / "workflows" / "ci.yml").write_text("name: ci\n", encoding="utf-8")
        (self.repo / "jt-queue").mkdir()
        (self.repo / "jt-queue" / "board.md").write_text(
            board_text("no items", lint="python3 -m ruff check", security="trufflehog filesystem ."),
            encoding="utf-8",
        )
        result = run_gate_raw(self.repo, "hooks")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("jtek-lint = python3 -m ruff check  [source: LINT_CMD, cheap]", result.stdout)
        self.assertIn("jtek-secret = trufflehog filesystem .  [source: SECURITY_CMD, cheap]", result.stdout)
        yaml = _hook_yaml(result.stdout)
        self.assertIn("https://github.com/rhysd/actionlint", yaml)
        self.assertIn("rev: v1.7.12", yaml)
        self.assertIn("https://github.com/zizmorcore/zizmor-pre-commit", yaml)
        self.assertIn("rev: v1.32.0", yaml)
        self.assertIn("id: jtek-lint", yaml)
        self.assertIn("id: jtek-secret", yaml)
        self.assertIn("pass_filenames: false", yaml)
        self.assertFalse((self.repo / ".pre-commit-config.yaml").exists())

    def test_expensive_commands_are_left_out(self) -> None:
        result = run_gate_raw(
            self.repo, "hooks", "--lint", "npm run lint", "--security", "osv-scanner scan ."
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("jtek-lint = (not added)", result.stdout)
        self.assertIn("jtek-secret = (not added)", result.stdout)
        yaml = _hook_yaml(result.stdout)
        self.assertNotIn("jtek-lint", yaml)
        self.assertNotIn("osv-scanner", yaml)
        self.assertNotIn("npm run lint", yaml)
        self.assertEqual(gate.command_tool("npx eslint ."), "eslint")
        self.assertEqual(gate.command_tool("npx --yes eslint"), "")
        self.assertFalse(gate._is_cheap_tool("semgrep scan", gate._CHEAP_LINT_TOOLS))
        self.assertFalse(gate._is_cheap_tool("uvx ruff check", gate._CHEAP_LINT_TOOLS))
        self.assertTrue(gate._is_cheap_tool("npx eslint .", gate._CHEAP_LINT_TOOLS))

    def test_commitlint_config_selects_that_hook(self) -> None:
        (self.repo / "commitlint.config.js").write_text(
            "module.exports = {extends: ['@commitlint/config-conventional']};\n",
            encoding="utf-8",
        )
        result = run_gate_raw(self.repo, "hooks")
        self.assertIn("[source: commitlint.config.js]", result.stdout)
        self.assertIn("@ v9.27.0", result.stdout)
        yaml = _hook_yaml(result.stdout)
        self.assertIn("id: commitlint", yaml)
        self.assertNotIn("conventional-pre-commit", yaml)

    def test_merge_keeps_existing_hooks_and_a_second_write_matches(self) -> None:
        existing = (
            "# team hooks\n"
            "exclude: ^(vendor|dist)/\n"
            "repos:\n"
            "  - repo: https://github.com/crate-ci/typos\n"
            "    rev: v1.0.0\n"
            "    hooks:\n"
            "      - id: typos\n"
            '        args: ["--force-exclude"]\n'
            "  - repo: https://github.com/pre-commit/pre-commit-hooks\n"
            "    rev: v5.0.0\n"
            "    hooks:\n"
            "      - id: trailing-whitespace\n"
            "        args: [--markdown-linebreak-ext=md]\n"
            "fail_fast: true\n"
        )
        path = self.repo / ".pre-commit-config.yaml"
        path.write_text(existing, encoding="utf-8")
        result = run_gate_raw(self.repo, "hooks", "--write", "--lint", "ruff check")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("typos = (kept)", result.stdout)
        merged = path.read_text(encoding="utf-8")
        self.assertIn("# team hooks", merged)
        self.assertIn("exclude: ^(vendor|dist)/", merged)
        self.assertIn("rev: v1.0.0", merged)
        self.assertIn('args: ["--force-exclude"]', merged)
        self.assertIn("id: trailing-whitespace", merged)
        self.assertIn("args: [--markdown-linebreak-ext=md]", merged)
        self.assertIn("fail_fast: true", merged)
        self.assertEqual(merged.count("id: typos"), 1)
        self.assertNotIn("rev: v1.52.2", merged)
        self.assertIn("id: jtek-lint", merged)
        self.assertIn('entry: "ruff check"', merged)
        self.assertIn("id: conventional-pre-commit", merged)
        self.assertNotIn("actionlint", merged)
        again = run_gate_raw(self.repo, "hooks", "--write", "--lint", "ruff check")
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertEqual(path.read_text(encoding="utf-8"), merged)

    def test_a_missing_hook_id_keeps_the_existing_rev(self) -> None:
        path = self.repo / ".pre-commit-config.yaml"
        path.write_text(
            "repos:\n"
            "  - repo: https://github.com/crate-ci/typos\n"
            "    rev: v1.0.0\n"
            "    hooks:\n"
            "      - id: typos-src\n",
            encoding="utf-8",
        )
        result = run_gate_raw(self.repo, "hooks", "--write")
        self.assertEqual(result.returncode, 0, result.stderr)
        merged = path.read_text(encoding="utf-8")
        self.assertIn("rev: v1.0.0", merged)
        self.assertIn("id: typos-src", merged)
        self.assertIn("id: typos", merged)
        self.assertNotIn("rev: v1.52.2", merged)

    def test_an_existing_hook_id_is_not_added_again_from_a_fork(self) -> None:
        path = self.repo / ".pre-commit-config.yaml"
        path.write_text(
            "repos:\n"
            "  - repo: https://example.invalid/typos-fork\n"
            "    rev: deadbeef\n"
            "    hooks:\n"
            "      - id: typos\n",
            encoding="utf-8",
        )
        result = run_gate_raw(self.repo, "hooks", "--write")
        self.assertEqual(result.returncode, 0, result.stderr)
        merged = path.read_text(encoding="utf-8")
        self.assertEqual(merged.count("id: typos"), 1)
        self.assertIn("rev: deadbeef", merged)
        self.assertNotIn("crate-ci/typos", merged)
        self.assertIn("example.invalid/typos-fork", merged)

    def test_unparsed_config_is_not_overwritten(self) -> None:
        path = self.repo / ".pre-commit-config.yaml"
        original = "repos:\n\t- repo: https://github.com/crate-ci/typos\n"
        path.write_text(original, encoding="utf-8")
        preview = run_gate_raw(self.repo, "hooks")
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertIn("[unparsed]", preview.stdout)
        self.assertIn("wrote: no", preview.stdout)
        self.assertEqual(path.read_text(encoding="utf-8"), original)
        written = run_gate_raw(self.repo, "hooks", "--write")
        self.assertEqual(written.returncode, 2)
        self.assertIn("wrote: no", written.stdout)
        self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_local_hooks_are_appended_not_replaced(self) -> None:
        path = self.repo / ".pre-commit-config.yaml"
        path.write_text(
            "repos:\n  - repo: local\n    hooks:\n      - id: mine\n        entry: echo hi\n",
            encoding="utf-8",
        )
        result = run_gate_raw(self.repo, "hooks", "--write", "--lint", "eslint .")
        self.assertEqual(result.returncode, 0, result.stderr)
        merged = path.read_text(encoding="utf-8")
        self.assertIn("id: mine", merged)
        self.assertIn("entry: echo hi", merged)
        self.assertIn("id: jtek-lint", merged)
        self.assertEqual(merged.count("repo: local"), 1)

    def test_create_then_write_is_idempotent(self) -> None:
        (self.repo / ".github" / "workflows").mkdir(parents=True)
        first = run_gate_raw(self.repo, "hooks", "--write")
        self.assertEqual(first.returncode, 0, first.stderr)
        path = self.repo / ".pre-commit-config.yaml"
        body = path.read_text(encoding="utf-8")
        self.assertIn("rev: v1.52.2", body)
        self.assertIn("rev: v1.7.12", body)
        self.assertIn("rev: v1.32.0", body)
        self.assertIn("rev: v4.5.0", body)
        again = run_gate_raw(self.repo, "hooks", "--write")
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertEqual(path.read_text(encoding="utf-8"), body)
        self.assertIn("typos = (kept)", again.stdout)

    def _docs_repo(self) -> None:
        init_repo(self.repo)
        (self.repo / "jt-queue" / "tasks" / "12").mkdir(parents=True)
        (self.repo / "jt-queue" / "board.md").write_text(
            board_text("- [ ] **12** readme (docs)", test=gate.NO_SUITE),
            encoding="utf-8",
        )
        (self.repo / "jt-queue" / "tasks" / "12" / "task.md").write_text(
            card_body(["README.md"], kind="docs"),
            encoding="utf-8",
        )
        (self.repo / "README.md").write_text("# Docs\n", encoding="utf-8")
        commit_all(self.repo, "docs: board")
        git(self.repo, "branch", "task-12")
        git(self.repo, "checkout", "task-12")
        (self.repo / "README.md").write_text("# Docs\n\nMore.\n", encoding="utf-8")
        commit_all(self.repo, "docs: readme")
        git(self.repo, "checkout", "main")

    def _path_env(self, precommit: bool) -> dict[str, str]:
        bin_dir = self.repo / "fake-bin"
        bin_dir.mkdir()
        git_bin = shutil.which("git")
        self.assertIsNotNone(git_bin)
        os.symlink(git_bin, bin_dir / "git")
        if precommit:
            script = bin_dir / "pre-commit"
            script.write_text('#!/bin/sh\ntouch "$HOOK_RAN"\nexit 1\n', encoding="utf-8")
            script.chmod(0o755)
        env = os.environ.copy()
        env["PATH"] = str(bin_dir)
        env["GIT_TERMINAL_PROMPT"] = "0"
        env["HOOK_RAN"] = str(self.repo / "hook-ran")
        return env

    def test_allowed_notes_missing_hooks_and_does_not_run_precommit(self) -> None:
        self._docs_repo()
        result = run_gate_env(self.repo, self._path_env(True), "reach-review", "--id", "12")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("allowed", result.stdout)
        self.assertIn("hooks: missing", result.stdout)
        self.assertIn("ai-review: skip", result.stdout)
        self.assertIn("tier: quick", result.stdout)
        self.assertFalse((self.repo / "hook-ran").exists())

    def test_allowed_notes_ok_when_the_git_hooks_exist(self) -> None:
        self._docs_repo()
        (self.repo / ".pre-commit-config.yaml").write_text(
            "default_install_hook_types:\n"
            "  - pre-commit\n"
            "  - commit-msg\n"
            "repos:\n"
            "  - repo: local\n"
            "    hooks:\n"
            "      - id: conventional-pre-commit\n"
            "        stages: [commit-msg]\n",
            encoding="utf-8",
        )
        hooks = Path(git(self.repo, "rev-parse", "--git-path", "hooks").stdout.strip())
        if not hooks.is_absolute():
            hooks = self.repo / hooks
        hooks.mkdir(parents=True, exist_ok=True)
        for name in ("pre-commit", "commit-msg"):
            (hooks / name).write_text("#!/bin/sh\n# File generated by pre-commit\nexit 0\n", encoding="utf-8")
        result = run_gate_env(self.repo, self._path_env(True), "reach-review", "--id", "12")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("hooks: ok", result.stdout)
        self.assertFalse((self.repo / "hook-ran").exists())

    def test_commit_msg_hook_missing_is_not_ok(self) -> None:
        self._docs_repo()
        (self.repo / ".pre-commit-config.yaml").write_text(
            "repos:\n"
            "  - repo: local\n"
            "    hooks:\n"
            "      - id: conventional-pre-commit\n"
            "        stages: [commit-msg]\n",
            encoding="utf-8",
        )
        hooks = Path(git(self.repo, "rev-parse", "--git-path", "hooks").stdout.strip())
        if not hooks.is_absolute():
            hooks = self.repo / hooks
        hooks.mkdir(parents=True, exist_ok=True)
        (hooks / "pre-commit").write_text("#!/bin/sh\n# pre-commit\n", encoding="utf-8")
        result = run_gate_env(self.repo, self._path_env(True), "reach-review", "--id", "12")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("hooks: missing", result.stdout)

    def test_no_precommit_program_prints_no_hooks_line(self) -> None:
        self._docs_repo()
        result = run_gate_env(self.repo, self._path_env(False), "reach-review", "--id", "12")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("\nhooks:", "\n" + result.stdout)
        self.assertIn("ai-review: skip", result.stdout)
        self.assertIn("gates: secret ok", result.stdout)

    def test_a_failing_check_still_refuses_when_precommit_is_installed(self) -> None:
        init_repo(self.repo)
        (self.repo / "jt-queue" / "tasks" / "12").mkdir(parents=True)
        (self.repo / "jt-queue" / "board.md").write_text(
            board_text(
                "- [ ] **12** readme (docs)",
                test="python3 -c 'import sys; sys.exit(1)'",
            ),
            encoding="utf-8",
        )
        (self.repo / "jt-queue" / "tasks" / "12" / "task.md").write_text(
            card_body(["README.md"], kind="docs"),
            encoding="utf-8",
        )
        (self.repo / "README.md").write_text("# Docs\n", encoding="utf-8")
        commit_all(self.repo, "docs: board")
        git(self.repo, "branch", "task-12")
        git(self.repo, "checkout", "task-12")
        (self.repo / "README.md").write_text("# Docs\n\nMore.\n", encoding="utf-8")
        commit_all(self.repo, "docs: readme")
        git(self.repo, "checkout", "main")
        env = self._path_env(True)
        python_bin = shutil.which("python3")
        self.assertIsNotNone(python_bin)
        os.symlink(python_bin, self.repo / "fake-bin" / "python3")
        result = run_gate_env(self.repo, env, "reach-review", "--id", "12")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refused: test-failed", result.stdout)
        self.assertNotIn("hooks:", result.stdout)
        self.assertFalse((self.repo / "hook-ran").exists())

    def test_fail_fast_order_and_size_hooks_stay(self) -> None:
        self.assertEqual(
            gate.FAIL_FAST, ("secret", "denylist", "typecheck", "lint", "tests", "verify")
        )
        self.assertEqual(
            gate.LARGE_SIZE_HOOKS,
            ("worktree-rounds", "fresh-context-review", "high-risk"),
        )
        self.assertEqual(gate.GATE_REPORT[:6], gate.FAIL_FAST)
