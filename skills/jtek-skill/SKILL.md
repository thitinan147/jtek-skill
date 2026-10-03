---
name: jtek-skill
description: Rulebook for the jtek card loop in card-loop/. Read it when carrying out jt-setup-board, jt-brief, jt-add-card, jt-read-board, jt-scan-skills, jt-do-card, jt-gate, jt-open-review, jt-send-back, jt-mark-merge, or jt-mark-close. Do not pick or implement a card from this skill alone.
license: MIT
compatibility: Codex, Claude Code, Cursor, Grok Build, and Antigravity. Needs a git repo. The loop stays in the open repo.
metadata:
  author: Thitinan
  version: "19"
  short-description: Rulebook for the jtek card loop
---

# jtek-skill

กติกาทั้งก้อนอยู่ที่ [references/loop.md](references/loop.md) จุดที่เปิด skill อื่นอยู่ที่ [references/skills.md](references/skills.md) แม่แบบอยู่ที่ `assets/` ข้างไฟล์นี้

คนเรียกคำสั่งเหล่านี้ ไม่ได้เรียก `/jtek-skill` เพื่อลงมือ

| คำสั่ง | งาน |
|---|---|
| `/jt-setup-board` | สร้าง board แล้วเติมตารางกับชื่อ skill |
| `/jt-brief` | ถามว่าอยากทำอะไร แล้วเขียน `card-loop/brief.md` |
| `/jt-add-card` | ถามจนคนรับร่าง ครั้งเดียวได้หลายใบ |
| `/jt-read-board` | อ่านคิว |
| `/jt-scan-skills` | รายงาน skill สองกลุ่ม แล้วหยุด |
| `/jt-do-card` | ทำทุก card ที่บรรทัดอนุญาต ข้ามใบที่ `รอรีวิว:` |
| `/jt-open-review` | เปิดของที่ `รอรีวิว:` |
| `/jt-send-back` | คนเปลี่ยนเป็น `ส่งกลับ:` |
| `/jt-mark-merge` | คนติ๊ก `merge:` |
| `/jt-mark-close` | คนติ๊ก `ปิด:` |
| `/jt-gate` | อ่านบรรทัดแล้วทำขั้นถัดไปที่กติกาอนุญาต ไม่ merge |

ถ้าคนเรียก skill นี้ตรง ๆ ให้บอกคำสั่งแล้วหยุด ห้ามหยิบ card
