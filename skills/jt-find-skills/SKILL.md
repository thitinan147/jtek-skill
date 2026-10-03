---
name: jt-find-skills
description: Find REPO_SKILLS of the open repo and TEK_SKILLS at the moments the loop already uses those names. Propose the names for the person to choose. Use when the user runs /jt-find-skills. Do not install anything. Do not write the board until the person accepts.
license: MIT
metadata:
  author: Thitinan
  version: "20"
  short-description: Propose skill names, then write the accepted ones
---

# jt-find-skills

หา `<REPO_SKILLS>` ของ repo ที่เปิดอยู่ และ `<TEK_SKILLS>` ตามจังหวะที่ลูปใช้อยู่แล้วใน `references/skills.md` ของ skill `jt-card-gate` เสนอชื่อให้คนเลือก

ยังไม่ติดตั้ง และยังไม่เขียน `card-loop/board.md` จนกว่าคนจะรับชื่อที่เลือก

`/jt-new-board` เติมชื่อจากหัว **ค้น** ตอนสร้าง board คำสั่งนี้เมื่อถูกรันเองให้เสนอชื่อก่อน

## ค้น

สแตกอ่านจาก repo ที่เปิดอยู่ คือ `<STACK_LOCK>` บน `card-loop/board.md` ถ้ามี และ `package.json` `go.mod` `pyproject.toml` `Cargo.toml`

skill ที่ติดตั้งแล้วคือทุกไฟล์ `SKILL.md` ใต้ทุกโฟลเดอร์ใน home ที่ชื่อขึ้นต้นด้วย `.` รวมใต้ `~/.config` โฮมชื่อ `.npm` `.cache` `.local` `.Trash` ไม่ต้องเดิน ระหว่างเดินข้ามโฟลเดอร์ชื่อ `node_modules` `.git` `.tmp` `backups` `sessions` `projects` `tmp` `downloads` ตาม symlink ไปจนถึงไฟล์จริง path จริงเดียวกันนับเป็นใบเดียว และชื่อ `name` เดียวกันนับเป็นใบเดียว อ่าน `name` กับ `description` จากทุกใบที่เหลือ

ชื่อที่ขึ้นต้นด้วย `jt-` หรือ `jtek-` ไม่เข้าสองกลุ่ม

ใบที่ไม่มีจากกติกานี้ให้ค้นด้วย

`https://skills.sh/api/search?q=<คำ>&limit=5`

อ่าน `skills[].skillId` `skills[].source` และ `skills[].installs` เรียง `installs` จากมากไปน้อย ข้ามใบที่ `installs` เป็น 0 ข้ามใบที่ชื่อตรงกับใบที่พบแล้ว

กลุ่มลงมือคือ `<TEK_SKILLS>` ตามจังหวะที่ลูปใช้อยู่แล้ว ค้นสามคำ คือ `grill` `debug` `yagni` แล้วเก็บใบที่ `description` บนเครื่องหรือ `skillId` จากเว็บตรงจังหวะใน `references/skills.md` ห้ามเพิ่มจังหวะ

กลุ่มของ repo คือ `<REPO_SKILLS>` ของ repo ที่เปิดอยู่ อ่าน `name` จาก `SKILL.md` ใน repo นี้ก่อน แล้วจึงค้นด้วยชื่อภาษาหรือเฟรมเวิร์กที่พบใน repo นี้เมื่อช่องยังไม่ครบ ห้ามเปิด repo อื่น

แต่ละกลุ่มบน board ได้ไม่เกินสามชื่อ ชื่อที่พบจาก `SKILL.md` มาก่อน ชื่อจากเว็บเติมที่เหลือ ตารางด้านล่างแสดงครบทุกชื่อที่เข้าเกณฑ์ รวมใบจากเว็บแม้ช่องบน board จะเต็ม

แสดงตารางนี้ในคำตอบ หนึ่งแถวต่อหนึ่งชื่อที่เข้าเกณฑ์

| กลุ่ม | ชื่อ | สถานะ |
|---|---|---|
| ชื่อกลุ่ม | ชื่อ skill | `มีในเครื่อง` หรือ `แนะนำให้ลง` |

`มีในเครื่อง` เมื่อพบ `SKILL.md` จากกติกาด้านบน `แนะนำให้ลง` เมื่อชื่อมาจากเว็บและยังไม่พบไฟล์นั้น

แถว `แนะนำให้ลง` ให้คำสั่งนี้คนคัดลอก ไม่รันคำสั่ง คำสั่งไม่ใส่ `-a` จึงลงให้ทุกเจ้าที่ CLI เห็นบนเครื่อง

`npx skills add <source>@<skillId> -g -y`

## เสนอ

เสนอชื่อสองกลุ่มด้วยตารางสถานะในหัว **ค้น** ให้คนเลือก ห้ามรันคำสั่งติดตั้ง ห้ามเปิดใบใด ยังไม่เขียน board

คนรับชื่อแล้ว จึงเขียนเฉพาะชื่อที่รับลงช่อง `<TEK_SKILLS>` กับ `<REPO_SKILLS>` บนสาขาคิว ชื่อที่คนไม่รับไม่เขียน ไม่ลบบรรทัดอื่น แล้ว commit เฉพาะ `card-loop/board.md` ยังไม่รับให้หยุดโดยไม่แก้ board

ไม่มี `card-loop/board.md` ให้หยุดแล้วบอกให้เรียก `/jt-new-board` ก่อน

เสร็จเมื่อคนรับแล้วสองช่องตรงชื่อที่รับ หรือคนยังไม่รับและ board ยังไม่ถูกเขียนจากการสั่งนี้
