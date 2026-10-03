---
name: jt-setup-board
description: Create card-loop/board.md, fill the command table from this repo, and write scanned skill names into the two rows. Use when the user runs /jt-setup-board or asks to set up the card loop board. Do not ask the user to fill the table.
license: MIT
metadata:
  author: Thitinan
  version: "16"
  short-description: Create the board and fill it
---

# jt-setup-board

1. repo ที่เปิดอยู่ไม่ใช่ git repo ให้หยุดแล้วบอกให้ `git init` ก่อน
2. HEAD ไม่อยู่บน branch ให้หยุดแล้วบอกให้ checkout branch ที่จะเก็บคิว
3. มี `card-loop/board.md` อยู่แล้วให้หยุดแล้วบอกว่ามีแล้ว
4. copy `assets/board.template.md` ของ skill `jtek-skill` ไปที่ `card-loop/board.md`
5. ใส่ชื่อ branch ปัจจุบันหลังบรรทัด `สาขาคิว:` และเปลี่ยน `<REPO_NAME>` ในหัวไฟล์เป็นชื่อโฟลเดอร์ของ repo
6. เติมตารางจาก repo ที่เปิดอยู่ คนไม่กรอกตารางนี้

ใช้ตัวจัดการแพ็กเกจจากไฟล์ล็อกที่มีอยู่ คือ `pnpm-lock.yaml` เป็น `pnpm` ไม่มีไฟล์นั้นแต่มี `yarn.lock` เป็น `yarn` ไม่มีสองไฟล์นั้นแต่มี `bun.lock` หรือ `bun.lockb` เป็น `bun` นอกนั้นเป็น `npm`

| ช่อง | ใส่ค่าแรกที่พบ |
|---|---|
| `<TEST_CMD>` | `scripts.test` ใน `package.json` เป็น `<ตัวจัดการ> test` ไม่มีให้ใช้ `cargo test` เมื่อมี `Cargo.toml` ไม่มีให้ใช้ `go test ./...` เมื่อมี `go.mod` ไม่มีให้ใช้ `pytest` เมื่อ `pyproject.toml` มี pytest ไม่มีทั้งสี่อย่างให้ใส่ `ไม่มีชุดเทส` |
| `<TYPECHECK_CMD>` | `scripts.typecheck` เป็น `<ตัวจัดการ> run typecheck` ไม่มีแต่มี `tsconfig.json` ให้ใส่ `<ตัวจัดการ> exec tsc --noEmit` ไม่มีแต่มี `go.mod` ให้ใส่ `go vet ./...` นอกนั้นเว้นช่องว่าง |
| `<LINT_CMD>` | `scripts.lint` เป็น `<ตัวจัดการ> run lint` นอกนั้นเว้นช่องว่าง |
| `<BROWSER_TOOL>` | มี `playwright` ใน `package.json` ให้ใส่ `playwright` ไม่มีแต่มี `cypress` ให้ใส่ `cypress` นอกนั้นเว้นช่องว่าง |
| `<STACK_LOCK>` | หนึ่งบรรทัด `ภาษา · เฟรมเวิร์กหรือไม่มีเฟรมเวิร์ก · คำสั่งใน <TEST_CMD> · ของที่ห้ามใช้: ไม่ได้ประกาศในไฟล์โปรเจกต์` อ่านภาษาและเฟรมเวิร์กจาก `package.json` `go.mod` `pyproject.toml` `Cargo.toml` |

7. หาชื่อ skill ตามหัว **ค้น** ใน `skills/jt-scan-skills/SKILL.md` เขียนชื่อกลุ่มลงมือลงช่อง `<TEK_SKILLS>` และชื่อของ repo ลงช่อง `<REPO_SKILLS>` คั่นด้วย `, ` ไม่มีชื่อในกลุ่มนั้นให้เว้นช่องนั้นว่าง
8. บอกคำสั่งติดตั้งของชื่อที่ยังไม่มีบนเครื่อง ไม่รันคำสั่งนั้น

ห้ามเรียก `/jt-do-card`

เสร็จเมื่อ `สาขาคิว:` เป็นชื่อ branch จริง ช่อง `<TEST_CMD>` กับ `<STACK_LOCK>` ไม่ว่าง และสองช่อง skill ได้ชื่อจากหัว **ค้น** แล้ว
