import os, ssl, sys, time, wave
import warnings
warnings.filterwarnings("ignore")

# แพตช์ SSL สำหรับเชื่อมต่อ Mumble
if not hasattr(ssl, 'wrap_socket'):
    def _wrap_socket(sock, keyfile=None, certfile=None, server_side=False, cert_reqs=ssl.CERT_NONE, ssl_version=None, ca_certs=None, do_handshake_on_connect=True, suppress_ragged_eofs=True, ciphers=None):
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT if not server_side else ssl.PROTOCOL_TLS_SERVER)
        context.check_hostname = False; context.verify_mode = ssl.CERT_NONE
        if certfile: context.load_cert_chain(certfile, keyfile)
        if ciphers: context.set_ciphers(ciphers)
        return context.wrap_socket(sock, server_side=server_side, do_handshake_on_connect=do_handshake_on_connect, suppress_ragged_eofs=suppress_ragged_eofs)
    ssl.wrap_socket = _wrap_socket
    if not hasattr(ssl, 'PROTOCOL_TLS'): ssl.PROTOCOL_TLS = ssl.PROTOCOL_TLS_CLIENT
    if not hasattr(ssl, 'PROTOCOL_TLSv1'): ssl.PROTOCOL_TLSv1 = ssl.PROTOCOL_TLS_CLIENT

if hasattr(os, 'add_dll_directory'): os.add_dll_directory(os.path.dirname(os.path.abspath(__file__)))

import pymumble_py3 as pymumble

BOT_NAME = sys.argv[1]
HOST = sys.argv[2]
PORT = int(sys.argv[3])
PASSWORD = sys.argv[4]
TARGET_CHANNEL_ID = int(sys.argv[5])

try:
    # 1. สตาร์ทบอท
    mumble = pymumble.Mumble(HOST, BOT_NAME, password=PASSWORD, port=PORT)
    mumble.start()
    mumble.is_ready()

    # 2. เดินเข้าห้องเป้าหมายไปยืนรอ
    if TARGET_CHANNEL_ID > 0:
        time.sleep(0.5)
        if TARGET_CHANNEL_ID in mumble.channels:
            mumble.channels[TARGET_CHANNEL_ID].move_in()
            time.sleep(0.5)
    
    # 3. วนลูปฟังคำสั่งจากหน้าเว็บอย่างเงียบๆ (ไม่รบกวนเซิร์ฟเวอร์)
    while True:
        line = sys.stdin.readline()
        if not line:
            break # ถ้าแอดมินกดถอนบอท มันจะออกจากลูปนี้แล้วตายไปเอง
        
        wav_file = line.strip()
        if os.path.exists(wav_file):
            try:
                with wave.open(wav_file, 'rb') as f:
                    pcm_data = f.readframes(f.getnframes())
                # ปล่อยเสียงออกไมค์
                mumble.sound_output.add_sound(pcm_data)
            except:
                pass

except Exception as e:
    sys.exit(1)