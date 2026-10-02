---
name: tek-mark-merge
description: Tick merge on the reviewed card and merge the open review item when this repo has that step. Use when the user runs /tek-mark-merge. The human invokes this.
disable-model-invocation: true
license: MIT
metadata:
  author: Thitinan
  version: "10"
  short-description: Tick merge on the reviewed card
---

# tek-mark-merge

อ่านกติกาหัวคนเปลี่ยนคำบนบรรทัดใน skill `tek-skill` ไฟล์ `references/loop.md`

เปลี่ยนบรรทัดที่คนรับเป็น `- [x]` ต่อท้าย `merge:` แล้ว merge ของที่เปิดไว้ถ้า repo นี้มีขั้นนั้น ย้ายบรรทัดไปส่วน **ปิดแล้ว** เมื่อคิวยาว แล้ว commit ที่ `card-loop/`

เสร็จเมื่อบรรทัดเป็น `merge:` และของที่เปิดไว้ถูก merge แล้วถ้า repo นี้มีขั้นนั้น
