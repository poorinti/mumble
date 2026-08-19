# คู่มือติดตั้ง ROIP Command Center ด้วย WinSCP

ใช้สำหรับส่งโปรเจกต์จาก Windows ขึ้น Ubuntu Server ผ่าน WinSCP/SFTP แล้วสั่ง Docker Compose

## ข้อมูลที่ต้องเตรียม

- IP หรือ Domain ของ Server
- Username และ Password หรือ Private Key ของ SSH
- SSH Port ปกติ `22`
- โฟลเดอร์โปรเจกต์ เช่น `C:\Users\PC\Documents\mumbledocker`

## 1. เชื่อมต่อ WinSCP

กรอกค่าใน WinSCP:

| ช่อง | ค่า |
| --- | --- |
| File protocol | `SFTP` |
| Host name | IP หรือ Domain ของ Server |
| Port number | `22` |
| User name | Username ของ Ubuntu |
| Password | Password หรือใช้ Private Key |

กด `Login` และยืนยัน Host key เมื่อเป็น Server ที่ตรวจสอบแล้ว

## 2. ส่งไฟล์ขึ้น Server

ฝั่งซ้ายเปิด:

```text
C:\Users\PC\Documents\mumbledocker
```

ฝั่งขวาเปิด Home ของผู้ใช้ เช่น `/home/ubuntu` สร้างโฟลเดอร์ `roip-command-center` แล้วลากไฟล์ทั้งหมดไปที่:

```text
/home/ubuntu/roip-command-center
```

ห้ามอัปโหลดไฟล์จากเครื่องพัฒนาไปทับ Production:

```text
.env
servers.json
tactical.db
static/records/
```

ให้ส่ง `.env.example` ได้ แต่สร้าง `.env` ใหม่บน Server

## 3. เปิด Terminal จาก WinSCP

เลือก `Commands` → `Open Terminal` แล้วรัน:

```bash
cd ~/roip-command-center
ls
```

ถ้าต้องการเก็บแบบ Production:

```bash
sudo mkdir -p /opt/roip-command-center
sudo cp -a ~/roip-command-center/. /opt/roip-command-center/
sudo chown -R "$USER":"$USER" /opt/roip-command-center
cd /opt/roip-command-center
```

## 4. ตั้งค่า .env

ไฟล์ที่ต้องแก้จริงคือ `.env` ในโฟลเดอร์เดียวกับ `docker-compose.yml` เช่น:

```text
/opt/roip-command-center/.env
```

ห้ามแก้เฉพาะ `.env.example` เพราะไฟล์นั้นเป็นเพียงต้นแบบ

```bash
cp .env.example .env
nano .env
```

เปลี่ยนทุกค่า `CHANGE_ME` โดยเฉพาะ `ADMIN_PASSWORD`, `FLASK_SECRET_KEY`, `POSTGRES_PASSWORD`, `AI_BOT_TOKEN`, `CONTROL_API_TOKEN` และ `MUMBLE_ICE_SECRET`

สร้างค่าสุ่มด้วย:

```bash
openssl rand -hex 32
openssl rand -hex 48
```

## 5. เปิดระบบ

ถ้าเครื่องรองรับ Compose รุ่นใหม่ ใช้คำสั่ง `docker compose` ได้เลย หากขึ้นข้อความว่าไม่รู้จัก `compose` ให้ใช้ `docker-compose` แทน หรือทำตามขั้นตอนติดตั้ง Compose plugin ด้านล่าง

```bash
docker compose up -d --build
docker compose ps
curl http://127.0.0.1:5000/healthz
```

ต้องได้:

```json
{"database":"ok","status":"ok"}
```

เปิดหน้าเว็บที่ `http://SERVER_IP:5000`

ติดตั้ง Compose plugin หากต้องการใช้คำสั่งแบบเว้นวรรค:

```bash
sudo apt update
sudo apt install -y docker-compose-plugin
docker compose version
```

หากระบบใช้แพ็กเกจรุ่นเก่า ให้ใช้รูปแบบมีขีด:

```bash
docker-compose up -d --build
docker-compose ps
curl http://127.0.0.1:5000/healthz
```

## 6. เปิด Firewall

```bash
sudo ufw allow 5000/tcp
sudo ufw allow 64740:64743/tcp
sudo ufw allow 64740:64743/udp
sudo ufw status
```

## 7. อัปเดตครั้งต่อไป

สำรองข้อมูลก่อน แล้วอัปโหลดเฉพาะไฟล์โปรแกรมผ่าน WinSCP ห้ามทับ `.env`, `servers.json`, `tactical.db` และ `static/records/`

```bash
sudo cp -a ~/roip-command-center/. /opt/roip-command-center/
cd /opt/roip-command-center
docker compose up -d --build
docker compose ps
curl http://127.0.0.1:5000/healthz
```

## 8. ตรวจปัญหา

```bash
docker compose logs -f command-center
docker compose logs -f gateway
docker compose logs -f postgres
```

เช็กลิสต์: Container เป็น `healthy`, `/healthz` ได้ `database: ok`, Login ได้, เพิ่มสถานีได้ และทดสอบ Backup แล้ว

