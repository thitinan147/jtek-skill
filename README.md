# tek-skill

ลูป backlog ของ repo ที่เปิดอยู่ คุณเขียน card แล้วเปลี่ยนคำบนบรรทัด เอเจนต์ทำเฉพาะข้อที่บรรทัดอนุญาต และไม่ไปทำ repo อื่น

ติดตั้งครั้งเดียวบนเครื่อง เลือกเจ้าที่คุณใช้

## ติดตั้ง

### Codex

```bash
npx skills add thitinan147/tek-skill -g -a codex -y
```

ในแชตพิมพ์ `$` แทน `/` เช่น `$tek-setup-board`

### Claude Code

```bash
npx skills add thitinan147/tek-skill -g -a claude-code -y
```

### Cursor

```bash
npx skills add thitinan147/tek-skill -g -a cursor -y
```

### Grok Build

```bash
npx skills add thitinan147/tek-skill -g -a grok -y
```

### Antigravity

```bash
npx skills add thitinan147/tek-skill -g -a antigravity -y
```

### Antigravity CLI

```bash
npx skills add thitinan147/tek-skill -g -a antigravity-cli -y
```

## ใช้ยังไง

เปิด repo ที่จะทำ แล้วพิมพ์ในแชต ข้อ 12 เป็นตัวอย่าง Codex ใช้ `$` แทน `/`

| ขั้น | พิมพ์ | เกิดอะไร |
|---|---|---|
| เริ่ม repo นี้ | `/tek-setup-board` | ได้ `card-loop/board.md` คุณเติมตารางคำสั่งเทส |
| เพิ่มข้อ | `/tek-add-card 12` | ได้ `card-loop/backlog/12.md` คุณเขียนทำ ไม่ทำ และตรวจผ่านเมื่อ |
| ให้ทำให้ | `/tek-do-card` | เอเจนต์ทำข้อที่บรรทัดอนุญาต แล้วตั้ง `รอรีวิว:` หรือเขียน `ถาม:` |
| ดูของที่เปิดไว้ | `/tek-open-review` | เทียบของชิ้นนั้นกับหัวตรวจผ่านเมื่อ |
| รับ | `/tek-mark-merge` | ติ๊ก `merge:` |
| ส่งกลับ | `/tek-send-back` แล้ว `/tek-do-card` | บรรทัดเป็น `ส่งกลับ:` แล้วเอเจนต์ทำข้อเดิมต่อ |
| ไม่เอา | `/tek-mark-close ไม่ทำแล้ว` | ติ๊ก `ปิด:` พร้อมเหตุ |
| ดูคิว | `/tek-read-board` | บอกว่าข้อไหนค้าง เรียกได้ทุกจังหวะ |

## ไฟล์ที่อยู่ใน repo คุณ

commit โฟลเดอร์ `card-loop/`

- `board.md` คิวและคำสั่งเทส คำบนบรรทัดคือสถานะ
- `backlog/12.md` ข้อตกลงที่คุณเขียน
- `plan/12.md` โน้ตที่เอเจนต์จดระหว่างทำ
