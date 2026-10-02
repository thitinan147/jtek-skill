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

เปิด repo ที่จะทำ งานเดินแบบนี้ สถานะที่เชื่อมีแค่คำบนบรรทัดของ board Codex ใช้ `$` แทน `/` ในตารางด้านล่าง

```mermaid
flowchart TD
  subgraph person ["คน"]
    card["เขียน card<br/>ทำ ไม่ทำ ตรวจผ่านเมื่อ"]
    edit["แก้ card"]
    look["เทียบหลักฐาน<br/>กับหัวตรวจผ่านเมื่อ"]
    done["รับ<br/>บรรทัดเป็น merge"]
    back["ส่งกลับ<br/>บรรทัดเป็น ส่งกลับ"]
    drop["ปิดข้อ<br/>บรรทัดเป็น ปิด"]
  end

  subgraph agent ["เอเจนต์"]
    line["อ่านบรรทัดบน board"]
    ask["เขียน ถาม แล้วหยุด"]
    work["ลงมือบน branch<br/>เก็บเทสและหลักฐาน"]
    wait["ตั้งบรรทัดเป็น รอรีวิว<br/>แล้วหยุด"]
  end

  card --> line
  line -->|เจตนาไม่ปิด| ask
  ask --> edit --> line
  line -->|เจตนาปิด| work
  work -->|ไปต่อไม่ได้| ask
  work -->|หลักฐานผ่าน| wait
  wait --> look
  look --> done
  look --> back
  look --> drop
  back --> work

  classDef human fill:#e7f6ec,stroke:#1b7f3b,color:#123
  classDef bot fill:#e7f0fb,stroke:#1d4e89,color:#123
  class card,edit,look,done,back,drop human
  class line,ask,work,wait bot
```

ข้อ 12 เป็นตัวอย่างของคำสั่งที่พิมพ์ในแต่ละขั้น

| ขั้น | พิมพ์ | เกิดอะไร |
|---|---|---|
| เริ่ม repo นี้ | `/tek-setup-board` | ได้ `card-loop/board.md` คุณเติมตารางคำสั่งเทส |
| ดู skill ของ repo | `/tek-scan-skills` | คำแนะนำสองกลุ่มจาก skill บนเครื่องและจาก skills.sh เฉพาะใบที่เห็นจำนวนคนติดตั้ง คุณติดตั้งเอง ชื่อที่ช่วยลงมือใส่ `<TEK_SKILLS>` ชื่อของ repo ใส่ `<REPO_SKILLS>` |
| เพิ่มข้อ | `/tek-add-card 12` | ได้ `card-loop/backlog/12.md` คุณเขียนทำ ไม่ทำ และตรวจผ่านเมื่อ |
| ให้ทำให้ | `/tek-do-card` | เอเจนต์ทำข้อที่บรรทัดอนุญาต แล้วตั้ง `รอรีวิว:` หรือเขียน `ถาม:` |
| ดูของที่เปิดไว้ | `/tek-open-review` | เทียบหัวตรวจผ่านเมื่อ ตารางการตัดสินใจใน plan และ diff |
| รับ | `/tek-mark-merge` | ติ๊ก `merge:` |
| ส่งกลับ | `/tek-send-back` แล้ว `/tek-do-card` | บรรทัดเป็น `ส่งกลับ:` แล้วเอเจนต์ทำข้อเดิมต่อ |
| ไม่เอา | `/tek-mark-close ไม่ทำแล้ว` | ติ๊ก `ปิด:` พร้อมเหตุ |
| ดูคิว | `/tek-read-board` | บอกว่าข้อไหนค้าง เรียกได้ทุกจังหวะ |

## ไฟล์ที่อยู่ใน repo คุณ

commit โฟลเดอร์ `card-loop/`

- `board.md` คิว คำสั่งเทส แถว `<TEK_SKILLS>` และ `<REPO_SKILLS>` คำบนบรรทัดคือสถานะ
- `backlog/12.md` ข้อตกลงที่คุณเขียน
- `plan/12.md` โน้ตของเอเจนต์ และตารางการตัดสินใจที่คุณอ่านตอน review
