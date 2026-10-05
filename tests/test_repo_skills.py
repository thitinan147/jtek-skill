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
        self.assertIn("เวอร์ชัน 20", loop)
        self.assertNotIn("playwright", loop.lower())
        self.assertNotIn("เริ่ม:", loop)
        self.assertNotIn("พอร์ต:", loop)
        self.assertNotIn("คลิก:", loop)
        self.assertNotIn("browser-empty", loop)
        self.assertIn("เกตเป็นตัวปฏิเสธ", loop)
        self.assertIn("`docs` ไม่เปิด", skills)
        self.assertNotIn("one-off-checker", loop)
        self.assertNotIn("repeat-patch", loop)
        self.assertNotIn("reach-review", loop)


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
]

OLD_SCREEN = (
    "หนึ่งรอบคือพยายามทั้งชุดจนจบครั้งหนึ่ง หลักฐานคือเทสที่เกี่ยวข้องเขียว "
    "และถ้าเป็นงานที่ผู้ใช้เห็นจอ ทุกชนิด ไม่เฉพาะ `fix` "
    "ขั้นตอนเดิมบนพื้นผิวเดิมไม่เกิดบั๊ก "
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
        self.assertIn("npx skills add thitinan147/jtek-skill -g", readme)
        self.assertIn("name: jt-card-gate", rule)
        for text in (readme, loop, rule, find, merge, drop, move, work):
            for old in OLD_NAMES:
                self.assertNotIn(old, text)
        self.assertIn("`<REPO_SKILLS>` ของ repo ที่เปิดอยู่", find)
        self.assertIn("`<TEK_SKILLS>` ตามจังหวะที่ลูปใช้อยู่แล้ว", find)
        self.assertIn("ยังไม่เขียน `card-loop/board.md` จนกว่าคนจะรับ", find)
        self.assertIn("ห้ามรันคำสั่งติดตั้ง", find)
        self.assertNotIn("โฟลเดอร์ของเจ้าที่กำลังรันเท่านั้น", find)
        self.assertIn("ทุกโฟลเดอร์ใน home ที่ชื่อขึ้นต้นด้วย `.`", find)
        self.assertIn("ตาม symlink ไปจนถึงไฟล์จริง", find)
        self.assertIn("path จริงเดียวกันนับเป็นใบเดียว", find)
        self.assertIn("`มีในเครื่อง`", find)
        self.assertIn("`แนะนำให้ลง`", find)
        self.assertIn("skills.sh/api/search", find)
        self.assertNotIn("-a <เจ้าที่กำลังรัน>", find)
        board = (REPO / "skills" / "jt-new-board" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("ตารางสถานะจากหัว **ค้น**", board)
        self.assertIn("แนะนำให้ลง", board)
        self.assertIn("มีคำสั่ง `playwright` บน PATH", board)
        self.assertIn("ชื่อเบราว์เซอร์ของเซสชันหรือ MCP ไม่ใส่", board)
        self.assertNotIn(
            "มี `playwright` ใน `package.json` ให้ใส่ `playwright` ไม่มีแต่มี `cypress` ให้ใส่ `cypress` นอกนั้นเว้นช่องว่าง",
            board,
        )
        self.assertIn("ไม่รัน git merge", merge)
        self.assertIn("เปลี่ยนเฉพาะเครื่องหมายบนบรรทัด", merge)
        self.assertIn("เปลี่ยน `- [ ]` บนบรรทัดนั้นเป็น `- [x]`", drop)
        self.assertIn("ไม่เอา:", drop)
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


class PairedRepoRuleTests(unittest.TestCase):
    def test_pair_rules_live_in_the_skills_and_the_gate(self) -> None:
        new_board = (REPO / "skills" / "jt-new-board" / "SKILL.md").read_text(encoding="utf-8")
        new_card = (REPO / "skills" / "jt-new-card" / "SKILL.md").read_text(encoding="utf-8")
        work = (REPO / "skills" / "jt-do-work" / "SKILL.md").read_text(encoding="utf-8")
        loop = (REPO / "skills" / "jt-card-gate" / "references" / "loop.md").read_text(
            encoding="utf-8"
        )
        merge = (REPO / "skills" / "jt-merge" / "SKILL.md").read_text(encoding="utf-8")
        gate = (REPO / "skills" / "jt-next-step" / "gate.py").read_text(encoding="utf-8")
        template = (REPO / "skills" / "jt-card-gate" / "assets" / "board.template.md").read_text(
            encoding="utf-8"
        )
        readme = (REPO / "README.md").read_text(encoding="utf-8")
        self.assertIn("ถามครั้งเดียว", new_board)
        self.assertIn("`ไม่มี`", new_board)
        self.assertIn("ห้ามใส่ชื่อ repo เอง", new_board)
        self.assertIn("ห้ามถามซ้ำ", new_board)
        self.assertIn("card-loop/paired.md", new_board)
        self.assertIn("อย่าถามว่า repo คู่อยู่ที่ไหน", new_card)
        self.assertIn("เป็นใบเดียว", new_card)
        self.assertIn("ไม่ใส่ชื่อนั้น", new_card)
        self.assertIn("อย่าสร้างเพราะ board มีชื่อ", new_card)
        self.assertIn("ห้ามตั้งสถานะใน repo คู่", work)
        self.assertIn("ห้ามสร้าง `card-loop/board.md`", work)
        self.assertIn("ห้ามย้ายทั้งคิวออกจาก repo หลัก", work)
        self.assertIn("card-loop/paired.md", work)
        self.assertIn("ชี้กลับ", work)
        self.assertIn("อย่าสร้างไฟล์นี้แค่เพราะ board บันทึกชื่อไว้", work)
        self.assertIn("คนเป็นคน merge ทั้งสอง repo", work)
        self.assertIn(OLD_SCREEN, work)
        self.assertIn("pair-not-passed", gate)
        self.assertNotIn("jtekth", gate)
        self.assertNotIn("git merge", gate)
        self.assertIn("pair-not-passed", work)
        self.assertIn("ถามครั้งเดียว", loop)
        self.assertIn("ห้ามย้ายทั้งคิวออกจาก repo หลัก", loop)
        self.assertIn("อย่าสร้างเพราะ board บันทึกชื่อไว้", loop)
        self.assertIn("คนเป็นคน merge ทั้งสอง repo", loop)
        self.assertIn("ไม่รัน git merge", loop)
        self.assertIn("เอเจนต์ไม่เรียกสามคำสั่งนั้น", loop)
        self.assertIn("`/jt-send-back` `/jt-merge` `/jt-drop-card`", loop)
        self.assertIn("ไม่รัน git merge", merge)
        self.assertIn("คนเป็นคน merge ทั้งสอง repo", merge)
        self.assertEqual(template.count("\nคู่:"), 1)
        self.assertEqual(readme.count("\n## "), 4)
        self.assertIn("/jt-new-board", readme)
        self.assertFalse(list(REPO.glob("*playbook*")))
        self.assertFalse(list((REPO / "skills").glob("**/*playbook*")))


class RepeatRuleTests(unittest.TestCase):
    def test_the_three_rules_agree_across_the_skills_and_the_readme(self) -> None:
        readme = (REPO / "README.md").read_text(encoding="utf-8")
        loop = (REPO / "skills" / "jt-card-gate" / "references" / "loop.md").read_text(
            encoding="utf-8"
        )
        work = (REPO / "skills" / "jt-do-work" / "SKILL.md").read_text(encoding="utf-8")
        nxt = (REPO / "skills" / "jt-next-step" / "SKILL.md").read_text(encoding="utf-8")
        new_card = (REPO / "skills" / "jt-new-card" / "SKILL.md").read_text(encoding="utf-8")
        reading = (REPO / "skills" / "jt-read-board" / "SKILL.md").read_text(encoding="utf-8")
        skills = (REPO / "skills" / "jt-card-gate" / "references" / "skills.md").read_text(
            encoding="utf-8"
        )
        plan = (REPO / "skills" / "jt-card-gate" / "assets" / "plan.template.md").read_text(
            encoding="utf-8"
        )
        card = (REPO / "skills" / "jt-card-gate" / "assets" / "card.template.md").read_text(
            encoding="utf-8"
        )
        gate = (REPO / "skills" / "jt-next-step" / "gate.py").read_text(encoding="utf-8")
        for text in (readme, loop, work):
            self.assertIn("คำสั่งตรวจที่มีอยู่", text)
            self.assertIn("สคริปต์ตรวจใหม่", text)
            self.assertIn("อัปเดตกติกา", text)
            self.assertIn("ชั้น", text)
        self.assertIn("ห้ามแยกเอเจนต์", readme)
        self.assertIn("ห้ามแยกเป็นเอเจนต์คู่ขนานโดยไม่ลิงก์", loop)
        self.assertIn("refused: one-off-checker", work)
        self.assertIn("refused: repeat-patch", work)
        self.assertIn("refused: related", work)
        self.assertIn("reason` เป็น `related`", nxt)
        self.assertIn("refused: one-off-checker", nxt)
        self.assertIn("refused: repeat-patch", nxt)
        self.assertIn("step: ถาม", nxt)
        self.assertIn("ห้ามแยกเป็นเอเจนต์คู่ขนาน", new_card)
        self.assertIn("ห้ามรายงานเป็นงานคู่ขนาน", reading)
        self.assertIn("ไม่มาแทนคำสั่งตรวจบน board", skills)
        self.assertIn("แถวนี้ว่างได้", skills)
        self.assertIn("อัปเดตกติกา", plan)
        self.assertIn("ชั้น:", card)
        self.assertIn("one-off-checker", gate)
        self.assertIn("repeat-patch", gate)
        self.assertIn("อัปเดตกติกา", gate)
        self.assertFalse(list(REPO.glob("*playbook*")))
        self.assertFalse(list((REPO / "skills").glob("**/*playbook*")))
        self.assertEqual(readme.count("\n## "), 4)


class DraftPrSkillTests(unittest.TestCase):
    def test_the_loop_opens_a_draft_pr_before_review_and_merge_only_marks(self) -> None:
        readme = (REPO / "README.md").read_text(encoding="utf-8")
        loop = (REPO / "skills" / "jt-card-gate" / "references" / "loop.md").read_text(
            encoding="utf-8"
        )
        work = (REPO / "skills" / "jt-do-work" / "SKILL.md").read_text(encoding="utf-8")
        nxt = (REPO / "skills" / "jt-next-step" / "SKILL.md").read_text(encoding="utf-8")
        merge = (REPO / "skills" / "jt-merge" / "SKILL.md").read_text(encoding="utf-8")
        command = "gh pr create --draft --base <สาขาคิว> --head card-<id>"
        for text in (readme, loop, work, nxt):
            self.assertIn(command, text)
            self.assertIn("บรรทัดต้องไม่เป็น `รอรีวิว:`", text)
        for text in (work, nxt):
            self.assertIn("refused: pr-missing", text)
            self.assertIn("step: ถาม", text)
        self.assertIn("ห้ามเปิดซ้ำ", work)
        self.assertIn("ข้าม `gh pr create`", nxt)
        self.assertIn("ไม่เปิด PR", merge)
        self.assertIn("ไม่ merge PR", merge)
        self.assertIn("ไม่รัน git merge", merge)
        self.assertIn("git merge-base --is-ancestor", merge)
        self.assertIn("รวมกรณี merge ผ่าน PR", readme)
        self.assertIn("ไม่เปิด PR ไม่ merge PR และไม่รัน git merge", loop)
        self.assertNotIn("reach-review", loop)


if __name__ == "__main__":
    unittest.main()
