---
name: jt-read-board
description: Read card-loop/board.md and report the next card and lines marked รอรีวิว, ส่งกลับ, and ถาม. Use when the user runs /jt-read-board or asks what is on the board. Do not implement.
license: MIT
metadata:
  author: Thitinan
  version: "20"
  short-description: Read the card-loop board
---

# jt-read-board

ไม่มี `card-loop/board.md` ให้บอกให้เรียก `/jt-new-board` ก่อน แล้วจบ มีไฟล์แล้วให้อ่านจาก branch ที่บรรทัด `สาขาคิว:` ชี้ แล้วรายงานตามลำดับหยิบในกติกา skill `jt-card-gate`

- ข้อที่จะถูกทำต่อ คือ `ส่งกลับ:` ก่อน แล้วจึง `ถาม:` ที่หัวข้อ **ถาม** ใน card ว่าง แล้วจึงข้อที่ยังไม่มี `ถาม:` `รอรีวิว:` หรือ `ส่งกลับ:` โดยตรวจตามหัวข้อ **ทำก่อน** แล้ว **งานหลัก** สำหรับหัวข้อ **เก็บเล็ก** จะหยิบได้ต่อเมื่อทุกใบใต้ **ทำก่อน** และ **งานหลัก** ไม่มี `- [ ]` ที่ยังไม่เสร็จ
- ทุกข้อที่ค้างเป็น `รอรีวิว:` `ส่งกลับ:` หรือ `ถาม:` โดยคิวไม่หยุดเพราะมี `รอรีวิว:`
- บรรทัด `สาขาคิว:` ว่าง ให้บอกว่าบอร์ดยังไม่พร้อม

ห้ามแก้ไฟล์ ห้ามลงมือ ห้าม checkout

เสร็จเมื่อรายงานนั้นถูกส่ง
