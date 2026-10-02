---
name: tek-send-back
description: Change the รอรีวิว line on card-loop/board.md to ส่งกลับ. Use when the user runs /tek-send-back after looking at the review. The human invokes this.
disable-model-invocation: true
license: MIT
metadata:
  author: Thitinan
  version: "10"
  short-description: Mark the reviewed card ส่งกลับ
---

# tek-send-back

อ่านกติกาหัวคนเปลี่ยนคำบนบรรทัดใน skill `tek-skill` ไฟล์ `references/loop.md`

เปลี่ยน `รอรีวิว:` เป็น `ส่งกลับ:` บนบรรทัดเดิม ข้อยังเป็น `- [ ]` ตั้ง `สถานะรอบ` ใน plan เป็น `ส่งกลับ` และ `รอบหลักฐาน` เป็น 1 เมื่อยังไม่ใช่ `ส่งกลับ` อยู่แล้ว แล้ว commit ที่ `card-loop/`

เสร็จเมื่อบรรทัดเป็น `ส่งกลับ:` และยังไม่ลงมือทำ card
