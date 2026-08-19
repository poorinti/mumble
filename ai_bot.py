import os, ssl, sys, queue, base64, time, threading, io, wave

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
import speech_recognition as sr
import requests
import numpy as np

BOT_NAME = sys.argv[1] if len(sys.argv) > 1 else "[AI-RECON]"
SERVER_ID = sys.argv[2] if len(sys.argv) > 2 else "1"
HOST = sys.argv[3] if len(sys.argv) > 3 else "127.0.0.1"
PORT = int(sys.argv[4]) if len(sys.argv) > 4 else 64738
PASSWORD = sys.argv[5] if len(sys.argv) > 5 else "tactical1234"
TARGET_CHANNEL_ID = int(sys.argv[6]) if len(sys.argv) > 6 else 0 

WEB_API = "http://127.0.0.1:5000/api/ai/transcript"
BOT_API_TOKEN = os.getenv("AI_BOT_TOKEN", "change-ai-bot-token")
BOT_API_HEADERS = {"X-ROIP-Bot-Token": BOT_API_TOKEN}
SILENCE_TIMEOUT = 1.0    
MIN_AUDIO_LENGTH = 0.5   
ENERGY_THRESHOLD = 600   

audio_queue = queue.Queue()

def set_processing_status(username, is_processing):
    try:
        action = 'start' if is_processing else 'end'
        requests.post(
            WEB_API,
            json={"user": username, "action": action, "bot": BOT_NAME, "server_id": SERVER_ID, "channel_id": TARGET_CHANNEL_ID},
            headers=BOT_API_HEADERS,
            timeout=2,
        )
    except: pass

def send_to_dashboard(username, text, b64_audio=None):
    try:
        payload = {"user": username, "text": text, "action": "msg", "bot": BOT_NAME, "server_id": SERVER_ID, "channel_id": TARGET_CHANNEL_ID}
        if b64_audio: payload["audio_b64"] = b64_audio
        requests.post(WEB_API, json=payload, headers=BOT_API_HEADERS, timeout=5)
    except: pass

recognizer = sr.Recognizer()
recognizer.energy_threshold = ENERGY_THRESHOLD

def process_audio(user_name, pcm_data):
    try:
        audio_data = np.frombuffer(pcm_data, dtype=np.int16).astype(np.float32)
        max_vol = np.max(np.abs(audio_data))
        if max_vol > 0: audio_data = (audio_data / max_vol) * 32767.0
        pcm_data = audio_data.astype(np.int16).tobytes()

        wav_io = io.BytesIO()
        with wave.open(wav_io, 'wb') as wav_file:
            wav_file.setnchannels(1); wav_file.setsampwidth(2); wav_file.setframerate(48000)
            wav_file.writeframes(pcm_data)
        wav_io.seek(0)
        
        with sr.AudioFile(wav_io) as source:
            audio = recognizer.record(source)
            try:
                text = recognizer.recognize_google(audio, language="th-TH").strip()
                if len(text) > 0:
                    wav_data_small = audio.get_wav_data(convert_rate=16000)
                    b64_audio = base64.b64encode(wav_data_small).decode('utf-8')
                    send_to_dashboard(user_name, text, b64_audio)
                else: set_processing_status(user_name, False)
            except sr.UnknownValueError:
                set_processing_status(user_name, False)
    except Exception as e: 
        set_processing_status(user_name, False)

def transcription_worker():
    while True:
        user_name, pcm_data = audio_queue.get() 
        set_processing_status(user_name, True)  
        process_audio(user_name, pcm_data)      
        audio_queue.task_done()                 

audio_buffers = {}
last_voice_time = {}

def sound_received_handler(user, sound_chunk):
    try:
        global audio_buffers, last_voice_time
        name = user['name']
        
        # ✨ บล็อกไม่ให้บอท AI แอบฟังกันเอง (แก้ปัญหาแชท AI พิมพ์ซ้ำ)
        if name == BOT_NAME or name.startswith('[AI-'): return 
        
        if name not in audio_buffers: audio_buffers[name] = bytearray()
        audio_buffers[name].extend(sound_chunk.pcm)
        last_voice_time[name] = time.time()
    except: pass

def loop_process_audio():
    global audio_buffers, last_voice_time
    while True:
        try:
            current_time = time.time()
            for name in list(audio_buffers.keys()):
                if current_time - last_voice_time.get(name, 0) > SILENCE_TIMEOUT:
                    data = audio_buffers.pop(name)
                    last_voice_time.pop(name, None)
                    if len(data) / (48000 * 2) > MIN_AUDIO_LENGTH: audio_queue.put((name, data))
        except: pass
        time.sleep(0.5)

threading.Thread(target=transcription_worker, daemon=True).start() 
threading.Thread(target=loop_process_audio, daemon=True).start()   

while True:
    try:
        mumble = pymumble.Mumble(HOST, BOT_NAME, password=PASSWORD, port=PORT)
        mumble.set_receive_sound(True) 
        mumble.start()
        mumble.is_ready() 

        if TARGET_CHANNEL_ID > 0:
            try:
                time.sleep(1.5) 
                if TARGET_CHANNEL_ID in mumble.channels:
                    mumble.channels[TARGET_CHANNEL_ID].move_in()
            except: pass

        mumble.callbacks.set_callback(pymumble.constants.PYMUMBLE_CLBK_SOUNDRECEIVED, sound_received_handler)
        while mumble.is_alive(): time.sleep(1)
    except KeyboardInterrupt: sys.exit()
    except Exception as e: pass
    time.sleep(5)
