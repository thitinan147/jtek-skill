---
name: jt-next-step
description: Read the current line on card-loop/board.md and do the next step the loop already allows. Use when the user runs /jt-next-step or asks for the next board step without naming a command. This command cannot merge.
license: MIT
metadata:
  author: Thitinan
  version: "20"
  short-description: Do the next step the board line allows
---

# jt-next-step

อ่านบรรทัดบน `card-loop/board.md` แล้วทำขั้นถัดไปที่กติกาใน `references/loop.md` ของ skill `jt-card-gate` อนุญาตอยู่แล้ว

รันจากรากของ repo ที่เปิดอยู่ ด้วย `gate.py` ของ skill นี้

```bash
python3 <โฟลเดอร์ของ skill นี้>/gate.py next --root .
```

ทำเฉพาะ `command` ที่สคริปต์พิมพ์ หนึ่งคำสั่ง แล้วหยุด `reason` เป็น `need-id` ให้ถามรหัสแล้วหยุด `reason` เป็น `wait` ให้แสดงคำถามแล้วหยุด `action` เป็น `stop` ให้บอก `reason` แล้วหยุด `reason` เป็น `related` ให้บอก `ids` แล้วหยุด ใบนั้น `ชั้น:` เดียวกันแต่หัว **อ้างอิง** ยังไม่ลิงก์ ห้ามแยกเอเจนต์คู่ขนาน `command` เป็น `/jt-open-work` ให้ใช้ข้อความใต้ `merge:` ที่สคริปต์พิมพ์ ห้ามเปลี่ยนบรรทัด

สคริปต์ไม่มีทาง merge แม้คนจะพิมพ์คำว่า merge ในรอบนี้ เครื่องหมายอยู่ที่ `/jt-merge` หลังคนเทียบหัว **ตรวจผ่านเมื่อ** กับ diff แล้วเท่านั้น คำสั่งนั้นเปลี่ยนเฉพาะเครื่องหมายบนบรรทัด ไม่รัน git merge ไม่เปิด PR และไม่ merge PR เกตนี้เรียกคำสั่งนั้นไม่ได้ คนเป็นคน merge บน GitHub หลัง commit ของ card อยู่ในสาขาคิวแล้ว รวมกรณี merge ผ่าน PR

`/jt-do-work` ตั้ง `รอรีวิว:` โดยรันสคริปต์นี้บนสาขาคิว

```bash
python3 <โฟลเดอร์ของ skill นี้>/gate.py reach-review --root . --id <id>
```

รอบแรกยังไม่ใส่ `--write` สคริปต์รัน `<SETUP_CMD>` และ `<TEST_CMD>` บน worktree สะอาดของ branch `card-<id>` หาก `<SETUP_CMD>` ล้มเหลว สคริปต์พิมพ์ `refused: setup-failed` คำสั่งเทสจบไม่เป็นศูนย์ สคริปต์ไม่เขียน `รอรีวิว:`

`git remote` ว่าง และรอบแรกพิมพ์ `allowed` ให้รันอีกครั้งพร้อม `--write --link local` บรรทัดเป็น `รอรีวิว: local`

`git remote` มีชื่อ และรอบแรกพิมพ์ `allowed` ให้ push เฉพาะ `card-<id>` แล้วเปิด draft PR เข้าสาขาคิว ก่อน `--write` `gh` ต้องใช้ได้ และยังไม่มี PR เปิดสำหรับ head เดิม

```bash
git push -u origin card-<id>
gh pr list --head card-<id> --base <สาขาคิว> --state open --json number,isDraft,url,baseRefName
gh pr create --draft --base <สาขาคิว> --head card-<id> --title "<id>" --body "card <id>"
```

`gh pr list` มี draft ที่ `baseRefName` เป็นสาขาคิวอยู่แล้ว ให้ข้าม `gh pr create` push ไม่ได้, `gh` ไม่อยู่ใน PATH, สร้างไม่ได้, ไม่มีใบเปิด, ใบเปิดไม่เป็น draft, หรือ base ไม่ใช่สาขาคิว ให้เขียน `ถาม:` ห้ามใส่ `--write` บรรทัดต้องไม่เป็น `รอรีวิว:` เกตเป็นตัวปฏิเสธ

จากนั้นรันพร้อม `--write` สคริปต์ตรวจ draft PR เอง ถ้าพิมพ์ `refused: pr-missing` หรือ `refused: gh-missing` หรือ `refused: pr-not-draft` หรือ `refused: pr-base` หรือ `refused: pr-duplicate` หรือ `refused: pr-failed` พร้อม `step: ถาม` ให้เขียน `ถาม:` ห้ามตั้ง `รอรีวิว:`

commit บน branch นั้นที่ชนิดแตะโค้ด สคริปต์ตรวจด้วย `scripts/jt-diff-check` ถ้าไม่มีหัวข้อ `## รีวิว diff` จะพิมพ์ `refused: review-diff (detail: no-review)` ถ้าหัวข้อนั้นไม่มี SHA จะพิมพ์ `refused: review-diff (detail: no-sha)` ถ้า SHA ไม่ตรง commit ล่าสุดหรือ worktree ของ `card-<id>` ยังมีโค้ดค้าง จะพิมพ์ `refused: review-diff (detail: stale-review)` และไม่เขียน `รอรีวิว:` การจดใน plan โดยไม่มี SHA ที่ตรงไม่นับ ชื่อจาก `<TEK_SKILLS>` ไม่มาทำรีวิวนี้แทน

```bash
python3 <โฟลเดอร์ jtek-skill>/scripts/jt-diff-check --root . --id <id>
```

สคริปต์พิมพ์ `refused: one-off-checker` เมื่อ diff เพิ่มสคริปต์ที่ชื่อไฟล์ขึ้นต้น `check` `lint` หรือ `verify` และหัว **ทำ** ไม่ได้สั่งให้สร้างไฟล์นั้น และไม่เขียน `รอรีวิว:` ให้ใช้คำสั่งตรวจที่มีอยู่บน board

งานที่ผู้ใช้เห็นจอ ก่อน `รอรีวิว:` ให้ใช้คำสั่งตรวจจอของ JTek หรือคำสั่งตรวจที่มีอยู่บน board ห้ามสร้างสคริปต์ตรวจใหม่

```bash
python3 <โฟลเดอร์ jtek-skill>/scripts/jt-screen-check --root . --id <id>
```

คำสั่งนี้สตาร์ทแอปเมื่อ card กำหนดไว้ แล้วรัน playwright หรือ cypress จาก PATH หรือจากแพ็กเกจ จบไม่เป็นศูนย์เมื่อไม่ผ่าน เกตยังพิมพ์ `refused: one-off-checker` เมื่อมีการสร้างสคริปต์ตรวจที่หัว **ทำ** ไม่ได้สั่ง

สคริปต์พิมพ์ `refused: repeat-patch` เมื่อใบที่ยังเปิดมี `ชั้น:` เดียวกัน แต่ตาราง **การตัดสินใจ** ไม่มีแถว `อัปเดตกติกา` ที่ชี้ path ของกติกา skill เกต หรือสคริปต์ lint/ตรวจใน diff ของใบนี้หรือใบที่ลิงก์ หรือมีแถวแต่ไม่ได้แก้ไฟล์นั้น และไม่เขียน `รอรีวิว:`

สคริปต์พิมพ์ `refused: related` กับ `step: ถาม` เมื่อ `ชั้น:` เดียวกันแต่หัว **อ้างอิง** ยังไม่ชี้อีกฝั่ง และไม่เขียน `รอรีวิว:`

card ที่ผู้ใช้เห็นจอ แต่ `<BROWSER_TOOL>` ว่าง สตาร์ทไม่ขึ้น หรือคลิกแล้ว exit code ไม่เป็นศูนย์ สคริปต์พิมพ์ `refused:` กับ `step: ถาม` และไม่เขียน `รอรีวิว:` วิธีสตาร์ท พอร์ต (คั่นด้วยจุลภาคหากมีหลายพอร์ต) เวลาหน่วง `รอ:` และขั้นตอนคลิกอยู่ที่ repo นั้น ให้เขียน `ถาม:`

หัวใบที่มีชื่อ repo คู่ สคริปต์พิมพ์ `refused: pair-not-passed` และไม่เขียน `รอรีวิว:` จนกว่าทั้งสองฝั่งจะผ่าน แล้วเขียน `รอรีวิว:` ครั้งเดียวบน board ของ repo หลัก บรรทัด `คู่:` เป็น `ไม่มี` สคริปต์ไม่รอฝั่งที่สอง

เสร็จเมื่อทำคำสั่งที่สคริปต์พิมพ์แล้ว หรือสคริปต์บอกให้หยุด และบรรทัดไม่ถูกติ๊ก `merge:`
