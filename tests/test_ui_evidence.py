"""Screen evidence, console findings, and snapshot updates the gate must not accept."""

import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GATE_PATH = REPO / "skills" / "jt-work" / "scripts" / "gate.py"


def load_gate():
    import importlib.util

    prev = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec = importlib.util.spec_from_file_location("tek_ui_gate", GATE_PATH)
        module = importlib.util.module_from_spec(spec)
        sys.modules["tek_ui_gate"] = module
        spec.loader.exec_module(module)
        return module
    finally:
        sys.dont_write_bytecode = prev


gate = load_gate()


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )


def commit_all(repo: Path, message: str) -> None:
    git(repo, "add", "-A")
    git(repo, "commit", "-m", message)


def run_gate(repo: Path, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    if args and args[0] == "reach-review" and "--id" in args:
        card_id = args[args.index("--id") + 1]
        subprocess.run(
            [sys.executable, str(GATE_PATH), "approve-commands", "--id", card_id, "--root", str(repo)],
            cwd=repo,
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
    return subprocess.run(
        [sys.executable, str(GATE_PATH), *args, "--root", str(repo)],
        cwd=repo,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def init_repo(repo: Path) -> None:
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Test")


SCREEN_TASK = """\
# 12 - button

kind: feat

size: small

screen: yes

do:
- show the button

out:
- other

pass:
- AC1: the button shows

files:
- app.py

ask:
"""


def evidence_plan(row: str, sha: str) -> str:
    return (
        "# Plan 12\n\n## evidence\n\n"
        "| pass line | command or artifact | result |\n"
        "|---|---|---|\n"
        f"{row}\n\n"
        "## review-diff\n\n"
        f"sha: {sha}\n"
        "verdict: pass\n"
        "checked: scope\n"
    )


class ScreenEvidenceTests(unittest.TestCase):
    def test_a_screen_ac_needs_a_screenshot_tied_to_that_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task = root / "jt-queue" / "tasks" / "12"
            task.mkdir(parents=True)
            (task / "task.md").write_text(SCREEN_TASK, encoding="utf-8")
            missing = "| AC1: the button shows | check | ok |"
            gaps = gate.evidence_gaps(root, "12", evidence_plan(missing, "abc"))
            self.assertTrue(any("screenshot" in gap for gap in gaps), gaps)
            video_only = "| AC1: the button shows | e2e/ac1.webm | ok |"
            video_gaps = gate.evidence_gaps(root, "12", evidence_plan(video_only, "abc"))
            self.assertTrue(any("screenshot" in gap for gap in video_gaps), video_gaps)
            shot = "| AC1: the button shows | e2e/ac1.png e2e/ac1.webm | ok |"
            self.assertEqual(gate.evidence_gaps(root, "12", evidence_plan(shot, "abc")), [])
            (task / "task.md").write_text(SCREEN_TASK.replace("screen: yes", "screen: no"), encoding="utf-8")
            self.assertEqual(gate.evidence_gaps(root, "12", evidence_plan(missing, "abc")), [])

    def test_a_screen_pass_line_without_an_ac_id_keeps_the_old_evidence_rule(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task = root / "jt-queue" / "tasks" / "12"
            task.mkdir(parents=True)
            (task / "task.md").write_text(
                "screen: yes\npass:\n- HEADER_TOKEN\n",
                encoding="utf-8",
            )
            row = "| HEADER_TOKEN | check | ok |"
            self.assertEqual(gate.evidence_gaps(root, "12", evidence_plan(row, "abc")), [])


class ConsoleFindingTests(unittest.TestCase):
    def test_console_and_network_errors_are_findings(self) -> None:
        hidden = evidence_plan(
            "| AC1: the button shows | e2e/ac1.png | ok console error: Uncaught TypeError |",
            "abc",
        )
        self.assertTrue(gate.unrecorded_console_findings(hidden))
        self.assertTrue(gate.console_findings("[ERROR] Failed to load resource: 404 @ /api/users"))
        self.assertTrue(gate.console_findings("page error: Uncaught ReferenceError: x"))
        self.assertTrue(gate.console_findings("net::ERR_CONNECTION_REFUSED"))
        recorded = evidence_plan(
            "| AC1: the button shows | e2e/ac1.png | finding: console error Uncaught TypeError |",
            "abc",
        )
        self.assertEqual(gate.unrecorded_console_findings(recorded), [])
        prose = recorded.replace(
            "## review-diff",
            "[ERROR] Failed to load resource: 404 @ /api/users\n\n## review-diff",
        )
        self.assertTrue(gate.unrecorded_console_findings(prose))


class SnapshotUpdateTests(unittest.TestCase):
    def test_verify_does_not_accept_new_snapshots(self) -> None:
        self.assertTrue(gate.updates_snapshots("npx playwright test --update-snapshots"))
        self.assertTrue(gate.updates_snapshots("npx playwright test -u"))
        self.assertFalse(gate.updates_snapshots("npx playwright test"))
        self.assertFalse(gate.updates_snapshots("python3 -c 'import sys; sys.exit(0)'"))
        self.assertEqual(
            gate.snapshot_block_reason("npx playwright test", gate.MINIMAL_PLAYWRIGHT_CONFIG),
            "",
        )
        self.assertIn("toHaveScreenshot", gate.MINIMAL_PLAYWRIGHT_CONFIG)
        self.assertIn('updateSnapshots: "none"', gate.MINIMAL_PLAYWRIGHT_CONFIG)
        self.assertNotIn("--update-snapshots", gate.MINIMAL_PLAYWRIGHT_CONFIG)
        self.assertNotEqual(gate.snapshot_block_reason("npx playwright test", "export default {}"), "")
        self.assertNotEqual(
            gate.snapshot_block_reason(
                "npx playwright test --update-snapshots",
                gate.MINIMAL_PLAYWRIGHT_CONFIG,
            ),
            "",
        )
        self.assertTrue(gate.config_writes_snapshots('updateSnapshots: "missing"'))
        self.assertFalse(gate.config_writes_snapshots('updateSnapshots: "none"'))

    def test_fail_fast_order_is_unchanged(self) -> None:
        self.assertEqual(
            gate.FAIL_FAST,
            ("secret", "denylist", "typecheck", "lint", "tests", "verify"),
        )


class ReachReviewUiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        init_repo(self.repo)
        (self.repo / "app.py").write_text("VALUE = 0\n", encoding="utf-8")
        (self.repo / "jt-queue" / "tasks" / "12").mkdir(parents=True)
        commit_all(self.repo, "chore: init")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _board(self, test: str, verify: str = "", browser: str = "") -> None:
        text = (
            "# Board - app\n\nqueue: main\n\n"
            "| Value | In this repo |\n|---|---|\n"
            f"| `<TEST_CMD>` | {test} |\n"
            f"| `<VERIFY_CMD>` | {verify} |\n"
            f"| `<BROWSER_TOOL>` | {browser} |\n"
            "| `<STACK_LOCK>` | py · none · test · ban |\n\n"
            "## first\n\n- [ ] **12** button (feat)\n\n"
            "## main\n\nno items\n\n## later\n\nno items\n"
        )
        (self.repo / "jt-queue" / "board.md").write_text(text, encoding="utf-8")

    def _branch_with_plan(self, task: str, row: str, extra: str = "") -> None:
        (self.repo / "jt-queue" / "tasks" / "12" / "task.md").write_text(task, encoding="utf-8")
        self._board("python3 -c 'import sys; sys.exit(0)'")
        commit_all(self.repo, "docs: add the task")
        git(self.repo, "checkout", "-b", "task-12")
        (self.repo / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
        if extra:
            (self.repo / "playwright.config.ts").write_text(extra, encoding="utf-8")
        commit_all(self.repo, "feat: show the button")
        sha = git(self.repo, "rev-parse", "HEAD").stdout.strip()
        plan = self.repo / "jt-queue" / "tasks" / "12" / "plan.md"
        plan.write_text(evidence_plan(row, sha), encoding="utf-8")
        commit_all(self.repo, "docs: record evidence")
        git(self.repo, "checkout", "main")

    def test_screen_task_without_a_screenshot_cannot_reach_review(self) -> None:
        self._branch_with_plan(SCREEN_TASK, "| AC1: the button shows | check | ok |")
        result = run_gate(self.repo, "reach-review", "--id", "12")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("refused: review-diff", result.stdout)
        self.assertIn("evidence-missing", result.stdout)
        self.assertIn("screenshot", result.stdout)
        self.assertIn("AC1", result.stdout)

    def test_a_console_error_on_a_touched_screen_is_a_finding(self) -> None:
        row = "| AC1: the button shows | e2e/ac1.png | ok console error: Uncaught TypeError |"
        self._branch_with_plan(SCREEN_TASK, row)
        result = run_gate(self.repo, "reach-review", "--id", "12")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("refused: console-error", result.stdout)
        self.assertIn("Uncaught TypeError", result.stdout)
        self.assertIn("next: retry", result.stdout)
        self.assertNotIn("round ", result.stdout)

    def test_snapshot_update_is_refused_before_the_command_runs(self) -> None:
        marker = self.repo / "snapshot-ran"
        task = SCREEN_TASK.replace("screen: yes\n", "screen: no\n")
        row = "| AC1: the button shows | python3 -c pass | ok |"
        self._branch_with_plan(task, row)
        verify = f"touch {marker} && npx playwright test --update-snapshots"
        self._board("python3 -c 'import sys; sys.exit(0)'", verify=verify)
        result = run_gate(self.repo, "reach-review", "--id", "12")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("refused: snapshot-update", result.stdout)
        self.assertIn("next: ask", result.stdout)
        self.assertFalse(marker.exists(), "verify must not run when it would update snapshots")
        self.assertNotIn("round ", result.stdout)

    def test_playwright_test_runs_when_snapshots_stay_none(self) -> None:
        marker = self.repo / "verify-ran"
        bindir = self.repo / "bin"
        bindir.mkdir()
        fake = bindir / "playwright"
        fake.write_text(f"#!/bin/sh\nprintf '%s\\n' \"$@\" > {marker}\nexit 0\n", encoding="utf-8")
        fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
        task = SCREEN_TASK.replace("screen: yes\n", "screen: no\n")
        row = "| AC1: the button shows | python3 -c pass | ok |"
        self._branch_with_plan(task, row, extra=gate.MINIMAL_PLAYWRIGHT_CONFIG)
        self._board("python3 -c 'import sys; sys.exit(0)'", verify="playwright test")
        env = os.environ.copy()
        env["PATH"] = f"{bindir}{os.pathsep}{env.get('PATH', '')}"
        result = run_gate(self.repo, "reach-review", "--id", "12", env=env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("verify ok", result.stdout)
        self.assertEqual(marker.read_text(encoding="utf-8").strip(), "test")


class SetupPlaywrightTests(unittest.TestCase):
    def test_a_web_app_proposes_verify_and_a_config_that_does_not_write_snapshots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                '{"dependencies":{"react":"18.0.0","react-dom":"18.0.0"}}\n',
                encoding="utf-8",
            )
            detected = run_gate(root, "detect")
            self.assertEqual(detected.returncode, 0, detected.stdout)
            self.assertIn("VERIFY_CMD = npx playwright test  [source: package.json react]", detected.stdout)
            self.assertIn("BROWSER_TOOL = playwright", detected.stdout)
            self.assertIn("feature-map: none", detected.stdout)
            self.assertIn("playwright-config: propose", detected.stdout)
            shown = run_gate(root, "playwright")
            self.assertIn('updateSnapshots: "none"', shown.stdout)
            self.assertIn("toHaveScreenshot", shown.stdout)
            self.assertNotIn("--update-snapshots", shown.stdout)
            self.assertFalse((root / "playwright.config.ts").exists())
            wrote = run_gate(root, "playwright", "--write")
            self.assertIn("wrote: playwright.config.ts", wrote.stdout)
            config = (root / "playwright.config.ts").read_text(encoding="utf-8")
            self.assertEqual(config, gate.MINIMAL_PLAYWRIGHT_CONFIG)
            again = run_gate(root, "playwright", "--write")
            self.assertIn("playwright-config: present", again.stdout)
            self.assertNotIn("wrote:", again.stdout)
            self.assertEqual((root / "playwright.config.ts").read_text(encoding="utf-8"), config)

    def test_a_library_does_not_get_a_playwright_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                '{"devDependencies":{"vitest":"1.0.0"}}\n',
                encoding="utf-8",
            )
            detected = run_gate(root, "detect")
            self.assertIn("VERIFY_CMD = (empty)  [source: not a web app]", detected.stdout)
            self.assertNotIn("BROWSER_TOOL", detected.stdout)
            skipped = run_gate(root, "playwright", "--write")
            self.assertIn("playwright: skip", skipped.stdout)
            self.assertFalse((root / "playwright.config.ts").exists())

    def test_index_html_is_a_web_app_and_express_alone_is_not(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text('{"dependencies":{"express":"4.0.0"}}\n', encoding="utf-8")
            self.assertEqual(gate.detect_web_app(root), (False, ""))
            (root / "index.html").write_text("<!doctype html><title>app</title>\n", encoding="utf-8")
            web, source = gate.detect_web_app(root)
            self.assertTrue(web)
            self.assertEqual(source, "index.html")

    def test_feature_map_names_create_verification_skill_when_installed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "index.html").write_text("<!doctype html>\n", encoding="utf-8")
            skill = root / ".agents" / "skills" / "create-verification-skill"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text("---\nname: create-verification-skill\n---\n", encoding="utf-8")
            detected = run_gate(root, "detect")
            self.assertIn("feature-map: create-verification-skill", detected.stdout)
            self.assertTrue(gate.verification_skill_installed(root))


class ScreenDocTests(unittest.TestCase):
    def test_skills_and_install_docs_name_the_cli_and_the_verify_slot(self) -> None:
        work = (REPO / "skills" / "jt-work" / "SKILL.md").read_text(encoding="utf-8")
        playbooks = (REPO / "skills" / "jt-work" / "references" / "playbooks.md").read_text(encoding="utf-8")
        setup = (REPO / "skills" / "jt-setup" / "SKILL.md").read_text(encoding="utf-8")
        guide = (REPO / "skills" / "jt-setup" / "references" / "playwright.md").read_text(encoding="utf-8")
        readme = (REPO / "README.md").read_text(encoding="utf-8")
        install = (REPO / "skills" / "jt-help" / "references" / "install-before-use.md").read_text(encoding="utf-8")
        self.assertIn("playwright-cli -s=<ticket-id>", work)
        self.assertIn("not Playwright MCP", work)
        self.assertIn("toHaveScreenshot", work)
        self.assertIn("--update-snapshots", work)
        self.assertIn("playwright-cli install --skills", playbooks)
        self.assertIn("npm install -g @playwright/cli@latest", playbooks)
        self.assertIn("https://playwright.dev/docs/getting-started-cli", playbooks)
        self.assertIn("https://playwright.dev/agent-cli/skills", playbooks)
        self.assertIn("console error", playbooks)
        self.assertIn("references/playwright.md", setup)
        self.assertIn("create-verification-skill", guide)
        self.assertIn("npx playwright test", guide)
        self.assertIn("updateSnapshots", guide)
        self.assertIn("feature-map", guide)
        row = next(line for line in readme.splitlines() if "Playwright CLI" in line)
        self.assertIn("npm install -g @playwright/cli@latest", row)
        self.assertIn("playwright-cli install --skills", row)
        self.assertNotIn("--skills -g", row)
        self.assertIn("VERIFY_CMD", row)
        self.assertIn("https://playwright.dev/docs/getting-started-cli", row)
        self.assertIn("https://playwright.dev/agent-cli/skills", row)
        help_row = next(line for line in install.splitlines() if "Playwright CLI" in line)
        self.assertIn("VERIFY_CMD", help_row)
        self.assertIn("https://playwright.dev/agent-cli/skills", help_row)
        self.assertIn("playwright-cli install --skills", help_row)
        self.assertNotIn("TEST_CMD", help_row)


if __name__ == "__main__":
    unittest.main()
