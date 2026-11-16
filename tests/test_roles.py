"""Roles on a spec, and the gate's human-only refusal."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from test_check import run, write_spec, Project
from test_gate import (
    AI_REVIEW_BLOCK,
    board_text,
    commit_all,
    gate,
    git,
    init_repo,
    run_gate,
)


def _roles(areas: str = "`src/auth/**` · payments", merger: str = "Alex", approver: str = "Alex") -> str:
    return (
        "<!-- scrum-spec -->\n\n## Roles\n\n"
        f"- **approver:** {approver}\n"
        "- **reviewer:** Sam\n"
        f"- **merger:** {merger}\n"
        f"- **human-only:** {areas}\n"
    )


class RoleCheckTests(unittest.TestCase):
    def test_a_named_human_section_passes(self) -> None:
        with Project("room-booking") as root:
            spec = write_spec(root, _roles())
            code, out = run(spec)
        self.assertEqual(code, 0, out)
        self.assertNotIn("ERROR", out)

    def test_missing_section_is_a_migration_with_a_fix(self) -> None:
        with Project("room-booking") as root:
            spec = write_spec(root, "<!-- scrum-spec -->\n\n## Story\n\n- **Story:** Book a room\n")
            code, out = run(spec)
        self.assertEqual(code, 0, out)
        self.assertIn("migration: spec has no ## Roles section", out)
        self.assertIn("fix:", out)

    def test_missing_approver_and_an_ai_merger_fail_with_fix(self) -> None:
        with Project("room-booking") as root:
            spec = write_spec(root, _roles(merger="Claude", approver="-"))
            code, out = run(spec)
        self.assertEqual(code, 1, out)
        self.assertIn("approver is missing", out)
        self.assertIn("merger must be a person, not an AI", out)
        self.assertIn("fix:", out)

    def test_a_bad_glob_fails_with_fix(self) -> None:
        with Project("room-booking") as root:
            spec = write_spec(root, _roles(areas="`../secrets/**` · `/etc/*` · `src/***`"))
            code, out = run(spec)
        self.assertEqual(code, 1, out)
        self.assertIn("../secrets/**", out)
        self.assertIn("fix:", out)
        self.assertIn("not well-formed", out)

    def test_empty_human_only_is_allowed(self) -> None:
        with Project("room-booking") as root:
            code, out = run(write_spec(root, _roles(areas="-")))
        self.assertEqual(code, 0, out)


class HumanOnlyMatchTests(unittest.TestCase):
    def test_globs_and_topics_match_only_what_they_name(self) -> None:
        self.assertTrue(gate.path_in_area("src/auth/login.py", "src/auth/**"))
        self.assertTrue(gate.path_in_area("src/payments/api.ts", "payments"))
        self.assertFalse(gate.path_in_area("src/author.py", "auth"))
        self.assertFalse(gate.path_in_area("src/paymentstuff.ts", "payments"))
        self.assertFalse(gate.path_in_area("src/app.py", "src/auth/**"))

    def test_signoff_must_name_the_spec_approver(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = root / "scrum-spec" / "book" / "spec.md"
            spec.parent.mkdir(parents=True)
            spec.write_text(
                _roles()
                + "\n## Acceptance Criteria\n\n**approve:** ✅ Alex · 2026-11-03\n",
                encoding="utf-8",
            )
            task = "spec: scrum-spec/book/spec.md\n"
            detail, fix = gate.human_only_problem(root, task, ["src/auth/login.py"])
            self.assertIn("src/auth/login.py", detail)
            self.assertIn("human-sign-off", fix)
            self.assertIn("Alex", fix)
            self.assertIsNone(
                gate.human_only_problem(
                    root,
                    task + "human-sign-off: ✅ Alex · 2026-11-16\n",
                    ["src/auth/login.py"],
                )
            )
            self.assertIsNotNone(
                gate.human_only_problem(
                    root,
                    task + "human-sign-off: ✅ Sam · 2026-11-16\n",
                    ["src/payments/fee.ts"],
                )
            )
            self.assertIsNone(gate.human_only_problem(root, task, ["src/app.py"]))


class HumanOnlyGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        init_repo(self.repo)
        (self.repo / "jt-queue" / "tasks" / "12").mkdir(parents=True)
        (self.repo / "check.py").write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
        spec = self.repo / "scrum-spec" / "book" / "spec.md"
        spec.parent.mkdir(parents=True)
        spec.write_text(
            _roles()
            + "\n## Acceptance Criteria\n\n**approve:** ✅ Alex · 2026-11-03\n\n"
            "| # | Given | When | Then | Guards |\n|---|---|---|---|---|\n"
            "| AC1 | staff | look | the button is enabled | |\n\n"
            "## Questions\n\n| # | Question | Ask | Blocks | Answer |\n|---|---|---|---|---|\n"
            "| Q1 | Spinner? | UX | later | |\n",
            encoding="utf-8",
        )
        self._write_task("")
        (self.repo / "jt-queue" / "board.md").write_text(
            board_text("- [ ] **12** book (feat)", test=gate.NO_SUITE),
            encoding="utf-8",
        )
        commit_all(self.repo, "docs: add the board")
        git(self.repo, "checkout", "-b", "task-12")
        path = self.repo / "src" / "auth" / "login.py"
        path.parent.mkdir(parents=True)
        path.write_text("def login():\n    return True\n", encoding="utf-8")
        commit_all(self.repo, "feat: touch auth")
        git(self.repo, "checkout", "main")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _write_task(self, signoff: str) -> None:
        (self.repo / "jt-queue" / "tasks" / "12" / "task.md").write_text(
            "# 12 - book\n\nkind: feat\n\nsize: small\n\n"
            "spec: scrum-spec/book/spec.md\n\n"
            "do:\n- book\n\nout:\n- other\n\n"
            "pass:\n- AC1: the button is enabled\n\n"
            "files:\n- src/auth/login.py\n\n"
            f"{signoff}"
            "ask:\n",
            encoding="utf-8",
        )

    def _plan(self) -> None:
        git(self.repo, "checkout", "task-12")
        sha = git(self.repo, "rev-parse", "HEAD").stdout.strip()
        plan = self.repo / "jt-queue" / "tasks" / "12" / "plan.md"
        plan.write_text(
            "# Plan 12\n\n## evidence\n\n| AC1: the button is enabled | check | ok |\n\n"
            "## review-diff\n\n"
            f"- commit: {sha}\n- reviewer: reviewer\n- verdict: pass\n- checked: scope\n"
            + AI_REVIEW_BLOCK,
            encoding="utf-8",
        )
        commit_all(self.repo, "docs: record review")
        git(self.repo, "checkout", "main")

    def test_a_human_only_diff_is_refused_until_the_approver_signs(self) -> None:
        result = run_gate(self.repo, "reach-review", "--id", "12")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("refused: human-only", result.stdout)
        self.assertIn("step: human-only", result.stdout)
        self.assertIn("skipped: secret", result.stdout)
        self.assertIn("fix:", result.stdout)
        self.assertIn("Alex", result.stdout)
        self.assertIn("merge: no", result.stdout)
        self._plan()
        self._write_task("human-sign-off: ✅ Alex · 2026-11-16\n")
        allowed = run_gate(self.repo, "reach-review", "--id", "12")
        self.assertEqual(allowed.returncode, 0, allowed.stdout + allowed.stderr)
        self.assertIn("human-only: ok", allowed.stdout)
        self.assertIn("merge: no", allowed.stdout)


if __name__ == "__main__":
    unittest.main()
