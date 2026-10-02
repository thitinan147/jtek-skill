---
name: tek-add-card
description: Add one card at card-loop/backlog and a line on card-loop/board.md. Use when the user runs /tek-add-card or asks to add a card. The human writes the card body.
license: MIT
metadata:
  author: Thitinan
  version: "12"
  short-description: Add a card to the board
---

# tek-add-card

คนเขียนหัว **ทำ** **ไม่ทำ** **ตรวจผ่านเมื่อ** เอเจนต์ไม่เขียนสามหัวนี้แทนคน

1. รหัสที่ต่อท้ายคำสั่งคือ `<id>` ไม่มีรหัสให้ถาม
2. ถามว่าบรรทัดไปอยู่ **ทำก่อน** **งานหลัก** หรือ **เก็บเล็ก**
3. copy `assets/card.template.md` ของ skill `tek-skill` ไปที่ `card-loop/backlog/<id>.md`
4. ใส่บรรทัด `- [ ]` บน `card-loop/board.md` ในหัวข้อที่คนเลือก

เสร็จเมื่อไฟล์ card กับบรรทัดอยู่ครบ และสามหัวนั้นยังว่างให้คนเติม ห้ามเรียก `/tek-do-card`
