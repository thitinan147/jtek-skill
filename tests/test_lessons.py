"""Team lessons: parse, propose, approve, fix lines, and legacy hits."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from test_gate import (
    board_text,
    card_body,
    commit_all,
    git,
    init_repo,
    run_gate,
    run_gate_raw,
    with_ai_review,
)
from test_flow import report

REPO = Path(__file__).resolve().parents[1]
import test_gate

gate = test_gate.gate


def lesson(repo: Path, *args: str):
    return run_gate_raw(repo, "lesson", *args)


class ParseTests(unittest.TestCase):
    def test_round_trip_and_template_header(self) -> None:
        rows = [
            gate.Lesson(
                id="L1",
                wrong="called it dmedasset",
                fix="call it dmecasset",
                enforced="not yet",
                seen=1,
            )
        ]
        text = gate.render_team_lessons(rows)
        parsed, err = gate.parse_team_lessons(text)
        self.assertEqual(err, "")
        self.assertEqual(parsed[0].id, "L1")
        self.assertEqual(parsed[0].enforced, "not yet")
        self.assertEqual(parsed[0].seen, 1)
        template = (REPO / "skills" / "jt-work" / "assets" / "team-lessons.template.md").read_text(
            encoding="utf-8"
        )
        header = "| id | wrong | fix | enforced by | seen | legacy | pattern |"
        self.assertIn(header, text)
        self.assertIn(header, template)
        self.assertIn("not yet", template)
        self.assertIsNone(gate.approved_denylist("not yet"))
        self.assertIsNone(gate.approved_denylist("proposed: denylist: dmedasset -> dmecasset"))
        self.assertIsNone(gate.approved_denylist("denylist: dmedasset -> dmecasset"))
        self.assertEqual(
            gate.approved_denylist("denylist: dmedasset -> dmecasset (approved)"),
            ("dmedasset", "dmecasset"),
        )

    def test_every_refusal_names_a_fix(self) -> None:
        missing = [key for key in gate.NEXT_FOR if not gate.HINT_FOR.get(key)]
        self.assertEqual(missing, [])
        with tempfile.TemporaryDirectory() as tmp:
            result = run_gate_raw(Path(tmp), "reach-review", "--id", "nope")
        self.assertIn("refused: invalid-id", result.stdout)
        self.assertIn("fix: Task ids look like 1 or 1.2 and nothing else.", result.stdout)
        self.assertIn("hint:", result.stdout)


class LessonCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        init_repo(self.repo)
        (self.repo / "jt-queue" / "tasks" / "12").mkdir(parents=True)
        (self.repo / "check.py").write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
        (self.repo / "oldname.py").write_text('name = "dmedasset"\n', encoding="utf-8")
        (self.repo / "other.py").write_text('name = "dmedassets"\n', encoding="utf-8")
        (self.repo / "plain.py").write_text("name = 'room'\n", encoding="utf-8")
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
        plan = self.repo / "jt-queue" / "tasks" / "12"
        plan.mkdir(parents=True, exist_ok=True)
        (plan / "plan.md").write_text(
            with_ai_review(
                "# Plan 12\n\n## evidence\n\n| HEADER_TOKEN | check | ok |\n\n"
                "## review-diff\n\n"
                f"- commit: {head}\n- reviewer: reviewer\n- verdict: pass\n- checked: scope\n"
            ),
            encoding="utf-8",
        )
        commit_all(self.repo, "docs: record review")
        git(self.repo, "checkout", "main")

    def _touch_check(self) -> None:
        git(self.repo, "checkout", "task-12")
        (self.repo / "check.py").write_text(
            "import sys\nsys.exit(0)\n# touched\n",
            encoding="utf-8",
        )
        commit_all(self.repo, "test: touch the check")
        git(self.repo, "checkout", "main")
        self._record_review()

    def _add_retired_line(self) -> None:
        git(self.repo, "checkout", "task-12")
        (self.repo / "app.py").write_text('label = "dmedasset"\n', encoding="utf-8")
        commit_all(self.repo, "feat: use the old name")
        git(self.repo, "checkout", "main")
        self._record_review()

    def _record_twice(self) -> None:
        first = lesson(
            self.repo,
            "--wrong",
            "called it dmedasset",
            "--fix",
            "call it dmecasset",
        )
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.assertIn("enforced by: not yet", first.stdout)
        second = lesson(
            self.repo,
            "--wrong",
            "called it dmedasset",
            "--fix",
            "call it dmecasset",
            "--old",
            "dmedasset",
            "--new",
            "dmecasset",
        )
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertIn("proposal: denylist: dmedasset -> dmecasset", second.stdout)
        self.assertIn("fix: replace dmedasset with dmecasset", second.stdout)
        self.assertIn("a human runs gate.py lesson-approve", second.stdout)

    def test_second_record_proposes_and_does_not_enforce(self) -> None:
        self._add_retired_line()
        self._record_twice()
        deny = self.repo / "jt-queue" / "denylist.txt"
        self.assertFalse(deny.exists())
        text = (self.repo / "jt-queue" / "team-lessons.md").read_text(encoding="utf-8")
        self.assertIn("proposed: denylist: dmedasset -> dmecasset", text)
        self.assertNotIn("(approved)", text)
        missed = run_gate(self.repo, "reach-review", "--id", "12")
        self.assertNotIn("deprecated-name", missed.stdout)
        self.assertIn("denylist skip", missed.stdout)
        bare = text.replace(
            "proposed: denylist: dmedasset -> dmecasset",
            "denylist: dmedasset -> dmecasset",
        )
        (self.repo / "jt-queue" / "team-lessons.md").write_text(bare, encoding="utf-8")
        still = run_gate(self.repo, "reach-review", "--id", "12")
        self.assertNotIn("deprecated-name", still.stdout)
        approved = run_gate_raw(self.repo, "lesson-approve", "--id", "L1")
        self.assertEqual(approved.returncode, 1, approved.stdout)
        self.assertIn("refused: lesson-unapproved", approved.stdout)
        (self.repo / "jt-queue" / "team-lessons.md").write_text(text, encoding="utf-8")
        approved = run_gate_raw(self.repo, "lesson-approve", "--id", "L1")
        self.assertEqual(approved.returncode, 0, approved.stdout + approved.stderr)
        self.assertIn("approved: yes", approved.stdout)
        self.assertIn("merge: no", approved.stdout)
        self.assertIn("dmedasset -> dmecasset", deny.read_text(encoding="utf-8"))
        hit = run_gate(self.repo, "reach-review", "--id", "12")
        self.assertIn("refused: deprecated-name", hit.stdout)
        self.assertIn("fix: replace dmedasset with dmecasset", hit.stdout)
        self.assertIn("app.py:", hit.stdout)
        self.assertNotIn("oldname.py:", hit.stdout)
        again = run_gate_raw(self.repo, "lesson-approve", "--id", "L1")
        self.assertEqual(again.returncode, 0, again.stdout)
        self.assertIn("already: yes", again.stdout)
        self.assertEqual(deny.read_text(encoding="utf-8").count("dmedasset -> dmecasset"), 1)

    def test_not_yet_cannot_be_approved(self) -> None:
        first = lesson(self.repo, "--wrong", "once", "--fix", "do the thing")
        self.assertEqual(first.returncode, 0, first.stdout)
        refused = run_gate_raw(self.repo, "lesson-approve", "--id", "L1")
        self.assertIn("refused: lesson-unapproved", refused.stdout)
        self.assertNotIn("(approved)", (self.repo / "jt-queue" / "team-lessons.md").read_text(encoding="utf-8"))
        self.assertFalse((self.repo / "jt-queue" / "denylist.txt").exists())

    def test_lint_proposal_does_not_change_the_command(self) -> None:
        before = (self.repo / "jt-queue" / "board.md").read_text(encoding="utf-8")
        lesson(self.repo, "--wrong", "bare except", "--fix", "name the error")
        second = lesson(
            self.repo,
            "--wrong",
            "bare except",
            "--fix",
            "name the error",
            "--lint",
            "no bare except",
        )
        self.assertIn("proposal: lint: no bare except", second.stdout)
        self.assertFalse((self.repo / "jt-queue" / "denylist.txt").exists())
        approved = run_gate_raw(self.repo, "lesson-approve", "--id", "L1")
        self.assertEqual(approved.returncode, 0, approved.stdout + approved.stderr)
        self.assertIn("lint: no bare except (approved)", approved.stdout)
        self.assertEqual((self.repo / "jt-queue" / "board.md").read_text(encoding="utf-8"), before)
        legacy = run_gate_raw(self.repo, "lesson-legacy", "--id", "L1")
        self.assertEqual(legacy.returncode, 0, legacy.stdout + legacy.stderr)
        self.assertIn("occurrences: unknown (no pattern to search)", legacy.stdout)
        self.assertIn("task: none", legacy.stdout)
        self.assertNotIn("merge:", (self.repo / "jt-queue" / "board.md").read_text(encoding="utf-8"))

    def test_legacy_task_lists_search_hits_and_spares_untouched_lines(self) -> None:
        self._touch_check()
        self._record_twice()
        approved = run_gate_raw(self.repo, "lesson-approve", "--id", "L1")
        self.assertEqual(approved.returncode, 0, approved.stdout)
        commit_all(self.repo, "docs: share the lesson")
        found = run_gate_raw(self.repo, "lesson-legacy", "--id", "L1")
        self.assertEqual(found.returncode, 0, found.stdout + found.stderr)
        hits = [line[2:] for line in found.stdout.splitlines() if line.startswith("- ")]
        self.assertIn("source: search", found.stdout)
        self.assertTrue(any(hit.startswith("oldname.py:") for hit in hits), found.stdout)
        self.assertFalse(any("jt-queue/" in hit or hit.startswith("other.py") or hit.startswith("plain.py") for hit in hits), found.stdout)
        task_id = next(
            line.split()[1] for line in found.stdout.splitlines() if line.startswith("task: ")
        )
        board = (self.repo / "jt-queue" / "board.md").read_text(encoding="utf-8")
        self.assertIn(f"- [ ] **{task_id}** replace retired name (chore)", board)
        self.assertNotIn("merge:", board)
        task = (self.repo / "jt-queue" / "tasks" / task_id / "task.md").read_text(encoding="utf-8")
        self.assertIn("oldname.py:", task)
        self.assertNotIn("team-lessons.md", task)
        self.assertNotIn("other.py", task)
        open_gate = run_gate(self.repo, "reach-review", "--id", "12")
        self.assertNotIn("deprecated-name", open_gate.stdout)
        self.assertEqual(open_gate.returncode, 0, open_gate.stdout + open_gate.stderr)
        closed = board.replace(
            f"- [ ] **{task_id}** replace retired name (chore)",
            f"- [x] **{task_id}** replace retired name (chore) merge:",
        )
        (self.repo / "jt-queue" / "board.md").write_text(closed, encoding="utf-8")
        later = run_gate(self.repo, "reach-review", "--id", "12")
        self.assertIn("refused: deprecated-name", later.stdout)
        self.assertIn("oldname.py:", later.stdout)
        self.assertIn("fix: replace dmedasset with dmecasset", later.stdout)
        self.assertNotIn('name = "dmedasset"', later.stdout + later.stderr)

    def test_board_lists_lessons_not_yet_enforced(self) -> None:
        lesson(self.repo, "--wrong", "called it dmedasset", "--fix", "call it dmecasset")
        lesson(
            self.repo,
            "--wrong",
            "bare except",
            "--fix",
            "name the error",
        )
        lesson(
            self.repo,
            "--wrong",
            "bare except",
            "--fix",
            "name the error",
            "--lint",
            "no bare except",
        )
        text = report(self.repo, since="2020-01-01", until="2030-01-01")
        self.assertIn("not-yet: L1 wrong: called it dmedasset", text)
        self.assertIn("proposed: L2 lint: no bare except", text)
        self.assertNotIn("ignore previous", text)


if __name__ == "__main__":
    unittest.main()
