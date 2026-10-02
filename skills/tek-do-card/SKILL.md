---
name: tek-do-card
description: Do the one card the line on card-loop/board.md allows. Continue a card marked ส่งกลับ, stop on รอรีวิว or an open ถาม, otherwise pick the next card and work until รอรีวิว or ถาม. Use when the user runs /tek-do-card or asks to do the next card.
license: MIT
metadata:
  author: Thitinan
  version: "11"
  short-description: Do the card the board line allows
---

# tek-do-card

อ่านกติกาหัว `/tek-do-card` ใน skill `tek-skill` ไฟล์ `references/loop.md` ตอน review โค้ดของ `feat` หรือ `fix` เปิดเฉพาะชื่อในแถว `<REPO_SKILLS>` ตาม `references/skills.md` ของ skill นั้น

ทำขั้นหยิบแล้วลงมือใน repo ที่เปิดอยู่ จนบรรทัดเป็น `รอรีวิว:` หรือมี `ถาม:` แล้วหยุด

เสร็จเมื่อลูปหยุดที่หนึ่งในสองคำนั้น หรือไม่มีข้อ `- [ ]` ที่หยิบได้
