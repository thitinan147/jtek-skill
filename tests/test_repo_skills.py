import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

OLD_NAMES = [
    "/jt-gate",
    "/jt-setup-board",
    "/jt-brief",
    "/jt-add-card",
    "/jt-do-card",
    "/jt-open-review",
    "/jt-scan-skills",
    "/jt-mark-merge",
    "/jt-mark-close",
]


class RepoSkillRuleTests(unittest.TestCase):
    def test_work_queue_skill_and_contract_exist_with_v21_metadata(self) -> None:
        work = (REPO / "skills" / "jt-work-queue" / "SKILL.md").read_text(encoding="utf-8")
        contract = (
            REPO / "skills" / "jt-work-queue" / "references" / "contract.md"
        ).read_text(encoding="utf-8")
        self.assertIn("name: jt-work-queue", work)
        self.assertIn('version: "21"', work)
        self.assertIn("version 21", contract)
        self.assertIn("review this card's diff", work)
        self.assertIn("review this card's diff yourself", contract)
        self.assertIn("Do not skip that review", work)
        self.assertIn("do not set `review:`", work)
        self.assertNotIn("playwright", contract.lower())
        self.assertNotIn("start:", contract)
        self.assertNotIn("port:", contract)
        self.assertNotIn("click:", contract)
        self.assertNotIn("browser-empty", contract)
        self.assertNotIn("one-off-checker", contract)
        self.assertNotIn("repeat-patch", contract)
        for text in (work, contract):
            for old in OLD_NAMES:
                self.assertNotIn(old, text)


class PlanTemplateTests(unittest.TestCase):
    def test_plan_template_requires_done_when_and_escape(self) -> None:
        plan = (
            REPO / "skills" / "jt-work-queue" / "assets" / "plan.template.md"
        ).read_text(encoding="utf-8")
        card = (
            REPO / "skills" / "jt-work-queue" / "assets" / "card.template.md"
        ).read_text(encoding="utf-8")
        for heading in (
            "## Goal",
            "## Architecture",
            "## Files",
            "## Steps",
            "## Out of scope",
            "## Done when",
            "## Escape",
            "## review-diff",
            "## decisions",
        ):
            self.assertIn(heading, plan)
        self.assertIn("layer:", card)
        self.assertNotIn("update-rule", plan)


if __name__ == "__main__":
    unittest.main()
