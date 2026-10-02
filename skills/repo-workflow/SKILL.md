---
name: repo-workflow
description: เดินลูป backlog ของ repo นี้ทีละข้อ ใช้เมื่อจะหยิบ card ลงมือ หรืออัปเดต work/backlog คนเขียน card และเปลี่ยนคำบนบรรทัดคิว เอเจนต์ไม่ดูปุ่ม review ของโฮสต์
---

# Repo workflow

ถ้า repo นี้ยังไม่มี `work/workflow.md` ให้ copy แม่แบบในโฟลเดอร์นี้ไปที่รากของ repo แล้วจึงอ่าน `work/workflow.md`

| จากโฟลเดอร์นี้ | ไปที่ repo |
|---|---|
| `workflow.template.md` | `work/workflow.md` |
| `skills.template.md` | `work/skills.md` |
| `backlog-readme.template.md` | `work/backlog/README.md` |
| `plans-readme.template.md` | `work/plans/README.md` |
| `card.template.md` | `work/backlog/<id>.md` ตอนเขียนตั๋ว |
| `plan.template.md` | `work/plans/<id>.md` ตอนหยิบงาน |

เติมตารางตั้งค่าใน `work/workflow.md` ก่อนหยิบข้อแรก บันทึกว่า copy จาก kit เวอร์ชัน 9

สถานะที่เชื่อมีแค่คำบนบรรทัดใน `work/backlog/README.md` คือ `ถาม:` `รอรีวิว:` `ส่งกลับ:` `merge:` และ `ปิด:`

คนเขียน card คนเปลี่ยน `รอรีวิว:` เป็น `ส่งกลับ:` หรือติ๊ก `merge:` / `ปิด:` เอเจนต์ตั้ง `รอรีวิว:` เมื่อหลักฐานผ่าน แล้วหยุด
