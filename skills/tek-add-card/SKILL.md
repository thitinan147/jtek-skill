---
name: tek-add-card
description: Add one card at card-loop/backlog and a line on card-loop/board.md. Use when the user runs /tek-add-card or asks to add a card. The human writes the card body.
license: MIT
metadata:
  author: Thitinan
  version: "10"
  short-description: Add a card to the board
---

# tek-add-card

อ่านกติกาหัว `/tek-add-card` ใน skill `tek-skill` ไฟล์ `references/loop.md`

รหัสที่ต่อท้ายคำสั่งคือ `<id>` ไม่มีรหัสให้ถาม ถามหัวข้อ **ทำก่อน** **งานหลัก** หรือ **เก็บเล็ก** แล้ว copy `assets/card.template.md` ไปที่ `card-loop/backlog/<id>.md` และใส่บรรทัด `- [ ]` บน board

เสร็จเมื่อไฟล์ card กับบรรทัดอยู่ครบ และหัว **ทำ** **ไม่ทำ** **ตรวจผ่านเมื่อ** ยังให้คนเติม
