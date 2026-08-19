# ROIP Command Center — สรุปสิ่งที่ทำในระบบ

เอกสารนี้สรุปโครงสร้างและฟังก์ชันที่มีอยู่ในโปรเจกต์ ROIP Command Center หลังปรับระบบให้ใช้งานจริงใน Docker พร้อม Login, สิทธิ์ผู้ใช้, ค้นหาแชท และเปิดเสียงย้อนหลัง

> หน้าใช้งานหลักคงหน้าตาและขั้นตอนเดิมทั้งหมด ระบบ React ที่ทดลองไว้ไม่ได้ถูกนำมาใช้เป็นหน้าหลัก เพื่อไม่เปลี่ยนรูปแบบการทำงานของผู้ใช้

## การเร่งความเร็วโดยไม่เปลี่ยน UI

- เพิ่ม cache สถานะ Mumble ระยะสั้น 1.5 วินาที ลดการเปิด Ice connection ซ้ำระหว่าง polling และหลายหน้าต่าง
- เพิ่ม PostgreSQL index สำหรับการกรองสถานี+ห้อง, keyword ตาม message, keyword fuzzy และ incident ตาม message
- เปิด browser cache ไฟล์ CSS/JS/static เป็นเวลา 1 ชั่วโมง
- คง Gunicorn worker เดียวไว้ เพราะระบบบอทและสถานะถอดเสียงอยู่ใน process เดียวกัน หากเพิ่ม worker โดยไม่ย้าย state ไป Redis จะทำให้สถานะคลาดเคลื่อน

ผลตรวจหลังปรับ: คำขอ `/api/server/2` ต่อเนื่องอยู่ประมาณ 5 ms หลัง cache อุ่น, `/healthz` ได้ `ok/database=ok` และหน้าเดิมไม่มี React asset ถูกส่งออกมา

## ธีม iOS Professional

- ปรับ Dashboard, Login, หน้าค้นหา, Help, Modal และ Dropdown ด้วย visual theme เดียวกัน
- ใช้ glass surface, blur, เงานุ่ม, มุมโค้ง และระบบสีแบบ iOS ทั้ง Dark/Light mode
- คง HTML, JavaScript, API, ตำแหน่งข้อมูล และฟังก์ชันเดิมทั้งหมด โดยเพิ่มเฉพาะ stylesheet ชั้นใหม่ `static/ios-theme.css`
- จอกว้างยังแสดงข้อมูล 3 คอลัมน์: ห้องและผู้ใช้ / สถานะและ Logs / Broadcast และ AI
- หน้าค้นหาจอกว้างแสดงตัวกรอง / ผลลัพธ์ / รายละเอียดหลักฐานพร้อมกัน
- รองรับการย่อเป็น 2 คอลัมน์และ 1 คอลัมน์ตามขนาดหน้าจอ
- ตรวจที่ 1280×720 และ 390×844 แล้วไม่เกิด horizontal overflow

## ฟังก์ชันหลัก

- Login ด้วย `username/password` เก็บรหัสผ่านเป็น hash ใน PostgreSQL
- บทบาท `admin` และ `user`
- Admin จัดการผู้ใช้: เพิ่ม, เปลี่ยนบทบาท, เปลี่ยนรหัสผ่าน, เปิด/ปิดบัญชี และลบบัญชี
- ป้องกันไม่ให้ลบ/ลดสิทธิ์/ปิดใช้งาน Admin คนสุดท้าย
- User ใช้งานคำสั่งของศูนย์ควบคุมได้ แต่สร้างห้องหรือลบห้องไม่ได้
- Admin จัดการสถานีและห้องได้ รวมถึงงาน Fleet ที่เกี่ยวข้องกับ Docker ผ่าน `control-service`
- ปุ่ม Help แบบวงกลมอยู่ถัดจากปุ่มออกจากระบบ พร้อมภาพจำลองหน้าจอจริงและหมายเลขกำกับปุ่มทุกขั้นตอน เช่น เชื่อมต่อสถานี วางบอทถอดเสียง วางบอทโทรโข่ง ค้นย้อนหลัง และกำหนดสิทธิ์ผู้ใช้

## ค้นหาแชทและเสียงย้อนหลัง

หน้าใช้งาน: `/chat-search`

ค้นหาได้จาก:

- คำพูด/ข้อความภาษาไทย และรหัสวิทยุ เช่น `ว.8`
- คำใกล้เคียง (fuzzy search)
- สถานี, ห้อง, ผู้พูด, ช่วงเวลา
- ประเภทข้อความ: voice transcript, text chat, TTS, PTT, alert
- มี/ไม่มีไฟล์เสียง
- Keyword, Confidence และสถานะ Incident
- เรียงล่าสุดก่อน/เก่าสุดก่อน และโหลดต่อด้วย cursor pagination

เมื่อเลือกผลลัพธ์จะแสดง:

- Transcript และข้อความที่แก้ไขแล้ว
- สถานี, ห้อง, ผู้พูด, เวลา, Confidence, Keyword
- บริบทก่อน–หลังในห้องเดียวกัน
- เครื่องเล่นเสียงย้อนหลัง พร้อม SHA-256 ของไฟล์
- Bookmark/Note, แก้ Transcript แบบเก็บ Revision และเปิด Incident
- Export CSV โดยใช้ขอบเขตสิทธิ์เดียวกับหน้าจอค้นหา

## กติกาสิทธิ์ข้อมูลย้อนหลัง

| บทบาท | ขอบเขตข้อมูล |
|---|---|
| Admin | ดู ค้นหา เปิดเสียง แก้ Transcript Bookmark Incident และ Export ได้ทุกสถานี/ทุกห้อง |
| User | ดู ค้นหา เปิดเสียง และจัดการหลักฐานได้เฉพาะห้องที่ Admin ผูกกับบัญชี |
| User ที่ยังไม่มีห้อง | ไม่เห็นผลลัพธ์และไม่สามารถเปิดเสียงจากห้องอื่นได้ |

สิทธิ์ห้องเก็บในตาราง `user_room_permissions` โดยใช้คู่ `station_id + channel_id` ต่อบัญชี ตัวอย่าง:

```text
username   station_id   channel_id   channel_name
somchai    2            0            Root (ห้องหลัก)
somchai    2            3            ภาคเหนือ
```

ข้อมูลเก่าที่ไม่มี `channel_id` จะถูกตีความเป็น Root (`channel_id=0`) เพื่อไม่ให้ข้อความจากการ migrate เดิมหายจากขอบเขตของ User ที่ได้รับสิทธิ์ Root

การกำหนดห้อง:

1. Login เป็น Admin
2. เปิด Command Center → **ผู้ใช้ระบบ**
3. เลือกห้องในช่อง “ห้องที่ User มีสิทธิ์ค้นหา/เปิดเสียงย้อนหลัง”
4. กด **บันทึก**

ระบบตรวจสิทธิ์ที่ backend ซ้ำใน endpoint ต่อไปนี้:

- `/api/chat/search`
- `/api/chat/messages/<id>/context`
- `/api/chat/messages/<id>/audio`
- `/api/chat/messages/<id>/correction`
- `/api/chat/bookmarks`
- `/api/chat/cases`
- `/api/chat/export.csv`

ดังนั้นการเปลี่ยน URL หรือ `message_id` เองไม่สามารถข้ามสิทธิ์ห้องได้

## ปุ่ม Help ในหน้าค้นหา

ปุ่ม **? วิธีใช้** อยู่ด้านขวาบนของ `/chat-search` และเปิดคู่มือขนาดใหญ่แบบ 3 คอลัมน์บนจอ Desktop โดยอธิบายฟังก์ชันครบ 10 กลุ่ม:

- Admin กับ User เห็นข้อมูลต่างกันอย่างไร
- ช่องค้นหาและปุ่มลัด
- สถานี ผู้พูด และช่วงเวลา
- ประเภทข้อมูล Voice Transcript, Alert, Text Chat, TTS และ PTT
- ตัวกรองเสียง Keyword Incident Confidence และคำใกล้เคียง
- การอ่าน เรียง และโหลดผลลัพธ์ต่อ
- การเปิดเสียง ดู metadata และบริบทก่อน–หลัง
- Bookmark, แก้ Transcript และเปิด Incident
- บันทึกชุดค้นหาและ Export CSV
- การล้างตัวกรองและแนวทางแก้ปัญหา

หน้าค้นหาใช้ความสูงเต็มจอ โดยแผงตัวกรอง รายการผลลัพธ์ และรายละเอียดเลื่อนแยกกัน รายการผลลัพธ์และแผงรายละเอียดถูกขยายให้กว้างขึ้นเพื่อลดการเลื่อนทั้งหน้าไปมา

ด้านบนหน้าค้นหายังมีป้ายขอบเขต เช่น `ADMIN · ดูได้ทุกห้อง` หรือ `USER · 2 ห้องที่ได้รับอนุญาต`

คู่มือหลักของ Command Center มีภาพสรุป Workflow ตั้งแต่เลือกสถานี ควบคุมแบบสด ค้นหาย้อนหลัง จนถึงการเก็บหลักฐาน ส่วนคู่มือหน้าค้นหามีภาพลำดับการกรองข้อมูล ตรวจผลลัพธ์ และเปิดเสียง/สร้าง Incident เพื่อให้เจ้าหน้าที่เริ่มใช้งานได้จากหน้าจอเดียว

## โครงสร้างข้อมูล PostgreSQL

- `app_users` — บัญชีและบทบาท
- `user_room_permissions` — ห้องที่ User มีสิทธิ์เข้าถึง
- `stations` — รายการสถานี
- `chat_messages` — Transcript/แชท/PTT/TTS/Alert
- `audio_assets` — metadata ไฟล์เสียง, SHA-256, ขนาด และ retention
- `keyword_hits` — คำเฝ้าระวังที่ตรวจพบ
- `message_bookmarks` — Bookmark และ Note รายผู้ใช้
- `transcript_revisions` — ประวัติแก้ Transcript
- `alert_cases`, `case_messages` — Incident และข้อความที่ผูกไว้
- `saved_searches` — ชุดค้นหาที่บันทึก
- `audit_events`, `user_audit_events` — ประวัติการใช้งานและการจัดการสิทธิ์

มีดัชนีสำหรับเวลา, สถานี, ห้อง, ผู้พูด, เสียง, Keyword และ GIN trigram สำหรับการค้นหาข้อความ

## โครงสร้าง Docker

```text
gateway (Caddy :5000)
  └── command-center (Flask + Gunicorn)
        ├── postgres (ข้อมูลหลัก)
        ├── control-service (งาน Docker socket เท่านั้น)
        └── static/records (ไฟล์เสียง)

mumble-node1..4 + node ที่สร้างเพิ่ม ใช้ named volume แยกกัน
```

คำสั่งหลัก:

```powershell
docker compose build --pull
docker compose up -d
docker compose ps
```

เปิดใช้งานที่ `http://localhost:5000`

## ค่าบัญชีเริ่มต้น

ตั้งใน `.env`:

```dotenv
ADMIN_USERNAME=admin
ADMIN_PASSWORD=เปลี่ยนเป็นรหัสผ่านที่ยาวอย่างน้อย 8 ตัวอักษร
```

หลัง Login ครั้งแรกควรเปลี่ยนรหัสผ่านและเพิ่มบัญชีแยกสำหรับเจ้าหน้าที่แต่ละคน

## ไฟล์ที่เกี่ยวข้อง

- `app.py` — Flask routes, session และ API หลัก
- `roip_auth.py` — Login, บัญชี, บทบาท และสิทธิ์ห้อง
- `roip_search/db.py` — schema bootstrap, migration, search และ access-scope query
- `roip_search/routes.py` — API ค้นหา/เสียง/บริบท/Export
- `roip_search/schema.sql` — PostgreSQL schema และ index
- `templates/chat_search.html` — หน้า Search และ Help dialog
- `static/chat-search.js` — ตัวกรอง ผลลัพธ์ และการเปิดหลักฐาน
- `static/chat-search.css` — รูปแบบหน้าค้นหา
- `templates/index.html` — Command Center และ modal จัดการผู้ใช้/สิทธิ์ห้อง
- `ROIP_CHAT_SEARCH.md` — คู่มือติดตั้ง สำรอง กู้คืน และแก้ปัญหา

## การตรวจสอบหลังแก้ไข

- ตรวจ Python syntax ด้วย `python -m py_compile app.py roip_auth.py roip_search/db.py roip_search/routes.py`
- ตรวจ JavaScript หน้า Search ด้วย `node --check static/chat-search.js`
- บนเครื่องที่มี Docker ให้ rebuild แล้วตรวจ `docker compose ps` และ `http://localhost:5000/healthz`
- ทดสอบจริงด้วยบัญชี Admin และ User: Admin ต้องเห็นทุกห้อง, User ต้องเห็นเฉพาะห้องที่กำหนด และ User ต้องเปิดเสียงของห้องอื่นไม่ได้

## ข้อควรทำก่อนใช้งานจริง

- กำหนดห้องให้ User ทุกบัญชีอย่างน้อยหนึ่งห้อง
- เปลี่ยนรหัสผ่าน Admin และค่า secret ใน `.env`
- ตั้ง retention และ backup ของ PostgreSQL/ไฟล์เสียง
- เปิด HTTPS และตั้ง `SESSION_COOKIE_SECURE=true` เมื่อใช้งานผ่านเครือข่ายภายนอก
- ตรวจพื้นที่ดิสก์ของ `static/records` และ PostgreSQL เป็นระยะ

## UI แบบ D · Spatial Network (19 สิงหาคม 2026)

Dashboard และหน้าค้นหาถูกปรับเป็นโทนดำ–น้ำเงินแบบ Spatial Network โดยไม่เปลี่ยน API หรือสิทธิ์เดิม:

- Dashboard มีแผนผังสถานีและห้องแบบโหนด ซึ่งสร้างจากสถานี ห้อง และผู้ใช้งานจริง
- กดโหนดห้องเพื่อเลื่อนไปยังการ์ดห้องและใช้คำสั่งเดิมได้ทันที
- Header มีตัวเลือก `แผนผัง`, `หน้าแชท`, `หน้า Log` และ `ประวัติ`; การเลือกถูกจำไว้ในเบราว์เซอร์
- แผนผังมี Radar sweep, วงสแกน, จุดสัญญาณวิ่งตามเส้นเชื่อม และ Beacon สำหรับห้องที่มีผู้ใช้งาน; ชื่อสถานีตัดบรรทัดและอยู่ภายในวงศูนย์กลางเสมอ
- คำสั่งเปลี่ยนรหัสผ่านเซิร์ฟเวอร์อยู่ในเมนู `⋮` ของแผงสถานะระบบ และเปิดเป็น Popup แยก; เว้นรหัสว่างเพื่อปลดรหัสผ่าน
- เพิ่ม `SERVER_INSTALLATION_GUIDE.md` สำหรับติดตั้งบน Ubuntu Server ด้วย Docker Compose, การตั้งค่า `.env`, firewall, ตรวจสุขภาพ, อัปเดต และสำรองข้อมูล
- เพิ่ม `WINSCP_INSTALLATION_GUIDE.md` สำหรับส่งไฟล์จาก Windows ขึ้น Server ด้วย WinSCP/SFTP โดยไม่ทับข้อมูล Production
- หน้าแชทและหน้า Log ใช้พื้นที่โซนขวาเต็มความสูง พร้อมเก็บ Broadcast, PTT, AI Bot, Export และคำสั่งเดิมทั้งหมด
- มุมมอง `ประวัติ` เปิดระบบค้นหาแชทและเสียงเดิมในโซนขวาแบบ SPA โดยไม่เปลี่ยนหน้าหลัก และไม่ซ่อนปุ่มไว้ในเมนู AI
- หน้าค้นหาใช้ธีมเดียวกัน มีแถบขอบเขตเครือข่าย และสลับรูปแบบผลลัพธ์ระหว่าง `หน้าแชท` กับ `หน้า Log`
- สิทธิ์ Admin/User, ตัวกรอง, เล่นเสียง, Bookmark, แก้ Transcript, Incident และ CSV Export ไม่เปลี่ยนแปลง

ไฟล์ UI ที่เพิ่มหรือแก้ไข:

- `static/spatial-network.css` — ธีมดำ Spatial Network และโหมดแสดงผล
- `templates/index.html` — แผนผัง Dynamic และ Header view switch
- `templates/chat_search.html` — Search network scope และ Chat/Log view switch
