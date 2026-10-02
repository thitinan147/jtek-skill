---
name: tek-read-board
description: Read card-loop/board.md and report the next card and lines marked รอรีวิว, ส่งกลับ, and ถาม. Use when the user runs /tek-read-board or asks what is on the board. Do not implement.
license: MIT
metadata:
  author: Thitinan
  version: "14"
  short-description: Read the card-loop board
---

# tek-read-board

ไม่มี `card-loop/board.md` ให้บอกให้เรียก `/tek-setup-board` ก่อน แล้วจบ มีไฟล์แล้วให้อ่านจาก branch ที่บรรทัด `สาขาคิว:` ชี้ แล้วรายงานตามลำดับหยิบในกติกา skill `tek-skill`

- ข้อที่จะถูกทำต่อ คือ `ส่งกลับ:` ก่อน แล้วจึงข้อที่ยังไม่มี `ถาม:` และ `รอรีวิว:`
- ทุกข้อที่ค้างเป็น `รอรีวิว:` `ส่งกลับ:` หรือ `ถาม:` โดยคิวไม่หยุดเพราะมี `รอรีวิว:`
- บรรทัด `สาขาคิว:` ว่าง ให้บอกว่าบอร์ดยังไม่พร้อม

ห้ามแก้ไฟล์ ห้ามลงมือ ห้าม checkout

เสร็จเมื่อรายงานนั้นถูกส่ง
