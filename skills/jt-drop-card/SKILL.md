---
name: jt-drop-card
description: Change the word on the board line from ปิด to ไม่เอา. Use when the user runs /jt-drop-card. Do not delete extra lines. The human invokes this.
disable-model-invocation: true
license: MIT
metadata:
  author: Thitinan
  version: "14"
  short-description: Change ปิด to ไม่เอา on the board line
---

# jt-drop-card

รหัสข้อคือตัวเลขนำหน้า ถ้ามีให้ใช้ใบนั้น คำที่เหลือคือเหตุ ถ้าไม่มีตัวเลขและมีบรรทัดที่ยังไม่ปิดใบเดียว ให้ใช้ใบนั้นทั้งก้อนที่พิมพ์มาเป็นเหตุ ถ้ามีหลายใบให้ถามรหัสแล้วหยุดโดยไม่เปลี่ยนบรรทัด

ไม่มีเหตุให้ถามหนึ่งบรรทัด ห้ามเปลี่ยนคำจนกว่าจะมีเหตุ

working tree สกปรกให้หยุดโดยไม่เปลี่ยนบรรทัด

checkout สาขาที่บรรทัด `สาขาคิว:` ชี้ เปลี่ยนคำบนบรรทัดนั้นจาก `ปิด` เป็น `ไม่เอา` ข้อเป็น `- [x]` ต่อท้าย `ไม่เอา:` พร้อมเหตุนั้น ไม่ลบบรรทัดอื่น ไม่ย้ายบรรทัด แล้ว commit เฉพาะ `card-loop/board.md` บนสาขาคิว

มี merge request ของ `card-<id>` ที่ยังเปิดอยู่ ให้ปิดใบนั้นโดยไม่ merge

เสร็จเมื่อบรรทัดบนสาขาคิวเป็น `ไม่เอา:` และมีเหตุ และบรรทัดอื่นยังอยู่
