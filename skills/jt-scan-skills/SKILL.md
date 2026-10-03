---
name: jt-scan-skills
description: Scan the open repo, installed skills, and skills.sh. Recommend general skills that sharpen jtek-skill and repo skills for code review in the loop. Use when the user runs /jt-scan-skills. Do not install or invoke any skill.
license: MIT
metadata:
  author: Thitinan
  version: "16"
  short-description: Recommend two skill groups for this repo
---

# jt-scan-skills

รายงานสองกลุ่มตาม `references/skills.md` ของ skill `jtek-skill` หัวรายงานต้องเขียนว่าเป็นคำแนะนำ ไม่ใช่รายการที่ต้องลง

`/jt-setup-board` เขียนชื่อจากหัว **ค้น** ลง board ให้แล้ว คำสั่งนี้รายงานอย่างเดียว

## ค้น

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

ชื่อที่ขึ้นต้นด้วย `jt-` หรือ `jtek-` ไม่เข้าสองกลุ่ม

ใบที่ยังไม่มีบนเครื่อง ให้ค้นด้วย

`https://skills.sh/api/search?q=<คำ>&limit=5`

อ่าน `skills[].skillId` `skills[].source` และ `skills[].installs` เรียง `installs` จากมากไปน้อย ข้ามใบที่ `installs` เป็น 0

กลุ่มลงมือค้นสามคำ คือ `grill` `debug` `yagni` แล้วเก็บใบที่ `description` บนเครื่องหรือ `skillId` จากเว็บตรงจังหวะใน `references/skills.md`

กลุ่มของ repo ค้นด้วยชื่อภาษาหรือเฟรมเวิร์กที่พบใน repo

แต่ละกลุ่มได้ไม่เกินสามชื่อ ชื่อที่ติดตั้งแล้วมาก่อน ชื่อจากเว็บเติมที่เหลือ ชื่อจากเว็บใส่คำสั่งนี้ให้คนคัดลอก ไม่รันคำสั่ง

`npx skills add <source>@<skillId> -g -a <เจ้าที่กำลังรัน> -y`

`<เจ้าที่กำลังรัน>` เป็น `codex` `claude-code` `cursor` `grok` `antigravity` หรือ `antigravity-cli`

ห้ามรันคำสั่งติดตั้ง ห้ามเปิดใบใด คำสั่งนี้ห้ามแก้ไฟล์

เสร็จเมื่อคนเห็นสองกลุ่มพร้อมคำว่าคำแนะนำ จำนวน `installs` ของใบจากเว็บ และยังไม่มีอะไรถูกติดตั้ง
