import urllib.request
import os

# ลิงก์ตรงสำหรับดาวน์โหลดไฟล์ libopus-0.dll (เวอร์ชัน 64-bit ที่เสถียรที่สุด)
url = "https://github.com/Just-Some-Bots/MusicBot/raw/master/libopus-0.x64.dll"

print("กำลังดาวน์โหลดไฟล์ Opus Library...")
try:
    # โหลดไฟล์มาวางและตั้งชื่อให้ครอบคลุมที่ระบบจะเรียกหา
    urllib.request.urlretrieve(url, "libopus-0.dll")
    urllib.request.urlretrieve(url, "opus.dll")
    
    print("✅ ดาวน์โหลดสำเร็จ!")
    print(f"ไฟล์ถูกติดตั้งไว้ที่: {os.getcwd()}")
    print("ตอนนี้คุณสามารถรัน 'python ai_bot.py' ได้เลยครับ 🚀")
except Exception as e:
    print(f"❌ เกิดข้อผิดพลาดในการดาวน์โหลด: {e}")