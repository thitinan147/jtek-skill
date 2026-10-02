---
name: tek-read-board
description: Read card-loop/board.md and report the next card and lines marked รอรีวิว, ส่งกลับ, and ถาม. Use when the user runs /tek-read-board or asks what is on the board. Do not implement.
license: MIT
metadata:
  author: Thitinan
  version: "12"
  short-description: Read the card-loop board
---

# tek-read-board

อ่าน `card-loop/board.md` แล้วรายงานตามลำดับหยิบในกติกา skill `tek-skill`

- ข้อ `- [ ]` ถัดไปที่ไม่มี `ถาม:` `รอรีวิว:` หรือ `ส่งกลับ:`
- ทุกข้อที่เป็น `รอรีวิว:` `ส่งกลับ:` หรือ `ถาม:`

ห้ามแก้ไฟล์ ห้ามลงมือ

เสร็จเมื่อรายงานนั้นถูกส่ง
