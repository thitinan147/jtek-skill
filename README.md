# tek-skill

Skill สำหรับเดินลูป backlog ของ repo หนึ่งตัว คนเขียน card แล้วเปลี่ยนคำบนบรรทัด เอเจนต์ทำข้อที่บรรทัดอนุญาต

กติกาอยู่ที่ [`skills/tek-skill/references/loop.md`](skills/tek-skill/references/loop.md) ตามสเปก [Agent Skills](https://agentskills.io/specification) ใช้กับ Codex, Claude Code, Cursor, Grok Build และ Antigravity

## ติดตั้งทั้งเครื่อง

รันครั้งเดียวบนเครื่องนี้ แต่ละคนในทีมติดตั้งเอง `<path-to-repo-workflow>` คือโฟลเดอร์ที่มี `skills/tek-skill/SKILL.md`

```bash
npx skills add <path-to-repo-workflow> -g \
  -a codex -a claude-code -a cursor -a antigravity -a antigravity-cli -a grok \
  -y
```

เมื่อ repo นี้อยู่บน GitHub:

```bash
npx skills add thitinan147/tek-skill -g \
  -a codex -a claude-code -a cursor -a antigravity -a antigravity-cli -a grok \
  -y
```

คำสั่งนี้วางชุด skill ทั้งแปดคำสั่งพร้อมกติกา `tek-skill` ไว้ที่เครื่อง ไม่ได้ commit ไฟล์ skill เข้า repo ที่ใช้ลูป

## คำสั่ง

พิมพ์แค่ชื่อคำสั่ง ใน Codex ใช้ `$` แทน `/`

| คำสั่ง | ทำอะไร |
|---|---|
| `/tek-setup-board` | สร้าง `card-loop/board.md` แล้วหยุดให้เติมตาราง |
| `/tek-add-card` | สร้าง card แล้วใส่บรรทัดบน board |
| `/tek-read-board` | อ่านคิว ไม่ลงมือ |
| `/tek-do-card` | ทำ card ที่บรรทัดอนุญาต |
| `/tek-open-review` | เปิดของที่ `รอรีวิว:` เทียบหัวตรวจผ่านเมื่อ |
| `/tek-send-back` | เปลี่ยน `รอรีวิว:` เป็น `ส่งกลับ:` |
| `/tek-mark-merge` | ติ๊ก `merge:` คนเรียกเอง |
| `/tek-mark-close` | ติ๊ก `ปิด:` คนเรียกเอง |

มีรหัสข้อหรือเหตุอยู่แล้ว ต่อท้ายได้ที่ `/tek-add-card 123` กับ `/tek-mark-close ไม่ทำแล้ว`

## ใน repo ที่ใช้ลูป

commit แค่ `card-loop/`

- `card-loop/board.md` คือคำบนบรรทัด และตารางคำสั่งเทส
- `card-loop/backlog/<id>.md` คือ card
- `card-loop/plan/<id>.md` คือโน้ตของเอเจนต์

ลูปอยู่ที่ repo ที่เปิดอยู่ เอเจนต์ไม่ไปเปิด repo อื่น
