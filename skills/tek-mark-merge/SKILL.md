---
name: tek-mark-merge
description: Tick merge on the reviewed card and merge the open review item when this repo has that step. Use when the user runs /tek-mark-merge. The human invokes this.
disable-model-invocation: true
license: MIT
metadata:
  author: Thitinan
  version: "12"
  short-description: Tick merge on the reviewed card
---

# tek-mark-merge

คนเรียกคำสั่งนี้หลังดู `/tek-open-review` แล้วเท่านั้น

ตาราง **การตัดสินใจ** ว่าง หรือ diff ไม่ตรงหัว **ตรวจผ่านเมื่อ** ให้หยุดแล้วบอกว่าหลักฐานไม่ครบ ห้ามติ๊ก

เมื่อหลักฐานครบ เปลี่ยนบรรทัดเป็น `- [x]` ต่อท้าย `merge:` merge ของที่เปิดไว้ถ้า repo นี้มีขั้นนั้น ย้ายบรรทัดไปส่วน **ปิดแล้ว** เมื่อคิวยาว แล้ว commit ที่ `card-loop/`

เสร็จเมื่อบรรทัดเป็น `merge:` และของที่เปิดไว้ถูก merge แล้วถ้า repo นี้มีขั้นนั้น
