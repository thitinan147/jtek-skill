import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

TEK_SKILLS = """## `<TEK_SKILLS>` ทำให้การลงมือเก่งขึ้น

`/jt-do-work` เปิดได้หนึ่งชื่อจากแถวนี้ต่อจังหวะ เฉพาะเมื่อ `description` ของใบนั้นตรงจังหวะ

| จังหวะ | คำใน description ของใบในแถว |
|---|---|
| card ยังมีสองทางที่ผลไม่เท่ากัน ก่อนเขียน `ถาม:` | grill, interview |
| `fix` ที่สาเหตุยังไม่ชัด ก่อนเขียนเทสที่แดง | diagnose, debug |
| กำลังแก้โค้ดผลิต | YAGNI, stdlib, delete |

ไม่มีชื่อในแถวที่ตรงจังหวะ ให้เดินต่อโดยไม่เปิดใบ ใบกลุ่มนี้ไม่ถูกเปิดตอน review โค้ดของ repo
"""


class RepoSkillRuleTests(unittest.TestCase):
    def test_missing_repo_skill_must_review_the_diff_itself(self) -> None:
        skills = (REPO / "skills" / "jt-card-gate" / "references" / "skills.md").read_text(
            encoding="utf-8"
        )
        do_card = (REPO / "skills" / "jt-do-work" / "SKILL.md").read_text(encoding="utf-8")
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
        template = (REPO / "skills" / "jt-card-gate" / "assets" / "board.template.md").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "`<TEK_SKILLS>` คือชื่อ skill ที่ทำให้การลงมือเก่งขึ้น "
            "`/jt-do-work` เปิดชื่อในแถวนี้ตอน card ยังมีสองทาง "
            "ตอนหาสาเหตุบั๊กก่อนเขียนเทส และตอนแก้โค้ดผลิต เว้นว่างคือไม่เปิด",
            template,
        )

    def test_name_check_is_not_in_ci_and_the_test_limit_is_not_a_loop_paragraph(self) -> None:
        workflow = (REPO / ".github" / "workflows" / "test.yml").read_text(encoding="utf-8")
        loop = (REPO / "skills" / "jt-card-gate" / "references" / "loop.md").read_text(encoding="utf-8")
        skills = (REPO / "skills" / "jt-card-gate" / "references" / "skills.md").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("REPO_SKILLS", workflow)
        self.assertNotIn("TEK_SKILLS", workflow)
        self.assertNotIn("reach-review", loop)
        self.assertIn("/jt-next-step", loop)
        self.assertIn("เวอร์ชัน 19", loop)
        self.assertNotIn("playwright", loop.lower())
        self.assertNotIn("เริ่ม:", loop)
        self.assertNotIn("พอร์ต:", loop)
        self.assertNotIn("คลิก:", loop)
        self.assertNotIn("browser-empty", loop)
        self.assertIn("เกตเป็นตัวปฏิเสธ", loop)
        self.assertIn("`docs` ไม่เปิด", skills)


COMMANDS = [
    "/jt-new-board",
    "/jt-ask-brief",
    "/jt-new-card",
    "/jt-read-board",
    "/jt-find-skills",
    "/jt-do-work",
    "/jt-open-work",
    "/jt-send-back",
    "/jt-merge",
    "/jt-drop-card",
    "/jt-move-card",
    "/jt-next-step",
]

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
    "jtek-skill",
]

OLD_SCREEN = (
    "หนึ่งรอบคือพยายามทั้งชุดจนจบครั้งหนึ่ง หลักฐานคือเทสที่เกี่ยวข้องเขียว "
    "และถ้าเป็น `fix` ที่ผู้ใช้เห็นจอ ขั้นตอนเดิมบนพื้นผิวเดิมไม่เกิดบั๊ก "
    "งานที่ผู้ใช้เห็นจอแต่คลิกไม่ได้ไม่ใช่รอบนี้ ให้ทำตามหัว **เขียน ถาม**"
)


class RenamedCommandTests(unittest.TestCase):
    def test_only_the_new_command_names_and_the_four_behavior_changes(self) -> None:
        readme = (REPO / "README.md").read_text(encoding="utf-8")
        loop = (REPO / "skills" / "jt-card-gate" / "references" / "loop.md").read_text(
            encoding="utf-8"
        )
        rule = (REPO / "skills" / "jt-card-gate" / "SKILL.md").read_text(encoding="utf-8")
        find = (REPO / "skills" / "jt-find-skills" / "SKILL.md").read_text(encoding="utf-8")
        merge = (REPO / "skills" / "jt-merge" / "SKILL.md").read_text(encoding="utf-8")
        drop = (REPO / "skills" / "jt-drop-card" / "SKILL.md").read_text(encoding="utf-8")
        move = (REPO / "skills" / "jt-move-card" / "SKILL.md").read_text(encoding="utf-8")
        work = (REPO / "skills" / "jt-do-work" / "SKILL.md").read_text(encoding="utf-8")
        rows = re.findall(r"^\| `(/jt-[^`]+)`", readme, re.M)
        self.assertEqual(rows, COMMANDS)
        self.assertEqual(re.findall(r"^\| `(/jt-[^`]+)`", loop, re.M), COMMANDS)
        self.assertEqual(readme.count("\n## "), 4)
        self.assertIn("ชุด skill หลายสิบตัว", readme)
        self.assertIn("npx skills add thitinan147/tek-skill -g", readme)
        self.assertIn("name: jt-card-gate", rule)
        for text in (readme, loop, rule, find, merge, drop, move, work):
            for old in OLD_NAMES:
                self.assertNotIn(old, text)
        self.assertIn("`<REPO_SKILLS>` ของ repo ที่เปิดอยู่", find)
        self.assertIn("`<TEK_SKILLS>` ตามจังหวะที่ลูปใช้อยู่แล้ว", find)
        self.assertIn("ยังไม่เขียน `card-loop/board.md` จนกว่าคนจะรับ", find)
        self.assertIn("ห้ามรันคำสั่งติดตั้ง", find)
        self.assertIn("ไม่รัน git merge", merge)
        self.assertIn("เปลี่ยนเฉพาะเครื่องหมายบนบรรทัด", merge)
        self.assertIn("จาก `ปิด` เป็น `ไม่เอา`", drop)
        self.assertIn("ไม่ลบบรรทัดอื่น", drop)
        self.assertIn("ไม่เปลี่ยนสถานะบนบรรทัดนั้น", move)
        self.assertIn("ไม่แตะโค้ด", move)
        self.assertIn("ไม่ merge", move)
        self.assertIn("เอเจนต์ไม่เรียกสามคำสั่งนั้น", loop)
        self.assertIn("`/jt-send-back` `/jt-merge` `/jt-drop-card`", loop)
        self.assertIn("คนเป็นคน merge", loop)
        self.assertIn("ไม่รัน git merge", loop)
        self.assertIn(OLD_SCREEN, work)
        self.assertIn("disable-model-invocation: true", merge)
        self.assertIn("disable-model-invocation: true", drop)
        send = (REPO / "skills" / "jt-send-back" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("disable-model-invocation: true", send)
        dirs = sorted(path.name for path in (REPO / "skills").iterdir() if path.is_dir())
        self.assertEqual(dirs, sorted([name[1:] for name in COMMANDS] + ["jt-card-gate"]))


if __name__ == "__main__":
    unittest.main()
