---
name: jt-brief
description: Interview until the user's desired work is clear, then write card-loop/brief.md. Use when the user runs /jt-brief or asks what they want to do before adding cards. Wait for them to accept the draft. Do not create cards or change the board.
license: MIT
metadata:
  author: Thitinan
  version: "17"
  short-description: Ask what to do, then write the brief
---

# jt-brief

ถามว่าอยากทำอะไร ถามจนงานที่อยากได้ชัด คนรับร่างแล้วจึงเขียน `card-loop/brief.md`

ยังไม่สร้าง card ยังไม่แก้บรรทัดบน board ห้ามเรียก `/jt-add-card` หรือ `/jt-do-card`

## ก่อนถาม

1. ไม่มี `card-loop/board.md` ให้หยุดแล้วบอกให้เรียก `/jt-setup-board` ก่อน
2. ข้อเท็จจริงใน repo ที่เปิดอยู่ให้เปิดไฟล์ดูเอง อย่าถามสิ่งที่ดูแล้วรู้
3. มี `card-loop/brief.md` อยู่แล้วให้อ่านไฟล์นั้น แล้วถามว่าจะเขียน brief ใหม่หรือหยุด ยังไม่เขียนทับจนกว่าคนจะรับร่างใหม่

## ถาม

ถามทีละรอบ หนึ่งรอบคือทุกคำถามที่ตอบได้ตอนนี้โดยไม่เดาคำตอบที่ยังไม่ได้ยิน แต่ละข้อมีคำตอบที่แนะนำหนึ่งข้อ แล้วหยุดรอคำตอบคน

รอบแรกถามว่าอยากทำอะไร

ถามรอบถัดไปเมื่อยังมีอย่างใดอย่างหนึ่ง

- ยังบอกไม่ได้ว่าเสร็จแล้วจะได้อะไร
- มีสองทางที่ผลไม่เท่ากันโดยยังไม่เลือก
- ขอบเขตคลุมเครือจนแยกเป็น card ไม่ได้

หยุดถามเมื่อบอกได้ว่าอยากได้อะไร อะไรไม่ทำในรอบนี้ และงานไหนแยกเป็นคนละ card ได้

## ร่าง

แสดง brief ทั้งไฟล์แล้วถามว่านี่คือสิ่งที่อยากทำหรือไม่

```markdown
# Brief

อยากทำอะไร:
-

ไม่ทำในรอบนี้:
-

งานที่แยกได้:
-
```

คนแก้ให้แสดงร่างใหม่ ยังไม่สร้างไฟล์ คนบอกว่ารับร่างนี้จึงไปหัว **สร้าง**

## สร้าง

1. บรรทัด `สาขาคิว:` ว่างให้หยุด มีไฟล์ที่แก้ค้างนอก `card-loop/` ให้หยุด
2. checkout สาขาคิว
3. เขียน `card-loop/brief.md` ตามร่างที่รับ
4. commit เฉพาะไฟล์นั้นบนสาขาคิว ด้วย `docs: add the brief`

เสร็จเมื่อไฟล์ตรงร่างที่คนรับ และยังไม่มี card ใบใหม่
