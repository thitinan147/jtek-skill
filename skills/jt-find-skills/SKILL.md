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

กลุ่มลงมือคือ `<TEK_SKILLS>` ตามจังหวะที่ลูปใช้อยู่แล้ว ค้นสามคำ คือ `grill` `debug` `yagni` แล้วเก็บใบที่ `description` บนเครื่องหรือ `skillId` จากเว็บตรงจังหวะใน `references/skills.md` ห้ามเพิ่มจังหวะ

กลุ่มของ repo คือ `<REPO_SKILLS>` ของ repo ที่เปิดอยู่ อ่าน `name` จาก `SKILL.md` ใน repo นี้ก่อน แล้วจึงค้นด้วยชื่อภาษาหรือเฟรมเวิร์กที่พบใน repo นี้เมื่อช่องยังไม่ครบ ห้ามเปิด repo อื่น

แต่ละกลุ่มได้ไม่เกินสามชื่อ ชื่อที่ติดตั้งแล้วมาก่อน ชื่อจากเว็บเติมที่เหลือ ชื่อจากเว็บใส่คำสั่งนี้ให้คนคัดลอก ไม่รันคำสั่ง

`npx skills add <source>@<skillId> -g -a <เจ้าที่กำลังรัน> -y`

`<เจ้าที่กำลังรัน>` เป็น `codex` `claude-code` `cursor` `grok` `antigravity` หรือ `antigravity-cli`

## เสนอ

เสนอชื่อสองกลุ่มให้คนเลือก ห้ามรันคำสั่งติดตั้ง ห้ามเปิดใบใด ยังไม่เขียน board

คนรับชื่อแล้ว จึงเขียนเฉพาะชื่อที่รับลงช่อง `<TEK_SKILLS>` กับ `<REPO_SKILLS>` บนสาขาคิว ชื่อที่คนไม่รับไม่เขียน ไม่ลบบรรทัดอื่น แล้ว commit เฉพาะ `card-loop/board.md` ยังไม่รับให้หยุดโดยไม่แก้ board

ไม่มี `card-loop/board.md` ให้หยุดแล้วบอกให้เรียก `/jt-new-board` ก่อน

เสร็จเมื่อคนรับแล้วสองช่องตรงชื่อที่รับ หรือคนยังไม่รับและ board ยังไม่ถูกเขียนจากการสั่งนี้
