import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

TEK_SKILLS = """## `<TEK_SKILLS>` ทำให้การลงมือเก่งขึ้น

`/tek-do-card` เปิดได้หนึ่งชื่อจากแถวนี้ต่อจังหวะ เฉพาะเมื่อ `description` ของใบนั้นตรงจังหวะ

| จังหวะ | คำใน description ของใบในแถว |
|---|---|
| card ยังมีสองทางที่ผลไม่เท่ากัน ก่อนเขียน `ถาม:` | grill, interview |
| `fix` ที่สาเหตุยังไม่ชัด ก่อนเขียนเทสที่แดง | diagnose, debug |
| กำลังแก้โค้ดผลิต | YAGNI, stdlib, delete |

ไม่มีชื่อในแถวที่ตรงจังหวะ ให้เดินต่อโดยไม่เปิดใบ ใบกลุ่มนี้ไม่ถูกเปิดตอน review โค้ดของ repo
"""


class RepoSkillRuleTests(unittest.TestCase):
    def test_missing_repo_skill_must_review_the_diff_itself(self) -> None:
        skills = (REPO / "skills" / "tek-skill" / "references" / "skills.md").read_text(
            encoding="utf-8"
        )
        do_card = (REPO / "skills" / "tek-do-card" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn(TEK_SKILLS.strip(), skills)
        start = skills.index("## `<TEK_SKILLS>`")
        end = skills.index("## `<REPO_SKILLS>`")
        self.assertEqual(skills[start:end].strip(), TEK_SKILLS.strip())
        for text in (skills, do_card):
            self.assertNotIn("ชื่อที่ไม่มีในเครื่อง ให้จดใน plan แล้วเดินตาม loop.md ต่อ", text)
            self.assertNotIn("ชื่อที่ไม่มีในเครื่องให้จดใน plan แล้วเดินต่อ", text)
            self.assertIn("review diff ของข้อนี้เอง", text)
            self.assertIn("ห้ามข้าม", text)
            self.assertIn("review diff ไม่ได้", text)
            self.assertIn("การจดใน plan แล้วเดินต่อไม่นับเป็นรีวิวนั้น", text)
        self.assertIn("ห้ามถึง `รอรีวิว:`", skills)
        self.assertIn("ห้ามตั้ง `รอรีวิว:`", do_card)

    def test_tek_skills_row_on_the_board_template_is_unchanged(self) -> None:
        template = (REPO / "skills" / "tek-skill" / "assets" / "board.template.md").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "`<TEK_SKILLS>` คือชื่อ skill ที่ทำให้การลงมือเก่งขึ้น "
            "`/tek-do-card` เปิดชื่อในแถวนี้ตอน card ยังมีสองทาง "
            "ตอนหาสาเหตุบั๊กก่อนเขียนเทส และตอนแก้โค้ดผลิต เว้นว่างคือไม่เปิด",
            template,
        )

    def test_name_check_is_not_in_ci_and_the_test_limit_is_not_a_loop_paragraph(self) -> None:
        workflow = (REPO / ".github" / "workflows" / "test.yml").read_text(encoding="utf-8")
        loop = (REPO / "skills" / "tek-skill" / "references" / "loop.md").read_text(encoding="utf-8")
        skills = (REPO / "skills" / "tek-skill" / "references" / "skills.md").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("REPO_SKILLS", workflow)
        self.assertNotIn("TEK_SKILLS", workflow)
        self.assertNotIn("reach-review", loop)
        self.assertIn("/tek-gate", loop)
        self.assertIn("เวอร์ชัน 19", loop)
        self.assertNotIn("playwright", loop.lower())
        self.assertNotIn("เริ่ม:", loop)
        self.assertNotIn("พอร์ต:", loop)
        self.assertNotIn("คลิก:", loop)
        self.assertNotIn("browser-empty", loop)
        self.assertIn("เกตเป็นตัวปฏิเสธ", loop)
        self.assertIn("`docs` ไม่เปิด", skills)


if __name__ == "__main__":
    unittest.main()
