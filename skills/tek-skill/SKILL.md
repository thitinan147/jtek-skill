---
name: tek-skill
description: Rulebook for the tek card loop in card-loop/. Read it when carrying out tek-setup-board, tek-brief, tek-add-card, tek-read-board, tek-scan-skills, tek-do-card, tek-open-review, tek-send-back, tek-mark-merge, or tek-mark-close. Do not pick or implement a card from this skill alone.
license: MIT
compatibility: Codex, Claude Code, Cursor, Grok Build, and Antigravity. Needs a git repo. The loop stays in the open repo.
metadata:
  author: Thitinan
  version: "18"
  short-description: Rulebook for the tek card loop
---

# tek-skill

กติกาทั้งก้อนอยู่ที่ [references/loop.md](references/loop.md) จุดที่เปิด skill อื่นอยู่ที่ [references/skills.md](references/skills.md) แม่แบบอยู่ที่ `assets/` ข้างไฟล์นี้

คนเรียกคำสั่งเหล่านี้ ไม่ได้เรียก `/tek-skill` เพื่อลงมือ

| คำสั่ง | งาน |
|---|---|
| `/tek-setup-board` | สร้าง board แล้วเติมตารางกับชื่อ skill |
| `/tek-brief` | ถามว่าอยากทำอะไร แล้วเขียน `card-loop/brief.md` |
| `/tek-add-card` | ถามจนคนรับร่าง ครั้งเดียวได้หลายใบ |
| `/tek-read-board` | อ่านคิว |
| `/tek-scan-skills` | รายงาน skill สองกลุ่ม แล้วหยุด |
| `/tek-do-card` | ทำทุก card ที่บรรทัดอนุญาต ข้ามใบที่ `รอรีวิว:` |
| `/tek-open-review` | เปิดของที่ `รอรีวิว:` |
| `/tek-send-back` | คนเปลี่ยนเป็น `ส่งกลับ:` |
| `/tek-mark-merge` | คนติ๊ก `merge:` |
| `/tek-mark-close` | คนติ๊ก `ปิด:` |

ถ้าคนเรียก skill นี้ตรง ๆ ให้บอกคำสั่งแล้วหยุด ห้ามหยิบ card
