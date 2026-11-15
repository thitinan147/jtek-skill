"""Tests for skills/jt-board/scripts/board.py against fixtures and maps.

Run: python3 -m unittest discover -s tests
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BOARD = REPO / "skills" / "jt-board" / "scripts" / "board.py"
CHECK = REPO / "skills" / "jt-spec-ac" / "scripts" / "check.py"
FIXTURES = REPO / "evals" / "files"


class BoardTests(unittest.TestCase):
    def test_generate_board_from_fixture(self) -> None:
        fixture_dir = FIXTURES / "room-booking" / "scrum-spec"
        with tempfile.TemporaryDirectory() as tmp:
            out_file = Path(tmp) / "board.html"
            res = subprocess.run(
                [sys.executable, "-I", str(BOARD), str(fixture_dir), "-o", str(out_file)],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertTrue(out_file.exists())
            html = out_file.read_text(encoding="utf-8")

            # Check that stories are included
            self.assertIn("rb-12-book-room", html)
            self.assertIn("rb-13-cancel-booking", html)
            self.assertIn("RB-12", html)
            self.assertIn("RB-13", html)

            # Check ACs are rendered
            self.assertIn("AC1", html)
            self.assertIn("EC1", html)

            # Check Decision D1
            self.assertIn("A booking lasts at most 4 hours", html)

            # Check Blocker question
            self.assertIn("BLOCKS DEV", html)
            self.assertIn("1 BLOCKER QUESTION", html)
            self.assertEqual(html.count("READY FOR SPRINT"), 1)
            self.assertIn("✅ Alex · 2026-11-03 (incl. D1)", html)
            self.assertIn("stateDiagram-v2", html)
            self.assertIn("AC1_given --&gt; AC1_then: they look at the", html)

    def test_generate_board_with_map(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            map_file = root / "map.md"
            map_file.write_text("""<!-- scrum-spec -->
# Story map · room-booking

**approve:** ❌ waiting for PO

## Steps

1. Find a room — Staff · PO note
2. Pick date and time — Staff · PO note

## Stories

| Story | Steps | Once done, the user can | Size signal |
|---|---|---|---|
| `rb-12-book-room` | 1–2 | Book a room | existing screen |

## Not now

- Email notifications — postponed

## Questions

| # | Question | Ask | Blocks | Answer |
|---|---|---|---|---|
| Q1 | Proposal: first slice is rb-12 | PO | stories | |
""", encoding="utf-8")

            spec_file = root / "rb-12-book-room" / "spec.md"
            spec_file.parent.mkdir(parents=True, exist_ok=True)
            spec_file.write_text("""<!-- scrum-spec -->
# rb-12-book-room

## Story

- **Ticket:** RB-12
- **Story:** As a user I want to book a room
- **In scope:**
  - Pick room
- **Out of scope:**
  - Email

## Rules

- Max 2 hours

## Acceptance Criteria

**approve:** ✅ Alex · 2026-11-03

| # | Given | When | Then |
|---|---|---|---|
| AC1 | Room free | Click Book | Booked |

## Questions

| # | Question | Ask | Blocks | Answer |
|---|---|---|---|---|

## Decisions

- **D1** Max 2 hours · Alex · 2026-11-03

## Test steps

- **Accounts:** Alex
- **Data to prepare:** none
- **Do not report:** none

### AC1 Booked

1. Click book
""", encoding="utf-8")

            out_file = root / "board.html"
            res = subprocess.run(
                [sys.executable, "-I", str(BOARD), str(root), "-o", str(out_file)],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertTrue(out_file.exists())
            html = out_file.read_text(encoding="utf-8")

            # Check steps
            self.assertIn("Step 1", html)
            self.assertIn("Find a room", html)
            self.assertIn("Step 2", html)

            # Check not now
            self.assertIn("Email notifications", html)

            # Check story & correlated map step
            self.assertIn("Steps 1–2", html)
            self.assertIn("rb-12-book-room", html)

    def test_board_and_check_agree_on_blocking(self) -> None:
        spec = (
            "<!-- scrum-spec -->\n"
            "# rb-99-old-blocks\n\n"
            "## Acceptance Criteria\n\n"
            "**approve:** ✅ Alex · 2026-11-15\n\n"
            "| # | Given | When | Then |\n"
            "|---|---|---|---|\n"
            "| AC1 | The form is open | they look | the fields are empty |\n\n"
            "## Questions\n\n"
            "| # | Question | Ask | Blocks | Answer |\n"
            "|---|---|---|---|---|\n"
            "| Q1 | Which API creates the booking? | BE | tasks | – |\n"
            "| Q2 | Rename the button? | PO | ac | - |\n\n"
            "## Decisions\n\n"
            "- **D1** Keep the form · Alex · 2026-11-15\n"
        )
        ready = spec.replace("tasks", "later").replace("| ac |", "| later |").replace("| – |", "| |").replace("| - |", "| |")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            blocking_spec = root / "blocking" / "spec.md"
            blocking_spec.parent.mkdir()
            blocking_spec.write_text(spec, encoding="utf-8")
            ready_spec = root / "ready" / "spec.md"
            ready_spec.parent.mkdir()
            ready_spec.write_text(ready, encoding="utf-8")

            def both(path: Path) -> tuple[str, str]:
                checked = subprocess.run(
                    [sys.executable, "-I", str(CHECK), str(path)],
                    capture_output=True, text=True, encoding="utf-8",
                )
                out_file = path.parent / "board.html"
                board = subprocess.run(
                    [sys.executable, "-I", str(BOARD), str(path.parent), "-o", str(out_file)],
                    capture_output=True, text=True, encoding="utf-8",
                )
                self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
                self.assertEqual(board.returncode, 0, board.stderr)
                return checked.stdout, out_file.read_text(encoding="utf-8")

            blocking_out, blocking_html = both(blocking_spec)
            ready_out, ready_html = both(ready_spec)

        self.assertIn("blocking: Q1 (tasks · BE), Q2 (ac · PO)", blocking_out)
        self.assertNotIn("READY FOR SPRINT", blocking_html)
        self.assertIn("2 BLOCKER QUESTION", blocking_html)
        self.assertNotIn("blocking", ready_out)
        self.assertIn("READY FOR SPRINT", ready_html)
