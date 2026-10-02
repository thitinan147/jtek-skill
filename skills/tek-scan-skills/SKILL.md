---
name: tek-scan-skills
description: Scan the open repo, installed skills, and skills.sh. Recommend general skills that sharpen tek-skill and repo skills for code review in the loop. Use when the user runs /tek-scan-skills. Do not install or invoke any skill.
license: MIT
metadata:
  author: Thitinan
  version: "12"
  short-description: Recommend two skill groups for this repo
---

# tek-scan-skills

รายงานสองกลุ่มตาม `references/skills.md` ของ skill `tek-skill` หัวรายงานต้องเขียนว่าเป็นคำแนะนำ ไม่ใช่รายการที่ต้องลง

สแตกอ่านจาก repo ที่เปิดอยู่ คือ `<STACK_LOCK>` บน `card-loop/board.md` ถ้ามี และ `package.json` `go.mod` `pyproject.toml` `Cargo.toml`

skill ที่ติดตั้งแล้วอ่าน `name` กับ `description` จากโฟลเดอร์ของเจ้าที่กำลังรันเท่านั้น

| เจ้าที่กำลังรัน | โฟลเดอร์ |
|---|---|
| Codex | `~/.codex/skills/` และ `~/.agents/skills/` |
| Claude Code | `~/.claude/skills/` |
| Cursor | `~/.cursor/skills/` และ `~/.agents/skills/` |
| Grok Build | `~/.grok/skills/` และ `~/.agents/skills/` |
| Antigravity | `~/.gemini/antigravity/skills/` และ `~/.gemini/config/skills/` |
| Antigravity CLI | `~/.gemini/antigravity-cli/skills/` |

ชื่อที่ขึ้นต้นด้วย `tek-` ไม่เข้าสองกลุ่ม

ใบที่ยังไม่มีบนเครื่อง ให้ค้นจาก [skills.sh](https://skills.sh/) แนะนำได้เมื่อเห็นจำนวนคนติดตั้ง และจำนวนนั้นสูง ไม่เห็นจำนวน ห้ามแนะนำใบนั้น ไม่เกินสามใบต่อกลุ่ม แต่ละใบใส่คำสั่งติดตั้งของเจ้าที่กำลังรันให้คนคัดลอก

บอกให้คนติดตั้งเอง แล้วเขียนชื่อกลุ่มลงมือลงแถว `<TEK_SKILLS>` และชื่อของ repo ลงแถว `<REPO_SKILLS>`

ห้ามรันคำสั่งติดตั้ง ห้ามแก้ไฟล์ ห้ามเปิดใบใด

เสร็จเมื่อคนเห็นสองกลุ่มพร้อมคำว่าคำแนะนำ และยังไม่มีอะไรถูกติดตั้ง
