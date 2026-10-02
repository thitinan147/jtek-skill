---
name: tek-send-back
description: Change the รอรีวิว line on card-loop/board.md to ส่งกลับ. Use when the user runs /tek-send-back after looking at the review. The human invokes this.
disable-model-invocation: true
license: MIT
metadata:
  author: Thitinan
  version: "12"
  short-description: Mark the reviewed card ส่งกลับ
---

# tek-send-back

เปลี่ยนบรรทัด `- [ ]` ที่เป็น `รอรีวิว:` ให้เป็น `ส่งกลับ:` บนบรรทัดเดิม ข้อยังเป็น `- [ ]`

ใน plan ของข้อนั้น ถ้า `สถานะรอบ` ยังไม่ใช่ `ส่งกลับ` ให้ตั้งเป็น `ส่งกลับ` และตั้ง `รอบหลักฐาน` เป็น 1 ถ้าเป็น `ส่งกลับ` อยู่แล้ว ห้ามรีเซ็ตรอบ

commit ที่ `card-loop/` แล้วหยุด ห้ามลงมือทำ card

เสร็จเมื่อบรรทัดเป็น `ส่งกลับ:` และยังไม่มีการแก้โค้ดของข้อ
