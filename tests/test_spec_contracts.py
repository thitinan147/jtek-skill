"""Contracts carried over from scrum-spec: markers, language, size, and the checker.

The command names changed. check.py, board.py, and specdoc.py did not.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SKILLS = REPO / "skills"
SPEC_SKILLS = ("jt-spec-split", "jt-spec-ac", "jt-spec-handoff", "jt-board", "jt-help")
LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
THAI = re.compile(f"[{chr(0x0E00)}-{chr(0x0E7F)}]")
MARKERS = (
    "<!-- scrum-spec -->",
    "**approve:** ❌ waiting for PO",
    "**approve:** ✅ <name> · <YYYY-MM-DD>",
    "- **D<n>** <what was decided> · <name> · <YYYY-MM-DD>",
    "⚠️ D<n>",
    "per <work> D<n>:",
    "**Source:**",
    "## Acceptance Criteria",
    "## Questions",
    "## Decisions",
    "## Test steps",
    "| # | Given | When | Then |",
    "| # | Given | When | Then | Guards |",
    "| # | Question | Ask | Blocks | Answer |",
)


def _allowed_thai(path: Path) -> bool:
    allowed = {
        (SKILLS / "jt-spec-ac" / "references" / "input.md").resolve(),
        (SKILLS / "jt-spec-ac" / "scripts" / "check.py").resolve(),
        (REPO / "evals" / "evals.json").resolve(),
    }
    try:
        resolved = path.resolve()
    except OSError:
        return False
    if resolved in allowed:
        return True
    # Spec skills ship real copies of the checker and the PDF notes.
    try:
        data = path.read_bytes()
    except OSError:
        return False
    return any(origin.is_file() and origin.read_bytes() == data for origin in allowed)


class SpecContractTests(unittest.TestCase):
    def test_one_run_loads_at_most_1500_words(self) -> None:
        for name in ("jt-spec-split", "jt-spec-ac", "jt-spec-handoff"):
            skill = SKILLS / name
            words = len((skill / "SKILL.md").read_text(encoding="utf-8").split())
            words += len((skill / "references" / "rules.md").read_text(encoding="utf-8").split())
            self.assertLessEqual(words, 1500, f"{name}: {words} words")
        for name in ("jt-spec-split", "jt-spec-ac", "jt-spec-handoff"):
            text = (SKILLS / name / "references" / "input.md").read_text(encoding="utf-8")
            self.assertLessEqual(len(text.split()), 450, name)

    def test_checker_markers_appear_in_the_prompts(self) -> None:
        prompts = "\n".join(
            path.read_text(encoding="utf-8")
            for name in SPEC_SKILLS
            for path in (SKILLS / name).rglob("*.md")
        )
        for marker in MARKERS:
            self.assertIn(marker, prompts, marker)

    def test_fixtures_follow_the_story_section_order(self) -> None:
        spec = (REPO / "evals" / "files" / "room-booking" / "scrum-spec" / "rb-12-book-room" / "spec.md").read_text(
            encoding="utf-8"
        )
        order = [line for line in spec.splitlines() if line.startswith("## ")]
        self.assertEqual(
            order,
            ["## Story", "## Rules", "## Acceptance Criteria", "## Questions", "## Decisions", "## Test steps"],
        )
        ac = (SKILLS / "jt-spec-ac" / "SKILL.md").read_text(encoding="utf-8")
        for section in order:
            if section == "## Test steps":
                self.assertIn(section, (SKILLS / "jt-spec-handoff" / "SKILL.md").read_text(encoding="utf-8"))
            else:
                self.assertIn(section, ac)

    def test_backticked_skill_files_exist(self) -> None:
        for name in ("jt-spec-split", "jt-spec-ac", "jt-spec-handoff", "jt-board"):
            skill = SKILLS / name
            for md_file in skill.rglob("*.md"):
                for ref in re.findall(r"`((?:references|scripts)/[A-Za-z0-9._-]+)`", md_file.read_text(encoding="utf-8")):
                    self.assertTrue((skill / ref).exists(), f"{md_file} cites missing {ref}")

    def test_no_claude_only_variables_in_spec_skills(self) -> None:
        for name in SPEC_SKILLS:
            for md_file in (SKILLS / name).rglob("*.md"):
                self.assertNotIn("${CLAUDE_SKILL_DIR}", md_file.read_text(encoding="utf-8"), str(md_file))

    def test_no_thai_outside_allowed_places(self) -> None:
        # tests/test_gate.py already uses a Thai status token to prove the gate
        # rejects it. That fixture predates the spec skills and is not a prompt.
        for path in REPO.rglob("*"):
            if ".git" in path.parts or not path.is_file():
                continue
            if path == REPO / "tests" / "test_gate.py" or _allowed_thai(path):
                continue
            if path.suffix in {".md", ".py", ".json", ".yaml", ".yml", ".txt"}:
                self.assertIsNone(THAI.search(path.read_text(encoding="utf-8")), str(path.relative_to(REPO)))

    def test_readme_names_the_board_and_the_release(self) -> None:
        readme = (REPO / "README.md").read_text(encoding="utf-8")
        security = (REPO / "SECURITY.md").read_text(encoding="utf-8")
        self.assertNotIn("Three commands", readme)
        self.assertIn("v24.4.0", readme)
        self.assertIn("board.py", security)
        self.assertIn("Google Fonts", security)
        self.assertIn("fonts.googleapis.com", security)
        evals = json.loads((REPO / "evals" / "evals.json").read_text(encoding="utf-8"))
        self.assertTrue(any(item["query"].startswith("/jt-board") for item in evals))
        for target in LINK_RE.findall((REPO / "docs" / "spec.md").read_text(encoding="utf-8")):
            if target.startswith(("http://", "https://", "#")):
                continue
            self.assertTrue(((REPO / "docs" / "spec.md").parent / target.split("#", 1)[0]).exists(), target)


if __name__ == "__main__":
    unittest.main()
