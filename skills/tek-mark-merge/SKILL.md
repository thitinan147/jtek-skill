---
name: tek-mark-merge
description: Tick merge on the reviewed card and merge the open review item when this repo has that step. Use when the user runs /tek-mark-merge. The human invokes this.
disable-model-invocation: true
license: MIT
metadata:
  author: Thitinan
  version: "14"
  short-description: Tick merge on the reviewed card
---

# tek-mark-merge

รหัสที่ต่อท้ายคำสั่งคือใบที่จะรับ ถ้าไม่มีรหัสและมีบรรทัด `รอรีวิว:` ใบเดียว ให้ใช้ใบนั้น ถ้ามีหลายใบให้ถามรหัสแล้วหยุดโดยไม่เปลี่ยนบรรทัด

คนเรียกคำสั่งนี้หลังดู `/tek-open-review` ของใบนั้นแล้วเท่านั้น

working tree สกปรกให้หยุดโดยไม่เปลี่ยนบรรทัด

อ่าน plan จาก branch `card-<id>` ตาราง **การตัดสินใจ** ว่าง หรือ diff จากสาขาคิวถึง `card-<id>` ไม่ตรงหัว **ตรวจผ่านเมื่อ** ให้หยุดแล้วบอกว่าหลักฐานไม่ครบ ห้ามติ๊กและห้าม merge

เมื่อหลักฐานครบ ให้อยู่บนสาขาคิว แล้ว merge `card-<id>` เข้าสาขาคิว merge ชนให้ยกเลิก merge ที่เพิ่งเริ่ม แล้วหยุดโดยไม่ติ๊ก

merge แล้ว เปลี่ยนบรรทัดเป็น `- [x]` ต่อท้าย `merge:` ย้ายบรรทัดไปส่วน **ปิดแล้ว** แล้ว commit ที่ `card-loop/` บนสาขาคิว

สาขาคิวมี remote ให้ push สาขาคิวด้วย push ธรรมดา push ไม่ผ่านให้บอกผล แล้วคงบรรทัด `merge:` ที่ commit แล้วไว้

เสร็จเมื่อบรรทัดบนสาขาคิวเป็น `merge:` และ `card-<id>` อยู่ในประวัติของสาขาคิว
