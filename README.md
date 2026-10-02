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

เปิด repo ที่จะทำ แล้วพิมพ์ในแชตตามลำดับนี้ ข้อ 12 เป็นตัวอย่าง

```text
/tek-setup-board
/tek-add-card 12
/tek-do-card
/tek-open-review
/tek-send-back
/tek-do-card
/tek-open-review
/tek-mark-merge
```

`/tek-setup-board` สร้าง `card-loop/board.md` เติมตารางคำสั่งเทสในไฟล์นั้นก่อนไปต่อ

`/tek-add-card 12` สร้าง card ที่ `card-loop/backlog/12.md` คุณเขียนว่าทำอะไร ไม่ทำอะไร และตรวจผ่านเมื่อไร แล้วใส่บรรทัดบน board

`/tek-do-card` ให้เอเจนต์ทำข้อที่บรรทัดอนุญาต พอหลักฐานผ่านจะตั้งบรรทัดเป็น `รอรีวิว:` แล้วหยุด

`/tek-open-review` เปิดของชิ้นนั้นมาเทียบกับหัวตรวจผ่านเมื่อ

จากนั้นคุณเลือกอย่างใดอย่างหนึ่ง

- `/tek-mark-merge` รับข้อนี้
- `/tek-send-back` ส่งกลับไปทำให้ใหม่ แล้วเรียก `/tek-do-card` อีกครั้ง
- `/tek-mark-close ไม่ทำแล้ว` ปิดข้อนี้พร้อมเหตุ

ดูว่าคิวค้างอะไร เรียก `/tek-read-board` ได้ทุกจังหวะ

## ไฟล์ที่อยู่ใน repo คุณ

commit โฟลเดอร์ `card-loop/`

- `board.md` คิวและคำสั่งเทส คำบนบรรทัดคือสถานะ
- `backlog/12.md` ข้อตกลงที่คุณเขียน
- `plan/12.md` โน้ตที่เอเจนต์จดระหว่างทำ
