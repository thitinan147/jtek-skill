---
name: tek-read-board
description: Read card-loop/board.md and report the next card and lines marked รอรีวิว, ส่งกลับ, and ถาม. Use when the user runs /tek-read-board or asks what is on the board. Do not implement.
license: MIT
metadata:
  author: Thitinan
  version: "10"
  short-description: Read the card-loop board
---

# tek-read-board

อ่านกติกาหัว `/tek-read-board` ใน skill `tek-skill` ไฟล์ `references/loop.md`

อ่าน `card-loop/board.md` แล้วรายงานข้อถัดไปตามขั้นหยิบ ข้อที่เป็น `รอรีวิว:` `ส่งกลับ:` และ `ถาม:`

เสร็จเมื่อรายงานนั้นถูกส่ง และไม่มีไฟล์ถูกแก้
