# ROIP Command Center — Chat Search และโครงสร้าง Docker

เอกสารนี้เป็นคู่มือติดตั้ง ใช้งาน สำรอง และกู้คืนระบบที่ปรับปรุงแล้ว โดยทุก service ทำงานใน Docker Compose และเปิดหน้าเว็บผ่านจุดเดียวที่ `http://<IP-เครื่อง>:5000`

ในหน้า Command Center มีปุ่ม **❔ HELP** ด้านขวาบน เปิดคู่มือแบบย่อสำหรับเจ้าหน้าที่ได้ทันที โดยไม่ต้องออกจากหน้าปฏิบัติงาน

## สิ่งที่เพิ่มให้แล้ว

- หน้าค้นหาใหม่ `/chat-search` รองรับคำไทย รหัสวิทยุ เช่น `ว.8`/`ว8` และค้นหาแบบคำใกล้เคียง
- ตัวกรองสถานี ห้อง ผู้พูด ช่วงเวลา ประเภทข้อความ Keyword ความมั่นใจ มี/ไม่มีเสียง และสถานะ Incident
- เลื่อนดูผลแบบ cursor pagination ซึ่งเสถียรกว่าเลขหน้าเมื่อมีข้อความใหม่เข้าตลอดเวลา
- เปิดบริบทก่อน–หลังข้อความ เล่นไฟล์เสียง ดู SHA-256 และส่งออก CSV ภาษาไทย
- Bookmark พร้อม tag/note, แก้ transcript แบบเก็บทุก revision, รวมข้อความเป็น Incident และบันทึกชุดค้นหา
- PostgreSQL พร้อมดัชนีเวลา สถานี ผู้พูด Keyword และ GIN trigram สำหรับค้นหาข้อความ
- ย้าย `ai_transcripts` และ `keyword_alerts` จาก `tactical.db` เข้า PostgreSQL อัตโนมัติแบบ idempotent โดยไม่ลบฐานเดิม
- บันทึก audit สำหรับการค้นหา เปิดเสียง แก้ข้อความ Bookmark Incident และ Export
- เพิ่มสิทธิ์ค้นหาย้อนหลังแบบผูกห้อง: Admin เห็นทุกสถานี/ทุกห้อง ส่วน User เห็นและเปิดเสียงได้เฉพาะห้องที่ Admin กำหนด
- เพิ่มปุ่ม **? วิธีใช้** ในหน้าค้นหา อธิบายขอบเขตสิทธิ์ ตัวกรอง การเปิดเสียง และการ Export
- เพิ่มเมนูจัดการสิทธิ์ห้องใน **ผู้ใช้ระบบ** เพื่อเลือกสถานี/ห้องให้ User แต่ละบัญชี
- ใช้ Gunicorn แทน Flask development server, มี Caddy gateway, health check และ restart policy
- แยกสิทธิ์ Docker socket ไปไว้ใน `control-service`; ตัวเว็บหลักไม่แตะ Docker socket โดยตรง
- ป้องกัน SQL injection ในการค้นหาเดิม, ตรวจ token ของ AI bot, และกู้ ZIP แบบ allow-list เพื่อกัน path traversal

## โครงสร้าง runtime

```text
ผู้ใช้ :5000
   │
   ▼
Caddy gateway
   │
   ▼
command-center (Flask + Gunicorn)
   ├── PostgreSQL 17       ข้อความ/ค้นหา/Bookmark/Incident/Audit
   ├── tactical.db         ฐานเดิมและ fallback ระหว่างเปลี่ยนระบบ
   ├── static/records      ไฟล์เสียงหลักฐาน
   └── control-service     สร้าง/ลบ Mumble container ผ่าน token ภายใน
          │
          └── Docker socket

Mumble node 1..4 + node ที่สร้างเพิ่ม ใช้ named volume แยกกัน
```

ไฟล์สำคัญ:

- `docker-compose.yml` — service, volume, health check และ resource limit ทั้งหมด
- `Dockerfile`, `Dockerfile.control`, `gunicorn.conf.py`, `Caddyfile` — image แยกของเว็บ/control และ production web stack
- `roip_search/schema.sql` — schema PostgreSQL และดัชนี
- `roip_search/db.py`, `roip_search/routes.py` — ingest, migration, search และ API
- `templates/chat_search.html`, `static/chat-search.js`, `static/chat-search.css` — หน้าค้นหา
- `roip_auth.py` — บัญชีผู้ใช้และตาราง `user_room_permissions`
- `control_service.py` — service สิทธิ์สูงสำหรับงาน Docker เท่านั้น
- `.env.example` — รายการค่าที่ต้องตั้งก่อนใช้จริง

## เริ่มระบบครั้งแรก

ต้องมี Docker Engine และ Docker Compose plugin บนเครื่อง host เท่านั้น ไม่ต้องติดตั้ง Python/PostgreSQL/Caddy ใน host

1. สำรอง `tactical.db`, `servers.json`, `.env`, `.secret_key` และโฟลเดอร์ `static/records` ก่อนอัปเกรด
2. ถ้ายังไม่มี `.env` ให้คัดลอก `.env.example` เป็น `.env`; ถ้ามีแล้วให้เพิ่ม key ที่ขาด
3. เปลี่ยนค่า `CHANGE_ME` ทุกค่า โดยเฉพาะ `ADMIN_PASSWORD`, `FLASK_SECRET_KEY`, `AI_BOT_TOKEN`, `CONTROL_API_TOKEN`, `POSTGRES_PASSWORD` และ `MUMBLE_ICE_SECRET`
4. ตรวจ config และเปิดระบบ:

```powershell
docker compose config
docker compose build --pull
docker compose up -d
docker compose ps
```

5. เปิด `http://localhost:5000` หรือตาม IP ของเครื่อง จากนั้น Login และเลือกเมนู **ค้นหาแชท**

เมื่อเปลี่ยน Caddy เป็น HTTPS แล้ว ให้ตั้ง `SESSION_COOKIE_SECURE=true`; ในโหมด HTTP ภายในให้คงเป็น `false` มิฉะนั้น browser จะไม่ส่ง session cookie

ดูสถานะเมื่อเริ่มครั้งแรก:

```powershell
docker compose logs -f --tail=200 command-center postgres control-service gateway
```

การเริ่มครั้งแรกจะสร้าง schema และนำเข้าข้อมูลเดิม อาจช้าตามจำนวน transcript และขนาดไฟล์เสียง ระบบจำ ID ล่าสุดของแต่ละตารางไว้ รอบถัดไปจึงอ่านเฉพาะข้อมูลใหม่/งาน fallback ที่ยังไม่ถูกนำเข้า และใช้ `source_event_id` กันข้อความซ้ำอีกชั้นหนึ่ง

## ค่าเครือข่าย

- หน้าเว็บใช้ TCP `5000`
- Mumble node เดิมใช้ TCP/UDP `64740` ถึง `64743`
- PostgreSQL และ control-service เปิดเฉพาะใน Docker network ไม่ publish ออก host
- Mumble node ที่สร้างจากหน้าเว็บจะใช้ port ที่ระบบจัดให้ต่อจากช่วงที่มีอยู่

ถ้าใช้ firewall ให้เปิดเฉพาะ TCP 5000 และ TCP/UDP ของ Mumble ที่จำเป็น ไม่ควรเปิด PostgreSQL หรือ Docker API สู่อินเทอร์เน็ต

## วิธีใช้หน้าค้นหา

1. กด **ค้นหาแชท** จากหน้า Command Center
2. พิมพ์คำค้น หรือเลือกตัวกรองหลายรายการร่วมกัน
3. เปิด **คำใกล้เคียง** เมื่อต้องการรองรับ transcript ที่สะกดคลาดเคลื่อน; คำต้องยาวอย่างน้อย 3 ตัวอักษร
4. คลิกผลลัพธ์เพื่อดูบริบทก่อน–หลังและเล่นเสียงหลักฐาน
5. ใช้ Bookmark สำหรับงานติดตาม, **แก้ Transcript** เมื่อ STT ผิด และ **สร้าง Incident** สำหรับเหตุสำคัญ
6. กด **บันทึกชุดค้นหา** เพื่อเรียกตัวกรองเดิมซ้ำ หรือ **Export CSV** สำหรับรายงานไม่เกิน 10,000 แถวต่อครั้ง

### ขอบเขตสิทธิ์ห้อง

- **Admin**: ค้นข้อความย้อนหลัง เปิดไฟล์เสียง ดูบริบท แก้ Transcript, Bookmark, Incident และ Export ได้ทุกสถานี/ทุกห้อง
- **User**: ทำรายการข้างต้นได้เฉพาะห้องที่ผูกไว้กับบัญชีในตาราง `user_room_permissions` เท่านั้น ถ้าไม่มีห้องที่กำหนดจะไม่เห็นผลลัพธ์
- สิทธิ์ถูกตรวจซ้ำที่ backend ใน Search, Context, Audio, Correction, Bookmark, Incident และ Export จึงไม่สามารถเปลี่ยน `message_id` หรือ URL เพื่อข้ามขอบเขตได้
- การกำหนดห้องทำจากหน้า Command Center → **ผู้ใช้ระบบ** → เลือกห้องในช่อง “ห้องที่ User มีสิทธิ์ค้นหา/เปิดเสียงย้อนหลัง” → **บันทึก**
- ปุ่ม **? วิธีใช้** ด้านขวาบนของหน้าค้นหาแสดงคำอธิบายสิทธิ์และตัวกรองแบบย่อ โดยไม่ต้องออกจากหน้า

ตัวอย่างข้อมูลที่ระบบบันทึกเมื่อกำหนดสิทธิ์:

```text
username   station_id   channel_id   channel_name
somchai    2            0            Root (ห้องหลัก)
somchai    2            3            ภาคเหนือ
```

ถ้า Mumble node offline ตอนเปิดหน้าจัดการผู้ใช้ ระบบจะแสดง Root ของสถานีนั้นเป็นตัวเลือกสำรอง ให้ตรวจสอบชื่อ/รหัสห้องอีกครั้งเมื่อ node กลับมาออนไลน์

ช่อง “แจ้งเตือนเมื่อพบใหม่” ใน Saved Search ถูกเก็บในฐานข้อมูลแล้ว แต่ยังไม่ส่ง Notification ภายนอก จนกว่าจะเชื่อมช่องทางแจ้งเตือนและ worker ในรอบถัดไป

## การเก็บข้อมูล

- PostgreSQL อยู่ใน named volume `postgres-data`
- Mumble แต่ละ node อยู่ใน named volume ของตัวเอง
- SQLite เดิม, รายการสถานี, secret key และเสียง ใช้ bind mount จากโฟลเดอร์โครงการเพื่อให้สำรองง่าย
- การลบ Mumble node แบบ dynamic จะลบ container แต่ตั้งใจเก็บ volume ไว้เพื่อกู้ข้อมูลได้
- ปุ่มล้างเสียงแจ้งเตือนลบเฉพาะไฟล์ `record_*.wav` ไม่ลบไฟล์ TTS/PTT อื่นโดยรวม

## สำรองข้อมูล

สำรอง PostgreSQL:

```powershell
docker compose exec postgres pg_dump -U roip -d roip -Fc -f /tmp/roip-postgres.dump
docker cp roip-postgres:/tmp/roip-postgres.dump .\roip-postgres.dump
```

สำรองฐานเดิมและไฟล์ประกอบ:

```powershell
Compress-Archive -Path tactical.db,servers.json,.env,.secret_key,static/records -DestinationPath roip-files.zip
```

ควรเก็บ dump และ zip ไว้นอกเครื่องระบบ พร้อมทดสอบกู้คืนเป็นระยะ ไฟล์ `.env` และ `.secret_key` เป็นความลับ ต้องเข้ารหัสหรือจำกัดสิทธิ์ที่จัดเก็บ

## กู้คืน

หยุดส่วนเว็บก่อนเพื่อไม่ให้มีการเขียนระหว่างกู้:

```powershell
docker compose stop command-center gateway
docker cp .\roip-postgres.dump roip-postgres:/tmp/roip-postgres.dump
docker compose exec postgres pg_restore -U roip -d roip --clean --if-exists /tmp/roip-postgres.dump
docker compose up -d command-center gateway
```

สำหรับไฟล์เดิม สามารถแตก `roip-files.zip` กลับตำแหน่งเดิมขณะ service หยุด หรือใช้หน้า Maintenance อัปโหลด ZIP ที่มีเฉพาะ `tactical.db`, `servers.json`, `.env` แล้วสั่ง:

```powershell
docker compose restart command-center
```

## อัปเดตและย้อนกลับ

ก่อนอัปเดตทุกครั้งให้ทำ backup แล้วจึงใช้:

```powershell
docker compose build --pull
docker compose up -d
docker compose ps
```

การย้อนกลับควรใช้ไฟล์โครงการชุดก่อนหน้าและ backup ที่สร้างก่อนอัปเดต แล้วรัน `docker compose up -d --build` อีกครั้ง ห้ามลบ named volume จนกว่าจะยืนยันว่าข้อมูลใหม่ไม่ต้องใช้

## ตรวจสอบและแก้ปัญหา

```powershell
docker compose ps
docker compose logs --tail=200 command-center
docker compose logs --tail=200 postgres
docker compose exec command-center python -m unittest discover -s tests -v
```

- หน้าเว็บไม่ขึ้น: ตรวจว่า `gateway` และ `command-center` เป็น healthy
- ค้นหาไม่ได้: ตรวจ `postgres` และค่า `POSTGRES_*` ใน `.env`
- สร้าง node ไม่ได้: ตรวจ `control-service`, Docker socket และ port ซ้ำ
- ถ้า `roip-mumble6` ในรายการเดิมขึ้น Offline บนเครื่องใหม่: node นี้เป็นสถานี dynamic เดิมและไม่ได้อยู่ใน Compose คงที่ 4 ตัว ให้ลบสถานีหมายเลข 6 จากหน้า Fleet แล้วสร้างใหม่ ระบบจะสร้าง container/volume ให้ผ่าน `control-service` (สำรอง volume เดิมก่อนถ้ามีข้อมูลสำคัญ)
- เปิดเสียงไม่ได้ (HTTP 410): metadata ยังอยู่แต่ไฟล์ใน `static/records` ถูกย้าย/หมดอายุ
- AI bot ส่ง transcript ไม่เข้า: `AI_BOT_TOKEN` ของ bot และ command-center ต้องตรงกัน

## ข้อจำกัดและสิ่งที่ควรเพิ่มรอบถัดไป

- ระบบ Login ใช้บัญชีรายบุคคลใน PostgreSQL และเก็บรหัสผ่านเป็น hash โดยสร้าง Admin เริ่มต้นจาก `ADMIN_USERNAME` / `ADMIN_PASSWORD` ใน `.env`
- สิทธิ์ `User`: สั่งการระบบได้ทุกอย่าง รวมถึงย้าย/เตะ/แบน/ปิดไมค์/ส่งข้อความ/ตั้งค่าห้อง แต่สร้างหรือลบห้องไม่ได้
- สิทธิ์ `Admin`: ทำได้เหมือน User และสร้าง/ลบห้อง จัดการสถานี รวมถึงสร้าง แก้บทบาท รีเซ็ตรหัสผ่าน และปิดใช้งานบัญชีผู้ใช้ได้
- ระบบไม่อนุญาตให้ลดสิทธิ์/ปิดใช้งาน/ลบ Admin คนสุดท้าย และทุก API สำคัญตรวจสิทธิ์ซ้ำที่ backend ไม่พึ่งเฉพาะการซ่อนปุ่มบนหน้าเว็บ
- สิทธิ์ User สำหรับข้อมูลย้อนหลังเป็นแบบ allow-list รายห้อง; การสั่งการหน้า Command Center ยังคงเป็นไปตามกติกาเดิม (User สั่งการได้ แต่สร้าง/ลบห้องไม่ได้)
- Saved Search Notification ต้องเพิ่ม worker และช่องทางส่ง เช่น LINE/Teams/Email
- Export เกิน 10,000 แถวควรเปลี่ยนเป็น background job พร้อมวันหมดอายุของไฟล์
- ควรกำหนด retention policy ของเสียง, ทำ PostgreSQL backup อัตโนมัติ และเพิ่ม monitoring/alert ของ disk, database และ container health
- สำหรับการเปิดผ่านเครือข่ายภายนอก ควรเพิ่มชื่อโดเมนและ HTTPS ใน `Caddyfile` ก่อนใช้งาน
