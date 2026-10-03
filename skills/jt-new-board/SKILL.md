---
name: jt-new-board
description: Create card-loop/board.md, fill the command table from this repo, and write scanned skill names into the two rows. Use when the user runs /jt-new-board or asks to set up the card loop board. Do not ask the user to fill the table.
license: MIT
metadata:
  author: Thitinan
  version: "20"
  short-description: Create the board and fill it
---

# jt-new-board

1. repo ที่เปิดอยู่ไม่ใช่ git repo ให้หยุดแล้วบอกให้ `git init` ก่อน
2. HEAD ไม่อยู่บน branch ให้หยุดแล้วบอกให้ checkout branch ที่จะเก็บคิว
3. มี `card-loop/board.md` อยู่แล้วให้หยุดแล้วบอกว่ามีแล้ว
4. copy `assets/board.template.md` ของ skill `jt-card-gate` ไปที่ `card-loop/board.md`
5. ใส่ชื่อ branch ปัจจุบันหลังบรรทัด `สาขาคิว:` และเปลี่ยน `<REPO_NAME>` ในหัวไฟล์เป็นชื่อโฟลเดอร์ของ repo
6. เติมตารางจาก repo ที่เปิดอยู่ คนไม่กรอกตารางนี้

ใช้ตัวจัดการแพ็กเกจจากไฟล์ล็อกที่มีอยู่ คือ `pnpm-lock.yaml` เป็น `pnpm` ไม่มีไฟล์นั้นแต่มี `yarn.lock` เป็น `yarn` ไม่มีสองไฟล์นั้นแต่มี `bun.lock` หรือ `bun.lockb` เป็น `bun` นอกนั้นเป็น `npm`

| ช่อง | ใส่ค่าแรกที่พบ |
|---|---|
| `<SETUP_CMD>` | คำสั่งเตรียมสภาพแวดล้อมหรือติดตั้ง dependency: `pnpm install --frozen-lockfile` เมื่อมี `pnpm-lock.yaml`, `yarn install --frozen-lockfile` เมื่อมี `yarn.lock`, `bun install --frozen-lockfile` เมื่อมี `bun.lock` หรือ `bun.lockb`, `npm ci` เมื่อมี `package-lock.json`, `npm install` เมื่อมี `package.json`, `cargo build` เมื่อมี `Cargo.toml`, `go mod download` เมื่อมี `go.mod`, `uv sync --frozen` หรือ `poetry install` ตามเครื่องมือ python นอกนั้นเว้นช่องว่าง |
| `<TEST_CMD>` | `scripts.test` ใน `package.json` เป็น `<ตัวจัดการ> test` ไม่มีให้ใช้ `cargo test` เมื่อมี `Cargo.toml` ไม่มีให้ใช้ `go test ./...` เมื่อมี `go.mod` ไม่มีให้ใช้ `pytest` เมื่อ `pyproject.toml` มี pytest ไม่มีทั้งสี่อย่างให้ใส่ `ไม่มีชุดเทส` |
| `<TYPECHECK_CMD>` | `scripts.typecheck` เป็น `<ตัวจัดการ> run typecheck` ไม่มีแต่มี `tsconfig.json` ให้ใส่ `<ตัวจัดการ> exec tsc --noEmit` ไม่มีแต่มี `go.mod` ให้ใส่ `go vet ./...` นอกนั้นเว้นช่องว่าง |
| `<LINT_CMD>` | `scripts.lint` เป็น `<ตัวจัดการ> run lint` นอกนั้นเว้นช่องว่าง |
| `<BROWSER_TOOL>` | มี `playwright` ใน `package.json` ให้ใส่ `playwright` ไม่มีแต่มี `cypress` ให้ใส่ `cypress` นอกนั้นเว้นช่องว่าง |
| `<STACK_LOCK>` | หนึ่งบรรทัด `ภาษา · เฟรมเวิร์กหรือไม่มีเฟรมเวิร์ก · คำสั่งใน <TEST_CMD> · ของที่ห้ามใช้: ไม่ได้ประกาศในไฟล์โปรเจกต์` อ่านภาษาและเฟรมเวิร์กจาก `package.json` `go.mod` `pyproject.toml` `Cargo.toml` |

7. หาชื่อ skill ตามหัว **ค้น** ใน `skills/jt-find-skills/SKILL.md` เขียนชื่อที่หัวนั้นให้ลงช่อง ไม่เกินสามชื่อต่อกลุ่ม ลง `<TEK_SKILLS>` และ `<REPO_SKILLS>` คั่นด้วย `, ` ไม่มีชื่อในกลุ่มนั้นให้เว้นช่องนั้นว่าง
8. แสดงตารางสถานะจากหัว **ค้น** ในคำตอบ คำสั่งติดตั้งอยู่เฉพาะแถว `แนะนำให้ลง` ไม่รันคำสั่งนั้น
9. ถามครั้งเดียวว่า repo คู่ชื่ออะไร เขียนคำตอบลงบรรทัด `คู่:` ที่มีอยู่แล้วบน board ของ repo นี้ บรรทัดนั้นเป็นชื่อที่คนตอบ หรือคำว่า `ไม่มี` ใช้เฉพาะคำที่คนตอบ ห้ามใส่ชื่อ repo เอง ห้ามถามซ้ำตอนเปิด card ใบหลัง ห้ามสร้าง `card-loop/paired.md` เพราะบรรทัดนี้ และห้ามสร้าง board ใน repo อื่น

ห้ามเรียก `/jt-do-work`

เสร็จเมื่อ `สาขาคิว:` เป็นชื่อ branch จริง บรรทัด `คู่:` เป็นชื่อที่คนตอบหรือคำว่า `ไม่มี` ช่อง `<TEST_CMD>` กับ `<STACK_LOCK>` ไม่ว่าง และสองช่อง skill ได้ชื่อจากหัว **ค้น** แล้ว
