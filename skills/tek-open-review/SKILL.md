---
name: tek-open-review
description: Show the card marked รอรีวิว against its ตรวจผ่านเมื่อ, the decision table, the diff, test results, and surface evidence. Use when the user runs /tek-open-review. Do not change the board line.
license: MIT
metadata:
  author: Thitinan
  version: "14"
  short-description: Show the card waiting for review
---

# tek-open-review

รหัสที่ต่อท้ายคำสั่งคือใบที่จะเปิด ถ้าไม่มีรหัสและมีบรรทัด `รอรีวิว:` ใบเดียว ให้เปิดใบนั้น ถ้ามีหลายใบให้ถามรหัสแล้วหยุดโดยไม่เปลี่ยนบรรทัด

อ่าน board จาก branch ที่บรรทัด `สาขาคิว:` ชี้ อ่าน card, plan, และ diff จาก branch `card-<id>` เทียบกับสาขาคิว อยู่บน branch อื่นได้โดยไม่ checkout

วางสี่อย่างนี้ให้คนเทียบ

1. หัว **ตรวจผ่านเมื่อ** ของ card
2. ตาราง **การตัดสินใจ** ใน plan ของ branch `card-<id>` ถ้าว่างให้บอกว่าตารางว่าง
3. diff จากสาขาคิวถึง `card-<id>` ว่าอยู่ในหัว **ทำ** และไม่ล้ำหัว **ไม่ทำ**
4. ผลเทส และหลักฐานบนพื้นผิวถ้า card ต้องการ

ห้ามเปลี่ยนบรรทัดบน board ห้ามติ๊ก `merge:` หรือ `ปิด:`

เสร็จเมื่อคนเห็นสี่อย่างนั้น และบรรทัดบนสาขาคิวยังเป็น `รอรีวิว:`
