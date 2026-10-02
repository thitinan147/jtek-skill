---
name: tek-add-card
description: Add one card at card-loop/backlog and a line on card-loop/board.md. Use when the user runs /tek-add-card or asks to add a card. The human writes the card body.
license: MIT
metadata:
  author: Thitinan
  version: "14"
  short-description: Add a card to the board
---

# tek-add-card

คนเขียนหัว **ทำ** **ไม่ทำ** **ตรวจผ่านเมื่อ** เอเจนต์ไม่เขียนสามหัวนี้แทนคน

1. ไม่มี `card-loop/board.md` ให้หยุดแล้วบอกให้เรียก `/tek-setup-board` ก่อน รหัสที่ต่อท้ายคำสั่งคือ `<id>` ไม่มีรหัสให้ถาม แล้วหยุดโดยยังไม่สร้างไฟล์
2. ถามว่าบรรทัดไปอยู่ **ทำก่อน** **งานหลัก** หรือ **เก็บเล็ก** ยังไม่ตอบให้หยุดโดยยังไม่สร้างไฟล์
3. บรรทัด `สาขาคิว:` ว่างให้หยุด มีไฟล์ที่แก้ค้างนอก `card-loop/` ให้หยุด checkout สาขาคิว ไฟล์ `card-loop/board.md` ที่ยังไม่ commit ให้รวมใน commit ของคำสั่งนี้
4. copy `assets/card.template.md` ของ skill `tek-skill` ไปที่ `card-loop/backlog/<id>.md` แทน `<ID>` ในหัวไฟล์ด้วยรหัสนั้น
5. ใส่บรรทัด `- [ ] **<id>** ยังไม่ตั้งชื่อ (docs)` ในหัวข้อที่คนเลือก บรรทัด `ไม่มีข้อ` ใต้หัวข้อนั้นให้เอาออก
6. commit เฉพาะ `card-loop/board.md` กับ `card-loop/backlog/<id>.md` บนสาขาคิว

เสร็จเมื่อไฟล์ card กับบรรทัดอยู่ครบ และสามหัวนั้นยังว่างให้คนเติม ห้ามเรียก `/tek-do-card`
