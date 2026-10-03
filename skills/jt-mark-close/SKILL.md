---
name: jt-mark-close
description: Tick ปิด on a card with a reason and close the open review item when it can be closed. Use when the user runs /jt-mark-close. The human invokes this.
disable-model-invocation: true
license: MIT
metadata:
  author: Thitinan
  version: "14"
  short-description: Tick ปิด on a card
---

# jt-mark-close

รหัสข้อคือตัวเลขนำหน้า ถ้ามีให้ใช้ใบนั้น คำที่เหลือคือเหตุ ถ้าไม่มีตัวเลขและมีบรรทัดที่ยังไม่ปิดใบเดียว ให้ใช้ใบนั้นทั้งก้อนที่พิมพ์มาเป็นเหตุ ถ้ามีหลายใบให้ถามรหัสแล้วหยุดโดยไม่เปลี่ยนบรรทัด

ไม่มีเหตุให้ถามหนึ่งบรรทัด ห้ามติ๊กจนกว่าจะมีเหตุ

working tree สกปรกให้หยุดโดยไม่เปลี่ยนบรรทัด

checkout สาขาที่บรรทัด `สาขาคิว:` ชี้ เปลี่ยนบรรทัดเป็น `- [x]` ต่อท้าย `ปิด:` พร้อมเหตุนั้น ย้ายบรรทัดไปส่วน **ปิดแล้ว** แล้ว commit เฉพาะ `card-loop/board.md` บนสาขาคิว

มี merge request ของ `card-<id>` ที่ยังเปิดอยู่ ให้ปิดใบนั้นโดยไม่ merge

เสร็จเมื่อบรรทัดบนสาขาคิวเป็น `ปิด:` และมีเหตุ
