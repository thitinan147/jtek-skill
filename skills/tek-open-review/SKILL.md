---
name: tek-open-review
description: Show the card marked รอรีวิว against its ตรวจผ่านเมื่อ, the decision table, the diff, test results, and surface evidence. Use when the user runs /tek-open-review. Do not change the board line.
license: MIT
metadata:
  author: Thitinan
  version: "12"
  short-description: Show the card waiting for review
---

# tek-open-review

เปิดของที่บรรทัดเป็น `รอรีวิว:` แล้ววางสี่อย่างนี้ให้คนเทียบ

1. หัว **ตรวจผ่านเมื่อ** ของ card
2. ตาราง **การตัดสินใจ** ใน `card-loop/plan/<id>.md` ถ้าว่างให้บอกว่าตารางว่าง
3. diff ว่าอยู่ในหัว **ทำ** และไม่ล้ำหัว **ไม่ทำ**
4. ผลเทส และหลักฐานบนพื้นผิวถ้า card ต้องการ

ห้ามเปลี่ยนบรรทัดบน board ห้ามติ๊ก `merge:` หรือ `ปิด:`

เสร็จเมื่อคนเห็นสี่อย่างนั้น และบรรทัดยังเป็น `รอรีวิว:`
