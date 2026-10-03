---
name: jt-gate
description: Read the current line on card-loop/board.md and do the next step the loop already allows. Use when the user runs /jt-gate or asks for the next board step without naming a command. This command cannot merge.
license: MIT
metadata:
  author: Thitinan
  version: "19"
  short-description: Do the next step the board line allows
---

# jt-gate

อ่านบรรทัดบน `card-loop/board.md` แล้วทำขั้นถัดไปที่กติกาใน `references/loop.md` ของ skill `jtek-skill` อนุญาตอยู่แล้ว

รันจากรากของ repo ที่เปิดอยู่ ด้วย `gate.py` ที่อยู่ข้างไฟล์นี้

```bash
python3 gate.py next
```

ทำเฉพาะ `command` ที่สคริปต์พิมพ์ หนึ่งคำสั่ง แล้วหยุด `reason` เป็น `need-id` ให้ถามรหัสแล้วหยุด `reason` เป็น `wait` ให้แสดงคำถามแล้วหยุด `action` เป็น `stop` ให้บอก `reason` แล้วหยุด `command` เป็น `/jt-open-review` ให้ใช้ข้อความใต้ `merge:` ที่สคริปต์พิมพ์ ห้ามเปลี่ยนบรรทัด

สคริปต์ไม่มีทาง merge แม้คนจะพิมพ์คำว่า merge ในรอบนี้ คำนั้นอยู่ที่ `/jt-mark-merge` หลังคนเทียบหัว **ตรวจผ่านเมื่อ** กับ diff แล้วเท่านั้น เกตนี้เรียกคำสั่งนั้นไม่ได้

`/jt-do-card` ตั้ง `รอรีวิว:` โดยรันสคริปต์นี้บนสาขาคิว

```bash
python3 gate.py reach-review --id <id> --write
```

ไม่มี remote ให้ใส่ `--link local` สคริปต์รัน `<TEST_CMD>` บน branch `card-<id>` คำสั่งเทสจบไม่เป็นศูนย์ สคริปต์ไม่เขียน `รอรีวิว:`

commit บน branch นั้นที่ชนิดแตะโค้ด แต่ diff ของโค้ด review ไม่ได้ สคริปต์พิมพ์ `refused: review-diff` และไม่เขียน `รอรีวิว:` การจดใน plan ไม่นับ ชื่อจาก `<TEK_SKILLS>` ไม่มาทำรีวิวนี้แทน

card ที่ผู้ใช้เห็นจอ แต่ `<BROWSER_TOOL>` ว่าง สตาร์ทไม่ขึ้น หรือคลิกไม่ตรงหัว **ตรวจผ่านเมื่อ** สคริปต์พิมพ์ `refused:` กับ `step: ถาม` และไม่เขียน `รอรีวิว:` วิธีสตาร์ท พอร์ต และขั้นตอนคลิกอยู่ที่ repo นั้น ให้เขียน `ถาม:`

เสร็จเมื่อทำคำสั่งที่สคริปต์พิมพ์แล้ว หรือสคริปต์บอกให้หยุด และบรรทัดไม่ถูกติ๊ก `merge:`
