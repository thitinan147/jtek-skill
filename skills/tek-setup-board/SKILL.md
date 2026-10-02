---
name: tek-setup-board
description: Create card-loop/board.md for this repo and stop so the human can fill the test command table. Use when the user runs /tek-setup-board or asks to set up the card loop board.
license: MIT
metadata:
  author: Thitinan
  version: "14"
  short-description: Create the card-loop board
---

# tek-setup-board

1. repo ที่เปิดอยู่ไม่ใช่ git repo ให้หยุดแล้วบอกให้ `git init` ก่อน
2. HEAD ไม่อยู่บน branch ให้หยุดแล้วบอกให้ checkout branch ที่จะเก็บคิว
3. มี `card-loop/board.md` อยู่แล้วให้หยุดแล้วบอกว่ามีแล้ว
4. copy `assets/board.template.md` ของ skill `tek-skill` ไปที่ `card-loop/board.md`
5. ใส่ชื่อ branch ปัจจุบันหลังบรรทัด `สาขาคิว:`

ตารางคำสั่งยังว่างให้คนเติม ห้ามเรียก `/tek-do-card`

เสร็จเมื่อไฟล์นั้นมีบรรทัด `สาขาคิว:` เป็นชื่อ branch จริง และตารางคำสั่งยังว่าง
