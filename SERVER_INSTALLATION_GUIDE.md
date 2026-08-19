# คู่มือติดตั้ง ROIP Command Center บนเซิร์ฟเวอร์

ถ้าส่งไฟล์จาก Windows ด้วย WinSCP ให้ใช้คู่มือแบบละเอียดที่ [WINSCP_INSTALLATION_GUIDE.md](WINSCP_INSTALLATION_GUIDE.md)

เอกสารนี้ใช้สำหรับติดตั้งระบบบน Ubuntu Server 22.04/24.04 LTS ด้วย Docker Compose ระบบจะเปิด Command Center, PostgreSQL, Control Service, Gateway และ Mumble stations ที่กำหนดใน `docker-compose.yml`

## 1. สิ่งที่ต้องเตรียม

- Ubuntu Server 22.04 หรือ 24.04 LTS, RAM อย่างน้อย 4 GB และพื้นที่ว่างอย่างน้อย 20 GB
- IP สาธารณะหรือ IP ภายในที่เครื่องใช้งานเข้าถึงได้
- สิทธิ์ `sudo`
- Docker Engine และ Docker Compose plugin
- โฟลเดอร์โปรเจกต์นี้ครบทั้งโฟลเดอร์ รวมถึง `.env.example`, `docker-compose.yml`, Dockerfile และไฟล์ `static/`

พอร์ตที่ต้องอนุญาตตามการใช้งานจริง:

| ใช้งาน | พอร์ต | โปรโตคอล |
| --- | --- | --- |
| หน้า ROIP Command Center | `5000` | TCP |
| Mumble station 1–4 | `64740–64743` | TCP และ UDP |

พอร์ต ICE และ PostgreSQL อยู่ใน Docker network ภายใน ไม่ควรเปิดออกอินเทอร์เน็ต

## 2. ติดตั้ง Docker บน Ubuntu

รันคำสั่งต่อไปนี้บนเซิร์ฟเวอร์:

```bash
sudo apt update
sudo apt install -y ca-certificates curl git
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker "$USER"
newgrp docker
docker --version
docker compose version
```

หากเซิร์ฟเวอร์ใช้ UFW ให้เปิดเฉพาะพอร์ตที่จำเป็น:

```bash
sudo ufw allow 5000/tcp
sudo ufw allow 64740:64743/tcp
sudo ufw allow 64740:64743/udp
sudo ufw enable
```

## 3. นำโปรเจกต์ขึ้นเซิร์ฟเวอร์

### ทางเลือก A: ใช้ Git

```bash
git clone <URL-REPOSITORY> roip-command-center
cd roip-command-center
```

### ทางเลือก B: ส่งจากเครื่อง Windows ด้วย SCP

รันจาก PowerShell บนเครื่องพัฒนา แล้วแทนค่า IP และชื่อผู้ใช้:

```powershell
scp -r C:\Users\PC\Documents\mumbledocker user@SERVER_IP:/opt/roip-command-center
```

จากนั้นเชื่อมต่อ SSH และเข้าโฟลเดอร์:

```bash
ssh user@SERVER_IP
cd /opt/roip-command-center
```

## 4. ตั้งค่าความลับก่อนเปิดระบบ

ให้แก้ไฟล์ `.env` ที่อยู่โฟลเดอร์เดียวกับ `docker-compose.yml` เช่น `/opt/roip-command-center/.env` ไม่ใช่ `.env.example`

ห้ามนำไฟล์ `.env` ของเครื่องพัฒนาไปใช้บน Production โดยไม่เปลี่ยนค่า secret

```bash
cp .env.example .env
openssl rand -hex 32
openssl rand -hex 48
```

เปิดแก้ไฟล์ `.env`:

```bash
nano .env
```

เปลี่ยนค่าอย่างน้อยรายการต่อไปนี้ให้เป็นค่าที่เดายากและไม่ซ้ำกัน:

```dotenv
ADMIN_USERNAME=admin
ADMIN_PASSWORD=รหัสผ่านผู้ดูแลที่ยาวและเดายาก
FLASK_SECRET_KEY=ผลลัพธ์-openssl-rand-hex-32
AI_BOT_TOKEN=ผลลัพธ์-openssl-rand-hex-48
CONTROL_API_TOKEN=ผลลัพธ์-openssl-rand-hex-48
POSTGRES_PASSWORD=รหัสผ่านฐานข้อมูลที่ยาวและเดายาก
MUMBLE_ICE_SECRET=secret-สำหรับ-ICE
```

หากหน้าเว็บเข้าผ่าน HTTPS ด้วย Reverse Proxy ที่เชื่อถือได้แล้ว ให้ตั้ง `SESSION_COOKIE_SECURE=true` หากยังเข้าโดย `http://IP:5000` ให้คงเป็น `false` มิฉะนั้น Browser จะไม่ส่ง session cookie

## 5. สร้างและเปิดระบบ

หาก Docker รุ่นเก่าไม่รู้จัก `docker compose` ให้ใช้ `docker-compose` แทน หรืออัปเดตด้วย `sudo apt install -y docker-compose-plugin`

```bash
docker compose up -d --build
docker compose ps
curl http://127.0.0.1:5000/healthz
```

ผล health check ที่ถูกต้อง:

```json
{"database":"ok","status":"ok"}
```

เปิด Browser ไปที่:

```text
http://SERVER_IP:5000
```

เข้าสู่ระบบด้วย `ADMIN_USERNAME` และ `ADMIN_PASSWORD` ที่ตั้งใน `.env` แล้วเพิ่มบัญชีเจ้าหน้าที่จากปุ่ม `ผู้ใช้ระบบ`

## 6. ตรวจสอบและแก้ปัญหา

ดูสถานะทั้งหมด:

```bash
docker compose ps
```

ดู Log ของหน้าเว็บหรือฐานข้อมูล:

```bash
docker compose logs -f command-center
docker compose logs -f postgres
docker compose logs -f gateway
```

รีสตาร์ตเฉพาะหน้า Command Center:

```bash
docker compose up -d --no-deps command-center
```

หากเปิดเว็บไม่ได้ ให้ตรวจ firewall, พอร์ต `5000`, สถานะ `gateway` และผล `/healthz` ก่อน

## 7. อัปเดตเวอร์ชัน

สำรองข้อมูลจากหน้าจอ `จัดการสถานี` ก่อน แล้วอัปเดต:

```bash
git pull
docker compose up -d --build
docker compose ps
```

หากส่งโฟลเดอร์ด้วย SCP ให้แทนที่เฉพาะไฟล์โปรแกรม แต่เก็บ `.env`, `servers.json`, `tactical.db` และ `static/records/` บนเซิร์ฟเวอร์ไว้ จากนั้นสั่ง `docker compose up -d --build`

## 8. สำรองข้อมูล

ใช้ปุ่ม `BACKUP สำรองข้อมูล` ใน `จัดการสถานี` เพื่อสร้างไฟล์สำรอง และเก็บไฟล์ ZIP ไว้นอกเซิร์ฟเวอร์เป็นประจำ

สำหรับไฟล์หลักที่ควรมีสำเนาเพิ่ม:

- `.env` — เก็บใน password manager หรือที่เก็บความลับที่เข้ารหัสเท่านั้น
- `servers.json` — รายการสถานี
- `tactical.db` — ข้อมูล legacy
- `static/records/` — ไฟล์เสียงหลักฐาน
- Docker volume `postgres-data` — ฐานข้อมูล PostgreSQL

ก่อนกด Restore ให้สำรองชุดปัจจุบันเสมอ เพราะ Restore จะเขียนทับข้อมูลเดิม

## 9. ความปลอดภัยก่อนใช้งานจริง

- เปลี่ยนทุกค่า `CHANGE_ME` ใน `.env`
- จำกัด firewall ให้เปิดเฉพาะพอร์ตที่ใช้จริง
- ใช้ HTTPS ผ่าน Reverse Proxy ก่อนเปิดใช้งานจากอินเทอร์เน็ต
- สร้างบัญชีแยกสำหรับเจ้าหน้าที่แต่ละคน ไม่ใช้บัญชี Admin ร่วมกัน
- สำรองข้อมูลและทดสอบการกู้คืนเป็นระยะ
- อัปเดต Docker image และระบบปฏิบัติการตามรอบบำรุงรักษา
