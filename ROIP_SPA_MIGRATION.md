# ROIP Command Center — คู่มือ SPA และ Docker

> สถานะ: ยกเลิกการนำ SPA ชุดนี้ขึ้นเป็นหน้าหลักแล้ว หน้าใช้งานจริงกลับไปใช้ UI เดิมทั้งหมด เอกสารส่วนที่เหลือเก็บไว้อ้างอิงเฉพาะงานทดลองเท่านั้น

เอกสารนี้อธิบายงานทดลอง Single Page Application (SPA) ด้วย React + TypeScript ซึ่งไม่ได้ถูกเปิดใช้เป็นหน้าหลัก

## ภาพรวมระบบ

```text
Browser
  │
  ▼
Caddy :5000
  ├─ /, /dashboard, /search, /admin/users, /help → React SPA
  ├─ /api/*, /healthz                         → Flask API
  ├─ /static/*                                → ไฟล์เดิมจาก Flask
  └─ /legacy                                  → หน้าควบคุมเดิม (สำรอง)

Flask API ── PostgreSQL
    │
    ├─ Mumble/Ice
    └─ control-service ── Docker socket
```

ส่วนประกอบทั้งหมดรันใน Docker Compose หน้าเว็บถูก build เป็นไฟล์ production ในอิมเมจ `gateway` จึงไม่ต้องติดตั้ง Node.js บนเครื่องที่นำไปใช้งานจริง

## เทคโนโลยีที่ใช้

- React + TypeScript: หน้าเว็บแบบ SPA
- React Router: เปลี่ยนหน้าโดยไม่โหลดเว็บใหม่ และรองรับการเปิด URL ตรง
- TanStack Query: โหลดข้อมูล, cache, polling และจัดการสถานะคำสั่ง
- Zod: เตรียมไว้สำหรับตรวจรูปแบบข้อมูลฝั่งหน้าเว็บ
- Vite: build หน้าเว็บ production
- Flask/Gunicorn: API และงานควบคุมเดิม
- PostgreSQL: ผู้ใช้ สิทธิ์ ประวัติแชท/เสียง bookmark revision และ incident
- Caddy: reverse proxy, gzip/zstd และ SPA fallback

## หน้าที่พร้อมใช้งาน

- `/login` — เข้าสู่ระบบด้วย username/password
- `/dashboard` — สถานี ห้อง ผู้ใช้ออนไลน์ คำสั่งควบคุม บอทถอดเสียง บอทลำโพง และกระจายข้อความ
- `/search` — ค้นหาแชทและเสียงย้อนหลังแบบละเอียด พร้อมบริบท เครื่องเล่นเสียง bookmark แก้ transcript incident บันทึกชุดค้นหา และ export CSV
- `/chat-search` — ชื่อ URL เดิมที่ชี้เข้าหน้าค้นหา SPA
- `/admin/users` — Admin เพิ่ม/แก้/ลบผู้ใช้ เปลี่ยนรหัสผ่าน บทบาท สถานะบัญชี และสิทธิ์ห้อง
- `/help` — คู่มือหน้าควบคุม หน้าค้นหา และการกำหนดสิทธิ์
- `/legacy` — หน้าควบคุมเดิมสำหรับใช้ระหว่างช่วงเปลี่ยนระบบ

## สิทธิ์

- `admin` ใช้งานคำสั่งทั้งหมด สร้าง/ลบห้อง จัดการสถานี ผู้ใช้ และดูประวัติทุกห้อง
- `user` ใช้งานคำสั่งควบคุมได้ แต่สร้าง/ลบห้องและจัดการบัญชีไม่ได้
- ผลการค้นหา ไฟล์เสียง context export bookmark correction และ incident ตรวจสิทธิ์ซ้ำที่ backend เสมอ
- User เห็นประวัติเฉพาะ `station_id + channel_id` ที่ Admin กำหนดให้

การซ่อนปุ่มในหน้าเว็บเป็นเพียงส่วนช่วยการใช้งาน การป้องกันจริงอยู่ที่ API จึงไม่สามารถข้ามสิทธิ์ด้วยการแก้ URL ได้

## วิธีรัน

จากโฟลเดอร์โปรเจกต์:

```powershell
docker compose up -d --build
```

เปิด `http://localhost:5000` แล้วเข้าสู่ระบบ ระบบจะนำไป `/dashboard` อัตโนมัติ

ตรวจสถานะ:

```powershell
docker compose ps
docker compose logs --tail 100 gateway command-center postgres
```

หยุดระบบโดยไม่ลบข้อมูล:

```powershell
docker compose stop
```

เริ่มระบบเดิมอีกครั้ง:

```powershell
docker compose start
```

อย่าใช้ `docker compose down -v` หากไม่ได้ตั้งใจลบ volume ฐานข้อมูล

## พัฒนาเฉพาะหน้าเว็บ

```powershell
cd frontend
npm install
npm run dev
```

ก่อนส่งขึ้นใช้งาน:

```powershell
npm run typecheck
npm run build
```

การแก้หน้าเว็บ production ต้องสั่ง build อิมเมจ `gateway` ใหม่:

```powershell
docker compose up -d --build gateway
```

## ไฟล์สำคัญ

- `frontend/src/App.tsx` — session, login, layout และ routing
- `frontend/src/pages/DashboardPage.tsx` — ศูนย์ควบคุม
- `frontend/src/pages/SearchPage.tsx` — ค้นหาแชทและเสียง
- `frontend/src/pages/AdminUsersPage.tsx` — ผู้ใช้และสิทธิ์
- `frontend/src/pages/HelpPage.tsx` — คู่มือ
- `frontend/src/api.ts` — ตัวกลางเรียก API และจัดการ error/401
- `frontend/src/styles.css` — ธีมและ responsive layout
- `Dockerfile.gateway` — build SPA แล้วบรรจุใน Caddy
- `Caddyfile` — แยก SPA กับ API และรองรับ refresh ทุก route

## ตรวจหลังติดตั้ง

1. เปิด `/dashboard`, `/search`, `/admin/users` และ `/help` ด้วย URL ตรง แล้วกด Refresh ต้องไม่พบ 404
2. Login เป็น Admin และตรวจว่าหน้าจัดการผู้ใช้เปิดได้
3. Login เป็น User และตรวจว่าไม่เห็นหน้าจัดการผู้ใช้กับปุ่มสร้าง/ลบห้อง
4. ตรวจว่า User ค้นหาและเปิดเสียงได้เฉพาะห้องที่ได้รับสิทธิ์
5. เปิด `/healthz` ต้องได้สถานะ HTTP 200 และฐานข้อมูล `ok`
6. หากต้องเทียบพฤติกรรมเดิม ให้เปิด `/legacy`

## สถานะการย้ายระบบ

งานหลักสำหรับใช้งานประจำวันย้ายเข้า SPA แล้ว ส่วนเครื่องมือดูแลระบบขั้นสูงจากหน้าเดิม เช่น ban list, registered users, backup/restore และการตั้งค่า Mumble เชิงลึก ยังเก็บไว้ที่ `/legacy` เพื่อไม่ตัดฟังก์ชันเดิมระหว่างใช้งานจริง และสามารถทยอยย้ายเข้าหน้า SPA ได้โดยไม่กระทบฐานข้อมูลหรือ API เดิม
