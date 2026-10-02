---
name: tek-scan-skills
description: Scan the open repo, installed skills, and skills.sh. Recommend general skills that sharpen tek-skill and repo skills for code review in the loop. Use when the user runs /tek-scan-skills. Do not install or invoke any skill.
license: MIT
metadata:
  author: Thitinan
  version: "11"
  short-description: Report two skill groups for this repo
---

# tek-scan-skills

อ่านหัว `/tek-scan-skills` ใน skill `tek-skill` ไฟล์ `references/loop.md` และแยกกลุ่มตาม `references/skills.md` ของ skill นั้น

ทำตามแหล่งในหัวนั้น สแตกอ่านจาก repo ที่เปิดอยู่ skill ที่ติดตั้งแล้วอ่านจากโฟลเดอร์ของเจ้าที่กำลังรันเท่านั้น

เสร็จเมื่อสองกลุ่มถูกส่ง และไม่มีไฟล์ถูกแก้ ไม่มี skill ถูกติดตั้งหรือถูกเปิด
