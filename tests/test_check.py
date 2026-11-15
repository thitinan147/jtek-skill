"""Tests for skills/jt-spec-ac/scripts/check.py against the fixtures in evals/files/.

Run: python3 -m unittest discover -s tests
Each test copies a fixture into a temporary git-like project, because check.py
resolves cited paths from the git root.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CHECK = REPO / "skills" / "jt-spec-ac" / "scripts" / "check.py"
FIXTURES = REPO / "evals" / "files"


def run(*paths: Path | str) -> tuple[int, str]:
    result = subprocess.run([sys.executable, "-I", str(CHECK), *map(str, paths)],
                            capture_output=True, text=True, encoding="utf-8")
    return result.returncode, result.stdout


class Project:
    """A temporary copy of a fixture with a .git folder, so it acts as its own git root."""

    def __init__(self, fixture: str):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / fixture
        shutil.copytree(FIXTURES / fixture, self.root)
        (self.root / ".git").mkdir()

    def __enter__(self) -> Path:
        return self.root

    def __exit__(self, *exc) -> None:
        self.tmp.cleanup()


def write_spec(root: Path, text: str) -> Path:
    path = root / "scrum-spec" / "x" / "spec.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class CheckTests(unittest.TestCase):
    def test_complete_spec_passes_with_full_coverage(self) -> None:
        with Project("room-booking") as root:
            code, out = run(root / "scrum-spec" / "rb-12-book-room")
        self.assertEqual(code, 0, out)
        self.assertIn("approve: ✅ Alex · 2026-11-03 (incl. D1)", out)
        self.assertIn("AC/EC with no test step: none", out)
        self.assertIn("questions open: 1", out)
        self.assertNotIn("blocking", out)
        self.assertNotIn("vague words", out)

    def test_open_and_unrecorded_questions_are_reported_not_failed(self) -> None:
        with Project("room-booking") as root:
            code, out = run(root / "scrum-spec" / "rb-13-cancel-booking")
        self.assertEqual(code, 0, out)
        self.assertIn("blocking: Q2 (dev · BE)", out)
        self.assertIn("answered, not yet in Decisions: Q1", out)

    def test_folder_is_searched_recursively(self) -> None:
        with Project("room-booking") as root:
            code, out = run(root)
        self.assertEqual(code, 0, out)
        self.assertEqual(out.count("spec.md"), 2)

    def test_bad_spec_reports_every_error(self) -> None:
        with Project("bad") as root:
            code, out = run(root)
        self.assertEqual(code, 1)
        for expected in ("line 1: must start with <!-- scrum-spec",
                         "line 5: approval must come from a person, not an AI",
                         "line 10: 3 cells, the header has 4",
                         "line 14: D1 must be decided by a person, not an AI",
                         "line 15: D2 must end with · <name> · YYYY-MM-DD",
                         "`src/missing/file.ts` not found",
                         "D7 is not in Decisions"):
            self.assertIn(expected, out)

    def test_nickname_ai_is_a_person(self) -> None:
        with Project("room-booking") as root:
            spec = write_spec(root, "<!-- scrum-spec -->\n\n## Acceptance Criteria\n\n**approve:** ✅ Ai · 2026-11-03\n\n"
                                    "## Decisions\n\n- **D1** Keep it · Bot · 2026-11-03\n")
            code, out = run(spec)
        self.assertEqual(code, 0, out)

    def test_new_files_line_suffixes_and_endpoints_are_not_checked_as_missing(self) -> None:
        with Project("room-booking") as root:
            spec = write_spec(root, "<!-- scrum-spec -->\n\n- **Source:** `DELETE /bookings/:id` · "
                                    "`src/booking/cancel.ts` (new) · `src/booking/api.ts:2`\n")
            code, out = run(spec)
        self.assertEqual(code, 0, out)

    def test_code_roots_from_config_are_searched(self) -> None:
        with Project("room-booking") as root:
            (root / "api" / "app").mkdir(parents=True)
            (root / "api" / "app" / "server.py").write_text("", encoding="utf-8")
            spec = write_spec(root, "<!-- scrum-spec -->\n\n- **Source:** `app/server.py`\n")
            self.assertEqual(run(spec)[0], 1)
            (root / "scrum-spec" / "config.md").write_text("code_roots: ., api\n", encoding="utf-8")
            code, out = run(spec)
        self.assertEqual(code, 0, out)

    def test_dotted_names_and_versions_are_not_paths(self) -> None:
        with Project("room-booking") as root:
            spec = write_spec(root, "<!-- scrum-spec -->\n\n- **Source:** `user.role` and `res.status` "
                                    "from `v0.2.0` · `src/booking/api.ts`\n")
            code, out = run(spec)
        self.assertEqual(code, 0, out)

    def test_paths_outside_source_are_not_checked(self) -> None:
        with Project("room-booking") as root:
            spec = write_spec(root, "<!-- scrum-spec -->\n\n## Story\n\n- **In scope:** see `docs/later.md`\n")
            self.assertEqual(run(spec)[0], 0)

    def test_tasks_section_from_0_2_is_kept_and_not_checked(self) -> None:
        with Project("room-booking") as root:
            spec = write_spec(root, "<!-- scrum-spec -->\n\n## Acceptance Criteria\n\n| # | Given | When | Then |\n"
                                    "|---|---|---|---|\n| AC1 | a | b | c |\n\n## Tasks\n\n"
                                    "| Task | Do | AC | Files | Depends on |\n|---|---|---|---|---|\n"
                                    "| FE-01 | Build it | AC9 | `src/missing/file.ts` | – |\n")
            code, out = run(spec)
        self.assertEqual(code, 0, out)
        self.assertNotIn("task", out)

    def test_no_git_root_skips_path_checks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            spec = Path(tmp) / "spec.md"
            spec.write_text("<!-- scrum-spec -->\n\n- **Source:** `src/nope.ts`\n", encoding="utf-8")
            code, out = run(spec)
        self.assertEqual(code, 0, out)
        self.assertIn("paths not checked", out)

    def test_cells_with_escaped_pipes_are_one_cell(self) -> None:
        with Project("room-booking") as root:
            spec = write_spec(root, "<!-- scrum-spec -->\n\n| # | Given | When | Then |\n|---|---|---|---|\n"
                                    "| AC1 | a \\| b | c | d |\n")
            self.assertEqual(run(spec)[0], 0)

    def test_assumptions_stay_visible_to_the_asked_role(self) -> None:
        with Project("room-booking") as root:
            spec = write_spec(root, "<!-- scrum-spec -->\n\n## Questions\n\n"
                                    "| # | Question | Ask | Blocks | Answer |\n|---|---|---|---|---|\n"
                                    "| Q1 | Cancel API? | BE | dev | ⚠️ D1 |\n\n"
                                    "## Decisions\n\n- **D1** assumption: DELETE /bookings/:id · Pat · 2026-11-12 (Q1)\n")
            code, out = run(spec)
        self.assertEqual(code, 0, out)
        self.assertIn("questions open: 0", out)
        self.assertIn("assumptions waiting for the asked role to confirm: Q1 (BE)", out)

    def test_missing_test_steps_are_reported(self) -> None:
        with Project("room-booking") as root:
            spec = write_spec(root, "<!-- scrum-spec -->\n\n## Acceptance Criteria\n\n| # | Given | When | Then |\n"
                                    "|---|---|---|---|\n| AC1 | a | b | c |\n| EC1 | a | b | c |\n\n"
                                    "## Test steps\n\n### AC1 Works\n\n1. Open it\n")
            code, out = run(spec)
        self.assertEqual(code, 0, out)
        self.assertIn("AC/EC with no test step: EC1", out)

    def test_decisions_of_other_specs_are_not_checked_here(self) -> None:
        with Project("room-booking") as root:
            spec = write_spec(root, "<!-- scrum-spec -->\n\n## Decisions\n\n"
                                    "- **D1** per rb-12-book-room D3: bookings start on the hour · Pat · 2026-11-12\n")
            code, out = run(spec)
        self.assertEqual(code, 0, out)

    def test_skill_decision_forms_must_exist(self) -> None:
        with Project("room-booking") as root:
            spec = write_spec(root, "<!-- scrum-spec -->\n\n## Acceptance Criteria\n\n"
                                    "**approve:** ✅ Tek · 2026-11-15 (incl. D1, D9)\n\n"
                                    "## Questions\n\n"
                                    "| # | Question | Ask | Blocks | Answer |\n|---|---|---|---|---|\n"
                                    "| Q1 | Ship it? | PO | later | ⚠️ D8 |\n\n"
                                    "## Rules\n\n- Room D4 is the large room\n\n"
                                    "## Decisions\n\n- **D1** Keep the large room · Tek · 2026-11-15\n")
            code, out = run(spec)
        self.assertEqual(code, 1, out)
        self.assertIn("D9 is not in Decisions", out)
        self.assertIn("D8 is not in Decisions", out)
        self.assertNotIn("D4 is not in Decisions", out)
        self.assertNotIn("D1 is not in Decisions", out)

    def test_vague_words_in_ac_are_notes(self) -> None:
        scripts = str(CHECK.parent)
        sys.dont_write_bytecode = True
        sys.path.insert(0, scripts)
        try:
            import check as check_mod
        finally:
            sys.path.remove(scripts)
        thai = next(word for word in check_mod.VAGUE_WORDS if not word.isascii())
        with Project("room-booking") as root:
            spec = write_spec(root, "<!-- scrum-spec -->\n\n## Story\n\n- **Story:** Make it fast for staff\n\n"
                                    "## Acceptance Criteria\n\n| # | Given | When | Then |\n|---|---|---|---|\n"
                                    f"| AC1 | a | b | It should feel Nice and user-friendly |\n"
                                    f"| EC1 | {thai} | b | breakfast is ready |\n")
            code, out = run(spec)
        self.assertEqual(code, 0, out)
        self.assertIn("vague words in AC/EC: AC1 'nice', AC1 'user-friendly', EC1 '" + thai + "'", out)
        self.assertNotIn("'fast'", out)

    def test_help_prints_usage(self) -> None:
        code, out = run("--help")
        self.assertEqual(code, 0)
        self.assertIn("Usage:", out)

    def test_no_documents_found_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, out = run(tmp)
        self.assertEqual(code, 1)
        self.assertIn("no spec.md or map.md", out)


if __name__ == "__main__":
    unittest.main()
