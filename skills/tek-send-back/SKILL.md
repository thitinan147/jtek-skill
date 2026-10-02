---
name: tek-send-back
description: Change the รอรีวิว line on card-loop/board.md to ส่งกลับ. Use when the user runs /tek-send-back after looking at the review. The human invokes this.
disable-model-invocation: true
license: MIT
metadata:
  author: Thitinan
  version: "14"
  short-description: Mark the reviewed card ส่งกลับ
---

# tek-send-back

รหัสที่ต่อท้ายคำสั่งคือใบที่จะส่งกลับ ถ้าไม่มีรหัสและมีบรรทัด `รอรีวิว:` ใบเดียว ให้ใช้ใบนั้น ถ้ามีหลายใบให้ถามรหัสแล้วหยุดโดยไม่เปลี่ยนบรรทัด

working tree สกปรกให้หยุดโดยไม่เปลี่ยนบรรทัด

checkout สาขาที่บรรทัด `สาขาคิว:` ชี้ เปลี่ยนบรรทัด `- [ ]` ของใบนั้นจาก `รอรีวิว:` เป็น `ส่งกลับ:` บนบรรทัดเดิม ข้อยังเป็น `- [ ]` แล้ว commit เฉพาะ `card-loop/board.md` บนสาขาคิว

จากนั้น checkout `card-<id>` เมื่อ branch นั้นมีอยู่ ถ้า `สถานะรอบ` ยังไม่ใช่ `ส่งกลับ` ให้ตั้งเป็น `ส่งกลับ` และตั้ง `รอบหลักฐาน` เป็น 1 ถ้าเป็น `ส่งกลับ` อยู่แล้ว ให้คงรอบเดิม แล้ว commit เฉพาะ `card-loop/plan/<id>.md` บน branch นั้น แล้ว checkout สาขาคิว ไม่มี branch `card-<id>` ให้หยุดหลัง commit บรรทัด แล้วบอกว่าหา branch ไม่เจอ

เสร็จเมื่อบรรทัดบนสาขาคิวเป็น `ส่งกลับ:` และยังไม่มีการแก้โค้ดของข้อ
