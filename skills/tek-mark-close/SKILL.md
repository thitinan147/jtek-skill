---
name: tek-mark-close
description: Tick ปิด on a card with a reason and close the open review item when it can be closed. Use when the user runs /tek-mark-close. The human invokes this.
disable-model-invocation: true
license: MIT
metadata:
  author: Thitinan
  version: "12"
  short-description: Tick ปิด on a card
---

# tek-mark-close

เหตุที่ต่อท้ายคำสั่งคือเหตุที่ปิด ไม่มีเหตุให้ถามหนึ่งบรรทัด ห้ามติ๊กจนกว่าจะมีเหตุ

เปลี่ยนบรรทัดเป็น `- [x]` ต่อท้าย `ปิด:` พร้อมเหตุนั้น ปิดของที่เปิดไว้ถ้าปิดได้ ย้ายบรรทัดไปส่วน **ปิดแล้ว** เมื่อคิวยาว แล้ว commit ที่ `card-loop/`

เสร็จเมื่อบรรทัดเป็น `ปิด:` และมีเหตุ
