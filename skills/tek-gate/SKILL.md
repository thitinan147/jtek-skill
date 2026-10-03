---
name: tek-gate
description: Read the current line on card-loop/board.md and do the next step the loop already allows. Use when the user runs /tek-gate or asks for the next board step without naming a command. This command cannot merge.
license: MIT
metadata:
  author: Thitinan
  version: "19"
  short-description: Do the next step the board line allows
---

# tek-gate

อ่านบรรทัดบน `card-loop/board.md` แล้วทำขั้นถัดไปที่กติกาใน `references/loop.md` ของ skill `tek-skill` อนุญาตอยู่แล้ว

รันจากรากของ repo ที่เปิดอยู่ ด้วย `gate.py` ที่อยู่ข้างไฟล์นี้

```bash
python3 gate.py next
```

ทำเฉพาะ `command` ที่สคริปต์พิมพ์ หนึ่งคำสั่ง แล้วหยุด `reason` เป็น `need-id` ให้ถามรหัสแล้วหยุด `reason` เป็น `wait` ให้แสดงคำถามแล้วหยุด `action` เป็น `stop` ให้บอก `reason` แล้วหยุด `command` เป็น `/tek-open-review` ให้ใช้ข้อความใต้ `merge:` ที่สคริปต์พิมพ์ ห้ามเปลี่ยนบรรทัด

สคริปต์ไม่มีทาง merge แม้คนจะพิมพ์คำว่า merge ในรอบนี้ คำนั้นอยู่ที่ `/tek-mark-merge` หลังคนเทียบหัว **ตรวจผ่านเมื่อ** กับ diff แล้วเท่านั้น เกตนี้เรียกคำสั่งนั้นไม่ได้

`/tek-do-card` ตั้ง `รอรีวิว:` โดยรันสคริปต์นี้บนสาขาคิว

```bash
python3 gate.py reach-review --id <id> --write
```

ไม่มี remote ให้ใส่ `--link local` สคริปต์รัน `<TEST_CMD>` บน branch `card-<id>` คำสั่งเทสจบไม่เป็นศูนย์ สคริปต์ไม่เขียน `รอรีวิว:`

เสร็จเมื่อทำคำสั่งที่สคริปต์พิมพ์แล้ว หรือสคริปต์บอกให้หยุด และบรรทัดไม่ถูกติ๊ก `merge:`
