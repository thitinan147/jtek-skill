---
name: jt-card-gate
description: Rulebook for the jt-card-gate loop in card-loop/. Read it when carrying out jt-new-board, jt-ask-brief, jt-new-card, jt-read-board, jt-find-skills, jt-do-work, jt-next-step, jt-open-work, jt-send-back, jt-merge, jt-drop-card, or jt-move-card. Do not pick or implement a card from this skill alone.
license: MIT
compatibility: Codex, Claude Code, Cursor, Grok Build, and Antigravity. Needs a git repo. The loop stays in the open repo.
metadata:
  author: Thitinan
  version: "20"
  short-description: Rulebook for the jt-card-gate loop
---

# jt-card-gate

กติกาทั้งก้อนอยู่ที่ [references/loop.md](references/loop.md) จุดที่เปิด skill อื่นอยู่ที่ [references/skills.md](references/skills.md) แม่แบบอยู่ที่ `assets/` ข้างไฟล์นี้

คนเรียกคำสั่งเหล่านี้ ไม่ได้เรียก `/jt-card-gate` เพื่อลงมือ

| คำสั่ง | งาน |
|---|---|
| `/jt-new-board` | สร้าง board แล้วเติมตารางกับชื่อ skill และถาม repo คู่ครั้งเดียว |
| `/jt-ask-brief` | ถามว่าอยากทำอะไร แล้วเขียน `card-loop/brief.md` |
| `/jt-new-card` | ถามจนคนรับร่าง ครั้งเดียวได้หลายใบ |
| `/jt-read-board` | อ่านคิว |
| `/jt-find-skills` | เสนอชื่อให้คนเลือก ยังไม่เขียน board จนกว่าจะรับ |
| `/jt-do-work` | ทำทุก card ที่บรรทัดอนุญาต ข้ามใบที่ `รอรีวิว:` |
| `/jt-open-work` | เปิดของที่ `รอรีวิว:` |
| `/jt-send-back` | คนเปลี่ยนเป็น `ส่งกลับ:` |
| `/jt-merge` | คนเปลี่ยนเครื่องหมาย `merge:` ไม่รัน git merge |
| `/jt-drop-card` | คนเปลี่ยนคำเป็น `ไม่เอา` ไม่ลบบรรทัดอื่น |
| `/jt-move-card` | ย้ายบรรทัดบน board ไม่เปลี่ยนสถานะ |
| `/jt-next-step` | อ่านบรรทัดแล้วทำขั้นถัดไปที่กติกาอนุญาต ไม่ merge |

งานที่ผู้ใช้เห็นจอ ก่อน `รอรีวิว:` ใช้คำสั่งตรวจจอของ JTek ที่ `scripts/jt-screen-check` หรือคำสั่งตรวจที่มีอยู่บน board ห้ามสร้างสคริปต์ตรวจใหม่ รายละเอียดอยู่ใน [references/loop.md](references/loop.md)

ถ้าคนเรียก skill นี้ตรง ๆ ให้บอกคำสั่งแล้วหยุด ห้ามหยิบ card
