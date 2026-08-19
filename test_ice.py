import Ice
import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

try:
    import MumbleServer
except ImportError:
    print("❌ นำเข้า MumbleServer ไม่สำเร็จ ตรวจสอบโฟลเดอร์ MumbleServer")
    sys.exit(1)

# ใส่ IP ของเครื่อง Ubuntu ที่รัน Mumble
TARGET_IP = "183.88.215.106" 
TARGET_PORT = "6502"

print(f"กำลังทดสอบทะลวงเกราะ Mumble Server ที่ {TARGET_IP}:{TARGET_PORT} ...")

ic = None
try:
    init_data = Ice.InitializationData()
    init_data.properties = Ice.createProperties()
    ic = Ice.initialize([], init_data)
    
    proxy_string = f"Meta:tcp -h {TARGET_IP} -p {TARGET_PORT} -t 5000"
    base = ic.stringToProxy(proxy_string)
    
    # พยายามเชื่อมต่อแบบเช็คสถานะทันที
    meta = MumbleServer.MetaPrx.checkedCast(base)
    
    if not meta:
        print("❌ เชื่อมต่อสำเร็จ แต่ Proxy ไม่ถูกต้อง")
    else:
        print("\n✅ [SUCCESS] เชื่อมต่อ ZeroC Ice สำเร็จแล้ว!")
        servers = meta.getBootedServers()
        print(f"✅ พบ Virtual Server กำลังรันอยู่: {len(servers)} เซิร์ฟเวอร์")
        for s in servers:
            print(f"   -> Server ID: {s.id()}, ผู้ใช้ออนไลน์: {len(s.getUsers())} คน")

except Ice.ConnectionRefusedException:
    print("\n❌ [ERROR: CONNECTION REFUSED]")
    print("เซิร์ฟเวอร์มีอยู่จริง แต่ปฏิเสธการพูดคุยด้วย! สาเหตุที่เป็นไปได้:")
    print("1. ในไฟล์ murmur.ini ยังเป็น ice=\"tcp -h 127.0.0.1 ...\" (ต้องแก้ 127.0.0.1 เป็น 0.0.0.0)")
    print("2. ลืม Restart Mumble หลังจากแก้ murmur.ini")
except Ice.TimeoutException:
    print("\n❌ [ERROR: TIMEOUT]")
    print("หาทางไปไม่เจอ หรือโดนกำแพงกันไว้! สาเหตุที่เป็นไปได้:")
    print("1. ลืมเปิดพอร์ตบน Ubuntu รันคำสั่ง: sudo ufw allow 6502/tcp")
    print("2. ใส่ IP ผิด หรือเครื่องคอมพิวเตอร์ของคุณกับ Ubuntu ไม่ได้อยู่ในวงแลนเดียวกัน")
except Exception as e:
    print(f"\n❌ [ERROR อื่นๆ]: {e}")
finally:
    if ic:
        ic.destroy()