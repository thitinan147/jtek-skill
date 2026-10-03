---
name: jt-merge
description: Change the merge mark on the board line. Use when the user runs /jt-merge. Do not run git merge. The human invokes this.
disable-model-invocation: true
license: MIT
metadata:
  author: Thitinan
  version: "20"
  short-description: Change the merge mark on the board line
---

# jt-merge

รหัสที่ต่อท้ายคำสั่งคือใบที่จะรับ ถ้าไม่มีรหัสและมีบรรทัด `รอรีวิว:` ใบเดียว ให้ใช้ใบนั้น ถ้ามีหลายใบให้ถามรหัสแล้วหยุดโดยไม่เปลี่ยนบรรทัด

คนเรียกคำสั่งนี้หลังดู `/jt-open-work` ของใบนั้นแล้วเท่านั้น

working tree สกปรกให้หยุดโดยไม่เปลี่ยนบรรทัด

บรรทัดของใบนั้นต้องมีสถานะ `รอรีวิว:` ถ้าไม่ใช่สถานะ `รอรีวิว:` ให้หยุดโดยไม่เปลี่ยนบรรทัด

อ่าน plan จาก branch `card-<id>` ตาราง **การตัดสินใจ** ว่าง หรือ diff จากสาขาคิวถึง `card-<id>` ไม่ตรงหัว **ตรวจผ่านเมื่อ** ให้หยุดแล้วบอกว่าหลักฐานไม่ครบ ห้ามเปลี่ยนเครื่องหมาย

ตรวจว่าคนได้ merge `card-<id>` เข้าสาขาคิวแล้วจริง โดยตรวจว่า commit ของ branch รวมอยู่ในสาขาคิวแล้ว (เช่น `git merge-base --is-ancestor card-<id> <สาขาคิว>`) หากยังไม่ได้ merge ให้บอกให้คน merge ก่อน ไม่รัน git merge เอง

เมื่อหลักฐานครบและคน merge โค้ดแล้ว ให้อยู่บนสาขาคิว เปลี่ยนเฉพาะเครื่องหมายบนบรรทัดนั้นเป็น `- [x]` ต่อท้าย `merge:` แล้ว commit เฉพาะ `card-loop/board.md` บนสาขาคิว

คำสั่งนี้เปลี่ยนเฉพาะเครื่องหมายบนบรรทัด ไม่รัน git merge ไม่ย้ายบรรทัด และไม่แตะโค้ด คนเป็นคน merge ใบที่หัวมีชื่อ repo คู่ คนเป็นคน merge ทั้งสอง repo คำสั่งนี้ยังเปลี่ยนเฉพาะเครื่องหมายบนบรรทัดของ board หลัก

เสร็จเมื่อบรรทัดบนสาขาคิวเป็น `merge:` และไม่ได้รัน git merge
