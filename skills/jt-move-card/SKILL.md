---
name: jt-move-card
description: Move one line on card-loop/board.md. Use when the user runs /jt-move-card. Do not change that line's status, do not touch code, and do not merge.
license: MIT
metadata:
  author: Thitinan
  version: "20"
  short-description: Move a line on the board
---

# jt-move-card

รหัสที่ต่อท้ายคำสั่งคือบรรทัดที่จะย้าย คำที่เหลือคือหัวข้อปลายทาง คือ **ทำก่อน** **งานหลัก** **เก็บเล็ก** หรือ **ปิดแล้ว** ถ้าไม่มีรหัสหรือไม่มีหัวข้อให้ถามแล้วหยุดโดยไม่ย้าย

ย้ายได้เฉพาะบรรทัดบน `card-loop/board.md`

ไม่เปลี่ยนสถานะบนบรรทัดนั้น ไม่แตะโค้ด ไม่ merge

working tree สกปรกนอก `card-loop/` ให้หยุดโดยไม่ย้าย

checkout สาขาที่บรรทัด `สาขาคิว:` ชี้ ย้ายบรรทัดนั้นไปหัวข้อที่บอก โดยคงข้อความสถานะบนบรรทัดเดิม แล้ว commit เฉพาะ `card-loop/board.md` บนสาขาคิว

เสร็จเมื่อบรรทัดอยู่หัวข้อใหม่ และสถานะบนบรรทัดเท่าเดิม
