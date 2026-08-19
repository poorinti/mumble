from flask import Flask, render_template, jsonify, request, send_file, session
from markupsafe import escape
import json, os, subprocess, sys, atexit, re, sqlite3, io, threading, time, random, string, base64, tempfile
import pandas as pd
import zipfile
import hmac
import requests as http_requests
from datetime import datetime, timezone
from dotenv import load_dotenv
from mumble_controller import (get_server_status, kick_user, broadcast_message,
                               create_channel, set_server_password, set_user_mute,
                               move_user, remove_channel, ban_user, mute_all_in_channel,
                               restart_server, get_ban_list, unban_user, set_user_deaf,
                               send_message_to_user, rename_channel, set_channel_description,
                               set_welcome_text, set_max_users, rename_user,
                               set_channel_password, set_channel_max_users,
                               get_mumble_logs, register_user, get_registered_users, unregister_user)

load_dotenv()

from roip_auth import (
    authenticate_user,
    audit_user_action,
    count_active_admins,
    create_user,
    delete_user,
    initialize_auth_tables,
    list_users,
    replace_user_room_permissions,
    update_user,
)

CONTROL_SERVICE_URL = os.getenv('CONTROL_SERVICE_URL', 'http://control-service:5100').rstrip('/')
CONTROL_API_TOKEN = os.getenv('CONTROL_API_TOKEN', 'change-control-token')

def _control_request(path, payload=None, timeout=45):
    response = http_requests.post(
        f"{CONTROL_SERVICE_URL}{path}",
        json=payload or {},
        headers={"Authorization": f"Bearer {CONTROL_API_TOKEN}"},
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()

# ✨ [SYSTEM] ตรวจสอบสภาพแวดล้อม (Auto-Environment Detection)
IS_DOCKER = os.path.exists('/.dockerenv')
if IS_DOCKER:
    print("🌐 Environment: SERVER (Inside Docker)")
else:
    print("💻 Environment: LOCAL (Windows/Desktop)")
    
app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 3600
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.getenv('SESSION_COOKIE_SECURE', 'false').lower() == 'true'
app.config['PERMANENT_SESSION_LIFETIME'] = 60 * 60 * 12

_sk_file = '.secret_key'
if os.path.exists(_sk_file):
    with open(_sk_file,'r') as _f: app.secret_key = _f.read().strip()
else:
    import secrets
    app.secret_key = secrets.token_hex(32)
    with open(_sk_file,'w') as _f: _f.write(app.secret_key)

app.secret_key = os.getenv('FLASK_SECRET_KEY', app.secret_key)
AI_BOT_TOKEN = os.getenv('AI_BOT_TOKEN', 'change-ai-bot-token')

os.makedirs(os.path.join('static', 'records'), exist_ok=True)

@app.before_request
def require_auth():
    allowed_paths = ['/', '/api/login', '/api/auth/login', '/api/session/check', '/healthz']
    if request.path == '/api/ai/transcript' and request.method == 'POST':
        supplied = request.headers.get('X-ROIP-Bot-Token', '')
        if not hmac.compare_digest(supplied, AI_BOT_TOKEN):
            return jsonify({"status": "failed", "error": "Invalid bot token"}), 401
        return None
    if request.path.startswith('/api/') and request.path not in allowed_paths:
        if not session.get('logged_in') or session.get('role') not in ('admin', 'user'):
            return jsonify({"status": "failed", "error": "Unauthorized Access (ACCESS DENIED)"}), 401

        path = request.path
        admin_only = (
            path.startswith('/api/admin/')
            or path.startswith('/api/fleet/')
            or (path == '/api/servers' and request.method == 'POST')
            or (path.startswith('/api/server/') and request.method == 'DELETE')
            or (path.startswith('/api/server/') and path.endswith('/channel') and request.method == 'POST')
            or (path.startswith('/api/server/') and '/channel/' in path and request.method == 'DELETE')
        )
        if admin_only and session.get('role') != 'admin':
            return jsonify({"status": "failed", "error": "ต้องใช้สิทธิ์ Admin สำหรับการสร้างหรือลบห้อง/จัดการระบบ"}), 403

@app.after_request
def add_charset(response):
    if response.content_type.startswith('text/html'):
        response.content_type = 'text/html; charset=utf-8'
    return response

DATA_FILE = 'servers.json'
DB_FILE = 'tactical.db'

def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute('PRAGMA journal_mode=WAL;') 
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, server_id INTEGER, time TEXT, message TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS ai_transcripts (id INTEGER PRIMARY KEY AUTOINCREMENT, server_id INTEGER, time TEXT, bot TEXT, user TEXT, message TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS keywords (id INTEGER PRIMARY KEY AUTOINCREMENT, word TEXT UNIQUE)''')
    c.execute('''CREATE TABLE IF NOT EXISTS keyword_alerts (id INTEGER PRIMARY KEY AUTOINCREMENT, server_id INTEGER, time TEXT, bot TEXT, user TEXT, message TEXT, keyword TEXT, audio_file TEXT)''')
    try: c.execute("ALTER TABLE keyword_alerts ADD COLUMN audio_file TEXT")
    except: pass 
    c.execute('SELECT count(*) FROM keywords')
    if c.fetchone()[0] == 0:
        for w in ['ฉุกเฉิน', 'ขอกำลังเสริม', 'ศัตรู', 'ปะทะ', 'บาดเจ็บ', 'ต้องการความช่วยเหลือ', 'ว.8']:
            c.execute('INSERT OR IGNORE INTO keywords (word) VALUES (?)', (w,))
    conn.commit(); conn.close()

init_db()

from roip_search import register_chat_search
from roip_search.db import database_health, ingest_chat_message, sync_stations

register_chat_search(app)
initialize_auth_tables()

@app.route('/healthz')
def healthz():
    if database_health():
        return jsonify({"status": "ok", "database": "ok"})
    return jsonify({"status": "degraded", "database": "unavailable"}), 503

server_user_snapshots = {}  

def monitor_users_silent():
    global server_user_snapshots
    time.sleep(5)  
    while True:
        try:
            servers = load_servers()
            for s in servers:
                sid = str(s['id'])
                try:
                    status = get_server_status(s['ip'], _ice_port(s), _ice_secret(s))
                    if not status['online']:
                        server_user_snapshots.pop(sid, None)
                        continue
                    current = {u['name'] for u in status.get('users', [])}
                    prev = server_user_snapshots.get(sid, None)
                    if prev is not None:
                        joined = current - prev
                        left = prev - current
                        for name in joined:
                            _log_db(s['id'], f"🟢 [{name}] เข้าร่วมเซิร์ฟเวอร์")
                        for name in left:
                            _log_db(s['id'], f"🔴 [{name}] ออกจากเซิร์ฟเวอร์")
                    server_user_snapshots[sid] = current
                except: pass
        except: pass
        time.sleep(15)

threading.Thread(target=monitor_users_silent, daemon=True).start()

ai_transcriptions = []
current_processing = []
active_ai_bots = [] 
active_tts_bots = [] 

def cleanup_bots():
    for b in active_ai_bots:
        try: b['proc'].terminate()
        except: pass
    for b in active_tts_bots:
        try: b['proc'].terminate()
        except: pass
atexit.register(cleanup_bots)

def load_servers():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f: return json.load(f)
    return []

def save_servers(servers):
    with open(DATA_FILE, 'w', encoding='utf-8') as f: json.dump(servers, f, indent=4, ensure_ascii=False)

def get_user_color(username):
    colors = ['#4ade80','#0ea5e9','#f43f5e','#a855f7','#eab308','#ec4899','#14b8a6','#f97316','#2dd4bf','#fb923c']
    return colors[sum(ord(c) for c in username) % len(colors)]

def _ice_port(server): return server.get('ice_port', 6502)
def _ice_secret(server): return server.get('ice_secret', 'tactical1234')

def _log_db(server_id, message):
    conn = sqlite3.connect(DB_FILE)
    conn.execute("INSERT INTO logs (server_id, time, message) VALUES (?, ?, ?)",
                 (server_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), message))
    conn.commit(); conn.close()

@app.route('/')
@app.route('/legacy')
def index(): return render_template('index.html')

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json(silent=True) or {}
    user = authenticate_user(data.get('username'), data.get('password'))
    if not user:
        return jsonify({"status": "failed", "error": "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง"}), 401
    session.clear()
    session.permanent = True
    session['logged_in'] = True
    session['user_id'] = user['id']
    session['username'] = user['username']
    session['role'] = user['role']
    session['operator_id'] = user['username']
    return jsonify({"status": "success", "user": user})

@app.route('/api/logout', methods=['POST'])
def api_logout():
    session.clear()
    return jsonify({"status": "success"})

def get_all_keywords():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT id, word FROM keywords")
    rows = cur.fetchall()
    conn.close()
    return [{"id": r[0], "word": r[1]} for r in rows]

@app.route('/api/keywords', methods=['GET'])
def api_get_keywords(): return jsonify(get_all_keywords())

@app.route('/api/keywords', methods=['POST'])
def api_add_keyword():
    word = request.json.get('word', '').strip()
    if word:
        try:
            conn = sqlite3.connect(DB_FILE)
            conn.execute("INSERT INTO keywords (word) VALUES (?)", (word,))
            conn.commit(); conn.close()
            return jsonify({"status": "success"})
        except: return jsonify({"status": "failed", "error": "มีคำนี้อยู่แล้ว"}), 400
    return jsonify({"status": "failed"}), 400

@app.route('/api/keywords/<int:kid>', methods=['DELETE'])
def api_del_keyword(kid):
    conn = sqlite3.connect(DB_FILE)
    conn.execute("DELETE FROM keywords WHERE id=?", (kid,))
    conn.commit(); conn.close()
    return jsonify({"status": "success"})

@app.route('/api/alerts', methods=['GET'])
def api_get_alerts():
    search = request.args.get('search', '')
    conn = sqlite3.connect(DB_FILE)
    query = "SELECT id, server_id, time, bot, user, message, keyword, audio_file FROM keyword_alerts"
    params = []
    if search:
        query += " WHERE message LIKE ? OR user LIKE ? OR keyword LIKE ?"
        params = [f"%{search}%", f"%{search}%", f"%{search}%"]
    query += " ORDER BY id DESC LIMIT 200"
    cur = conn.cursor()
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    
    servers = {str(s['id']): s['name'] for s in load_servers()}
    alerts = []
    for r in rows:
        alerts.append({
            "id": r[0], "server_name": servers.get(str(r[1]), f"Server {r[1]}"), "time": r[2], 
            "bot": r[3], "user": r[4], "message": r[5], "keyword": r[6], "audio_file": r[7]
        })
    return jsonify(alerts)

@app.route('/api/alerts/clear_audio', methods=['POST'])
def api_clear_alert_audio():
    record_dir = os.path.join('static', 'records')
    for f in os.listdir(record_dir):
        if f.startswith('record_') and f.endswith('.wav'):
            try: os.remove(os.path.join(record_dir, f))
            except: pass
    conn = sqlite3.connect(DB_FILE)
    conn.execute("UPDATE keyword_alerts SET audio_file = NULL")
    conn.commit(); conn.close()
    return jsonify({"status": "success"})

@app.route('/api/alerts/clear_all', methods=['POST'])
def api_clear_all_alerts():
    record_dir = os.path.join('static', 'records')
    for f in os.listdir(record_dir):
        if f.startswith('record_') and f.endswith('.wav'):
            try: os.remove(os.path.join(record_dir, f))
            except: pass
    conn = sqlite3.connect(DB_FILE)
    conn.execute("DELETE FROM keyword_alerts")
    conn.commit(); conn.close()
    return jsonify({"status": "success"})

@app.route('/api/log/<int:server_id>', methods=['POST'])
def api_save_log(server_id):
    msg = request.json.get('message', '')
    _log_db(server_id, msg)
    return jsonify({"status": "success"})

@app.route('/api/logs/<int:server_id>', methods=['GET'])
def api_get_logs(server_id):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT time, message FROM logs WHERE server_id=? ORDER BY id DESC LIMIT 50", (server_id,))
    rows = cur.fetchall()
    conn.close()
    return jsonify([{"time": r[0], "message": r[1]} for r in rows[::-1]]) 

@app.route('/api/export/<doc_type>/<int:server_id>')
def export_excel(doc_type, server_id):
    start_date = request.args.get('start', '')
    end_date = request.args.get('end', '')
    conn = sqlite3.connect(DB_FILE)
    if doc_type == 'logs':
        query = f"SELECT time AS 'วันที่/เวลา', message AS 'รายละเอียดเหตุการณ์' FROM logs WHERE server_id={server_id}"
        filename = f"Command_Logs_Server_{server_id}.xlsx"
    elif doc_type == 'user_logs': 
        query = f"SELECT time AS 'วันที่/เวลา', message AS 'รายละเอียดเหตุการณ์' FROM logs WHERE server_id={server_id} AND (message LIKE '%เข้าร่วม%' OR message LIKE '%ออกจาก%')"
        filename = f"User_Activity_Server_{server_id}.xlsx"
    elif doc_type == 'alerts':
        query = f"SELECT time AS 'วันที่/เวลา', keyword AS 'คำที่ตรวจพบ', user AS 'เป้าหมาย', message AS 'ข้อความเต็ม', bot AS 'บอทผู้ตรวจจับ' FROM keyword_alerts WHERE server_id={server_id}"
        filename = f"Keyword_Alerts_Server_{server_id}.xlsx"
    else:
        query = f"SELECT time AS 'วันที่/เวลา', bot AS 'ชื่อบอท', user AS 'เป้าหมาย', message AS 'ข้อความเสียง' FROM ai_transcripts WHERE server_id={server_id}"
        filename = f"AI_Transcripts_Server_{server_id}.xlsx"
    params = []
    if start_date:
        query += " AND time >= ?"
        params.append(start_date + " 00:00:00")
    if end_date:
        query += " AND time <= ?"
        params.append(end_date + " 23:59:59")
    query += " ORDER BY time DESC"
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Report')
    output.seek(0)
    return send_file(output, download_name=filename, as_attachment=True)

@app.route('/api/stats')
def api_stats():
    servers = load_servers()
    total_users = 0; total_channels = 0; online_servers = 0
    for s in servers:
        try:
            st = get_server_status(s['ip'], _ice_port(s), _ice_secret(s))
            if st['online']:
                online_servers += 1
                total_users += len(st.get('users', []))
                total_channels += len(st.get('channels', []))
        except: pass
    active_bots = len([b for b in active_ai_bots if isinstance(b, dict) and b.get('proc') and b['proc'].poll() is None])
    return jsonify({
        "online_servers": online_servers, "total_servers": len(servers),
        "total_users": total_users, "total_channels": total_channels,
        "active_bots": active_bots
    })

@app.route('/api/ai/bot/start/<int:server_id>', methods=['POST'])
def api_start_bot(server_id):
    global active_ai_bots
    target = next((s for s in load_servers() if s['id'] == server_id), None)
    if not target: return jsonify({"error": "server not found"}), 400
    
    data = request.json or {}
    mode = data.get('mode', 'single')
    channel_id = data.get('channel_id', 0)
    active_ai_bots = [b for b in active_ai_bots if b['proc'].poll() is None]

    if mode == 'all':
        try:
            status = get_server_status(target['ip'], _ice_port(target), _ice_secret(target))
            channels_to_join = list(set([0] + [c['id'] for c in status.get('channels', [])]))
        except: channels_to_join = [0]
        
        for ch_id in channels_to_join:
            rs = ''.join(random.choices(string.ascii_uppercase + string.digits, k=3))
            b_name = f"[AI-R-{rs}]"
            proc = subprocess.Popen([sys.executable, 'ai_bot.py', b_name, str(server_id), target['ip'], str(target.get('port', 64738)), target.get('password', 'tactical1234'), str(ch_id)])
            active_ai_bots.append({"name": b_name, "proc": proc, "server_id": server_id})
            time.sleep(0.5)
    else:
        rs = ''.join(random.choices(string.ascii_uppercase + string.digits, k=3))
        b_name = f"[AI-R-{rs}]"
        proc = subprocess.Popen([sys.executable, 'ai_bot.py', b_name, str(server_id), target['ip'], str(target.get('port', 64738)), target.get('password', 'tactical1234'), str(channel_id)])
        active_ai_bots.append({"name": b_name, "proc": proc, "server_id": server_id})
    return jsonify({"status": "success", "count": len(active_ai_bots)})

@app.route('/api/ai/bot/kill/<int:server_id>', methods=['POST'])
def api_kill_bot(server_id):
    global active_ai_bots
    bot_name = request.json.get('name')
    target = next((s for s in load_servers() if s['id'] == server_id), None)
    if target:
        try:
            status = get_server_status(target['ip'], _ice_port(target), _ice_secret(target))
            for u in status.get('users', []):
                if u['name'] == bot_name:
                    kick_user(target['ip'], u['session'], _ice_port(target), _ice_secret(target))
        except: pass
    for b in active_ai_bots:
        if b['name'] == bot_name:
            try: b['proc'].terminate()
            except: pass
    active_ai_bots = [b for b in active_ai_bots if b['name'] != bot_name and b['proc'].poll() is None]
    return jsonify({"status": "success"})

@app.route('/api/ai/bot/stop', methods=['POST'])
@app.route('/api/ai/bot/stop/<int:server_id>', methods=['POST'])
def api_stop_bot(server_id=None):
    global active_ai_bots
    selected = [b for b in active_ai_bots if server_id is None or b.get('server_id') == server_id]
    for bot in selected:
        try: bot['proc'].terminate()
        except: pass
    active_ai_bots = [b for b in active_ai_bots if b not in selected and b['proc'].poll() is None]
    if server_id is None:
        ai_transcriptions.clear(); current_processing.clear()
    else:
        ai_transcriptions[:] = [m for m in ai_transcriptions if m.get('server_id') != str(server_id)]
        current_processing[:] = [p for p in current_processing if p.get('server_id') != str(server_id)]
    return jsonify({"status": "success", "count": len(active_ai_bots)})

@app.route('/api/ai/bot/status', methods=['GET'])
def api_bot_status():
    global active_ai_bots
    active_ai_bots = [b for b in active_ai_bots if b['proc'].poll() is None]
    return jsonify({"count": len(active_ai_bots)})

@app.route('/api/ai/clear', methods=['POST'])
@app.route('/api/ai/clear/<int:server_id>', methods=['POST'])
def api_clear_ai(server_id=None):
    global ai_transcriptions, current_processing
    if server_id is None:
        ai_transcriptions.clear(); current_processing.clear()
    else:
        ai_transcriptions[:] = [m for m in ai_transcriptions if m.get('server_id') != str(server_id)]
        current_processing[:] = [p for p in current_processing if p.get('server_id') != str(server_id)]
    return jsonify({"status": "success"})

@app.route('/api/ai/transcript', methods=['GET', 'POST'])
def api_transcript():
    global ai_transcriptions, current_processing
    if request.method == 'POST':
        data = request.json
        action = data.get('action', 'msg'); user = data.get('user', 'Unknown'); server_id = data.get('server_id', "1")
        raw_bot = data.get('bot', '[AI]'); audio_b64 = data.get('audio_b64')
        channel_id = data.get('channel_id')
        confidence = data.get('confidence')
        match = re.search(r'\[AI-R-(.*?)\]', raw_bot)
        short_bot = f"R-{match.group(1)}" if match else "AI"
        
        proc_obj = {"user": user, "bot": short_bot, "server_id": server_id}
        if action == 'start':
            if proc_obj not in current_processing: current_processing.append(proc_obj)
        elif action == 'end':
            current_processing = [p for p in current_processing if not (p['user'] == user and p['bot'] == short_bot)]
        else:
            current_processing = [p for p in current_processing if not (p['user'] == user and p['bot'] == short_bot)]
            text = data.get('text', '')
            time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            time_display = datetime.now().strftime("%H:%M:%S")
            occurred_at = datetime.now(timezone.utc)
            
            all_kws = [k['word'] for k in get_all_keywords()]
            found_kws = [kw for kw in all_kws if kw in text]
            audio_filename = None
            if found_kws:
                if audio_b64:
                    audio_filename = f"record_{server_id}_{int(time.time())}_{random.randint(1000,9999)}.wav"
                    filepath = os.path.join('static', 'records', audio_filename)
                    try:
                        with open(filepath, 'wb') as f:
                            f.write(base64.b64decode(audio_b64))
                    except: audio_filename = None

                conn = sqlite3.connect(DB_FILE)
                for kw in found_kws:
                    conn.execute("INSERT INTO keyword_alerts (server_id, time, bot, user, message, keyword, audio_file) VALUES (?, ?, ?, ?, ?, ?, ?)", 
                                 (server_id, time_str, raw_bot, user, text, kw, audio_filename))
                conn.commit(); conn.close()
                
            if found_kws:
                keyword_pattern = re.compile(
                    "(" + "|".join(re.escape(kw) for kw in sorted(found_kws, key=len, reverse=True)) + ")"
                )
                keyword_set = set(found_kws)
                highlighted_text = "".join(
                    (
                        "<span style='color:#ff8a8a; font-weight:bold; background:rgba(229,57,53,0.3); "
                        "padding:0 3px; border-radius:3px; border:1px solid rgba(229,57,53,0.5);'>"
                        f"{escape(part)}</span>"
                    ) if part in keyword_set else str(escape(part))
                    for part in keyword_pattern.split(text)
                )
            else:
                highlighted_text = str(escape(text))

            user_color = get_user_color(user)
            conn = sqlite3.connect(DB_FILE)
            cur = conn.execute("INSERT INTO ai_transcripts (server_id, time, bot, user, message) VALUES (?, ?, ?, ?, ?)", (server_id, time_str, raw_bot, user, text))
            legacy_id = cur.lastrowid
            conn.commit(); conn.close()

            try:
                ingest_chat_message(
                    source_event_id=f"legacy-ai:{legacy_id}",
                    station_id=int(server_id),
                    occurred_at=occurred_at,
                    speaker_name=user,
                    content=text,
                    bot_name=raw_bot,
                    channel_id=channel_id,
                    confidence=float(confidence) if confidence not in (None, '') else None,
                    audio_filename=audio_filename,
                    keywords=found_kws,
                    metadata={"ingest_source": "ai_bot"},
                )
            except Exception as e:
                print(f"[chat-search] PostgreSQL ingest failed; legacy SQLite retained: {e}")
            
            bot_badge = f"<span style='background:rgba(255,255,255,0.1); border:1px solid rgba(255,255,255,0.2); padding:1px 4px; border-radius:3px; font-size:0.7em; color:var(--text-muted); margin-right:5px;'>{escape(short_bot)}</span>"
            formatted_msg = f"<div style='margin-bottom:4px; line-height:1.4;'><span style='color:var(--text-muted); font-size:0.85em; margin-right:5px;'>[{time_display}]</span>{bot_badge}<strong style='color:{user_color};'>[{escape(user)}]:</strong> <span style='color:var(--text-main);'>{highlighted_text}</span></div>"
            ai_transcriptions.append({"server_id": str(server_id), "html": formatted_msg})
            if len(ai_transcriptions) > 150: ai_transcriptions.pop(0)
        return jsonify({"status": "success"})
    
    server_id = request.args.get('server_id', "1")
    return jsonify({"messages": [m['html'] for m in ai_transcriptions if m['server_id'] == str(server_id)],
                    "processing": [p for p in current_processing if p['server_id'] == str(server_id)]})

@app.route('/api/servers', methods=['GET', 'POST'])
def api_servers():
    servers = load_servers()
    if request.method == 'POST':
        data = request.json
        if data.get('id'):
            for s in servers:
                if s['id'] == data['id']: s.update(data); break
        else:
            data['id'] = 1 if not servers else servers[-1]['id'] + 1
            servers.append(data)
        save_servers(servers)
        try:
            sync_stations()
        except Exception as exc:
            print(f"[chat-search] Station sync deferred: {exc}")
        return jsonify({"status": "success"})
    return jsonify(servers)

@app.route('/api/server/<int:id>', methods=['DELETE'])
def api_delete_server(id):
    return delete_docker_server(id)

@app.route('/api/server/<int:server_id>', methods=['GET'])
def api_get_server_detail(server_id):
    target = next((s for s in load_servers() if s['id'] == server_id), None)
    if not target: return jsonify({"error": "Not found"}), 404
    return jsonify({"server": target, "status": get_server_status(target['ip'], _ice_port(target), _ice_secret(target))})

@app.route('/api/server/<int:server_id>/autobots', methods=['POST'])
def api_set_autobots(server_id):
    mode = request.json.get('mode', 'off')
    channels = request.json.get('channels', [])
    servers = load_servers()
    for s in servers:
        if s['id'] == server_id: 
            s['autobot_config'] = {'mode': mode, 'channels': channels}
            break
    save_servers(servers)
    return jsonify({"status": "success"})

@app.route('/api/server/<int:server_id>/broadcast', methods=['POST'])
def api_broadcast(server_id):
    target = next((s for s in load_servers() if s['id'] == server_id), None)
    if not target: return jsonify({"status": "failed"}), 404
    data = request.json
    msg = data.get('message', '')
    channel_id = data.get('channel_id', 'all')
    ch_id = 0 if channel_id == 'all' else int(channel_id)
    tree = True if channel_id == 'all' else False
    if broadcast_message(target['ip'], msg, ch_id, tree, _ice_port(target), _ice_secret(target)):
        return jsonify({"status": "success"})
    return jsonify({"status": "failed"}), 500

@app.route('/api/server/<int:server_id>/tts_bot/start', methods=['POST'])
def api_start_tts_bot(server_id):
    global active_tts_bots
    target = next((s for s in load_servers() if s['id'] == server_id), None)
    if not target: return jsonify({"status": "failed", "error": "Server not found"}), 404

    channel_id = request.json.get('channel_id', 'all')
    for b in active_tts_bots[:]:
        if b['server_id'] == server_id:
            try: b['proc'].terminate()
            except: pass
            active_tts_bots.remove(b)

    channels_to_join = []
    if channel_id == 'all':
        try:
            status = get_server_status(target['ip'], _ice_port(target), _ice_secret(target))
            channels_to_join = list(set([0] + [c['id'] for c in status.get('channels', [])]))
        except:
            channels_to_join = [0]
    else:
        channels_to_join = [int(channel_id)]
    
    for ch in channels_to_join:
        bot_name = f"[AI-SPK-{random.randint(10,99)}]"
        proc = subprocess.Popen(
            [sys.executable, 'tts_bot.py', bot_name, target['ip'], str(target.get('port', 64738)), target.get('password', 'tactical1234'), str(ch)],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, text=True
        )
        active_tts_bots.append({'proc': proc, 'server_id': server_id, 'channel_id': ch})
        time.sleep(0.2)
        
    return jsonify({"status": "success", "count": len(active_tts_bots)})

@app.route('/api/server/<int:server_id>/tts_bot/stop', methods=['POST'])
def api_stop_tts_bot(server_id):
    global active_tts_bots
    for b in active_tts_bots[:]:
        if b['server_id'] == server_id:
            try: b['proc'].terminate()
            except: pass
            active_tts_bots.remove(b)
    return jsonify({"status": "success"})

@app.route('/api/server/<int:server_id>/tts_broadcast', methods=['POST'])
def api_tts_broadcast(server_id):
    global active_tts_bots
    target = next((s for s in load_servers() if s['id'] == server_id), None)
    if not target: return jsonify({"status": "failed", "error": "Server not found"}), 404
    text = request.json.get('message', '')
    channel_id = request.json.get('channel_id', 'all')
    if not text: return jsonify({"status": "failed", "error": "No text provided"}), 400
    
    bots_to_send = []
    for b in active_tts_bots:
        if b['server_id'] == server_id:
            if channel_id == 'all' or str(b['channel_id']) == str(channel_id):
                bots_to_send.append(b)
                
    if not bots_to_send:
        return jsonify({"status": "failed", "error": "ไม่ได้วางบอทลำโพง! โปรดกด 'วางบอท' เพื่อแสตนด์บายก่อนส่งเสียงครับ"}), 400

    def background_tts_task(srv_id, txt, ch_id, bots):
        try:
            timestamp = int(time.time() * 1000)
            mp3_path = os.path.join('static', 'records', f"tts_{srv_id}_{timestamp}.mp3")
            wav_path = os.path.join('static', 'records', f"tts_{srv_id}_{timestamp}.wav")
            
            subprocess.run(['edge-tts', '--voice', 'th-TH-NiwatNeural', '--text', txt, '--write-media', mp3_path], check=True)
            subprocess.run(['ffmpeg', '-y', '-i', mp3_path, '-ar', '48000', '-ac', '1', '-acodec', 'pcm_s16le', wav_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if os.path.exists(mp3_path): os.remove(mp3_path) 
            
            for b in bots:
                try: b['proc'].stdin.write(f"{os.path.abspath(wav_path)}\n"); b['proc'].stdin.flush()
                except: pass
            _log_db(srv_id, f"📢 [AI โทรโข่ง] สั่งการ: '{txt}' (เป้าหมาย: {ch_id})")
        except Exception as e: print("TTS Error:", e)

    threading.Thread(target=background_tts_task, args=(server_id, text, channel_id, bots_to_send), daemon=True).start()
    return jsonify({"status": "success"})

@app.route('/api/tts/clear_files', methods=['POST'])
def api_clear_tts_files():
    record_dir = os.path.join('static', 'records')
    if os.path.exists(record_dir):
        for f in os.listdir(record_dir):
            if f.startswith('tts_') and f.endswith('.wav'):
                try: os.remove(os.path.join(record_dir, f))
                except: pass
    return jsonify({"status": "success"})

@app.route('/api/web-mic/upload', methods=['POST'])
def api_web_mic_upload():
    if 'audio' not in request.files: return jsonify({"status": "error", "message": "No audio file"}), 400
    server_id = request.form.get('server_id')
    audio_file = request.files['audio']
    temp_path = os.path.join('static', 'records', f"mic_live_{int(time.time())}.webm")
    wav_path = temp_path.replace('.webm', '.wav')
    audio_file.save(temp_path)

    try:
        subprocess.run(['ffmpeg', '-y', '-i', temp_path, '-ar', '48000', '-ac', '1', '-acodec', 'pcm_s16le', wav_path], 
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        target_bots = [b for b in active_tts_bots if str(b['server_id']) == str(server_id)]
        if not target_bots: return jsonify({"status": "error", "message": "ไม่ได้วางบอทลำโพง โปรดกด 'วางบอท' ก่อนใช้ไมค์!"}), 400
        for b in target_bots:
            try: b['proc'].stdin.write(f"{os.path.abspath(wav_path)}\n"); b['proc'].stdin.flush()
            except: pass
        if os.path.exists(temp_path): os.remove(temp_path)
        _log_db(server_id, "🎙️ [LIVE PTT] ผบ. ส่งข้อความเสียงสดผ่านหน้าเว็บ")
        return jsonify({"status": "success"})
    except Exception as e: return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/maintenance/backup')
def api_backup():
    backup_filename = f"ROIP_BACKUP_{datetime.now().strftime('%Y%m%d_%H%M')}.zip"
    archive = io.BytesIO()
    with tempfile.TemporaryDirectory(prefix='roip-backup-') as temp_dir:
        sqlite_snapshot = os.path.join(temp_dir, 'tactical.db')
        if os.path.exists(DB_FILE):
            source = sqlite3.connect(DB_FILE)
            target = sqlite3.connect(sqlite_snapshot)
            try:
                source.backup(target)
            finally:
                target.close()
                source.close()
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as z:
            if os.path.exists(sqlite_snapshot): z.write(sqlite_snapshot, 'tactical.db')
            if os.path.exists(DATA_FILE): z.write(DATA_FILE, 'servers.json')
            if os.path.exists('.env'): z.write('.env', '.env')
    archive.seek(0)
    return send_file(archive, as_attachment=True, download_name=backup_filename, mimetype='application/zip')

@app.route('/api/maintenance/restore', methods=['POST'])
def api_restore():
    if 'file' not in request.files: return jsonify({"status": "error", "message": "No file uploaded"}), 400
    file = request.files['file']
    if request.content_length and request.content_length > 200 * 1024 * 1024:
        return jsonify({"status": "error", "message": "ไฟล์สำรองใหญ่เกิน 200 MB"}), 413
    temp_handle = tempfile.NamedTemporaryFile(prefix='roip-restore-', suffix='.zip', delete=False)
    temp_zip = temp_handle.name
    temp_handle.close()
    file.save(temp_zip)
    try:
        allowed = {'tactical.db', 'servers.json', '.env'}
        payloads = {}
        with zipfile.ZipFile(temp_zip, 'r') as z:
            files = [entry for entry in z.infolist() if not entry.is_dir()]
            if not files or any(entry.filename.replace('\\', '/') not in allowed for entry in files):
                raise ValueError('ไฟล์สำรองมีรายการที่ระบบไม่อนุญาต')
            if sum(entry.file_size for entry in files) > 200 * 1024 * 1024:
                raise ValueError('ข้อมูลภายในไฟล์สำรองใหญ่เกิน 200 MB')
            payloads = {entry.filename.replace('\\', '/'): z.read(entry) for entry in files}

        if 'servers.json' in payloads:
            server_data = json.loads(payloads['servers.json'].decode('utf-8'))
            if not isinstance(server_data, list):
                raise ValueError('servers.json ในไฟล์สำรองไม่ถูกต้อง')

        if 'tactical.db' in payloads:
            with tempfile.NamedTemporaryFile(prefix='roip-sqlite-check-', suffix='.db', delete=False) as db_check:
                db_check.write(payloads['tactical.db'])
                db_check_path = db_check.name
            try:
                check_conn = sqlite3.connect(db_check_path)
                integrity = check_conn.execute('PRAGMA integrity_check').fetchone()[0]
                check_conn.close()
                if integrity != 'ok':
                    raise ValueError('ฐานข้อมูล SQLite ในไฟล์สำรองเสียหาย')
            finally:
                if os.path.exists(db_check_path): os.remove(db_check_path)

        for target_name, content in payloads.items():
            with tempfile.NamedTemporaryFile(prefix='.roip-restore-', dir='.', delete=False) as staged:
                staged.write(content)
                staged_path = staged.name
            os.replace(staged_path, target_name)
        return jsonify({"status": "success", "message": "กู้คืนไฟล์แล้ว กรุณารีสตาร์ต command-center เพื่อโหลดข้อมูลใหม่"})
    except (ValueError, json.JSONDecodeError, zipfile.BadZipFile) as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        if os.path.exists(temp_zip): os.remove(temp_zip)

@app.route('/api/server/<int:server_id>/kick/<int:session>', methods=['POST'])
def api_kick(server_id, session):
    target = next((s for s in load_servers() if s['id'] == server_id), None)
    if target and kick_user(target['ip'], session, _ice_port(target), _ice_secret(target)): return jsonify({"status": "success"})
    return jsonify({"status": "failed"}), 500

@app.route('/api/server/<int:server_id>/ban/<int:session>', methods=['POST'])
def api_ban(server_id, session):
    target = next((s for s in load_servers() if s['id'] == server_id), None)
    if target and ban_user(target['ip'], session, _ice_port(target), _ice_secret(target)): return jsonify({"status": "success"})
    return jsonify({"status": "failed"}), 500

@app.route('/api/server/<int:server_id>/bans', methods=['GET'])
def api_get_bans(server_id):
    target = next((s for s in load_servers() if s['id'] == server_id), None)
    if not target: return jsonify({"error": "Not found"}), 404
    return jsonify({"bans": get_ban_list(target['ip'], _ice_port(target), _ice_secret(target))})

@app.route('/api/server/<int:server_id>/unban/<int:index>', methods=['POST'])
def api_unban(server_id, index):
    target = next((s for s in load_servers() if s['id'] == server_id), None)
    if target and unban_user(target['ip'], index, _ice_port(target), _ice_secret(target)): return jsonify({"status": "success"})
    return jsonify({"status": "failed"}), 500

@app.route('/api/server/<int:server_id>/deaf/<int:session>', methods=['POST'])
def api_deaf(server_id, session):
    target = next((s for s in load_servers() if s['id'] == server_id), None)
    if target and set_user_deaf(target['ip'], session, request.json.get('deaf', True), _ice_port(target), _ice_secret(target)): return jsonify({"status": "success"})
    return jsonify({"status": "failed"}), 500

@app.route('/api/server/<int:server_id>/message/<int:session>', methods=['POST'])
def api_message_user(server_id, session):
    target = next((s for s in load_servers() if s['id'] == server_id), None)
    msg = request.json.get('message', '')
    if target and send_message_to_user(target['ip'], session, msg, _ice_port(target), _ice_secret(target)): return jsonify({"status": "success"})
    return jsonify({"status": "failed"}), 500

@app.route('/api/server/<int:server_id>/channel/<int:channel_id>/rename', methods=['POST'])
def api_rename_channel(server_id, channel_id):
    target = next((s for s in load_servers() if s['id'] == server_id), None)
    new_name = request.json.get('name', '')
    if target and rename_channel(target['ip'], channel_id, new_name, _ice_port(target), _ice_secret(target)): return jsonify({"status": "success"})
    return jsonify({"status": "failed"}), 500

@app.route('/api/server/<int:server_id>/channel/<int:channel_id>/description', methods=['POST'])
def api_channel_description(server_id, channel_id):
    target = next((s for s in load_servers() if s['id'] == server_id), None)
    if target and set_channel_description(target['ip'], channel_id, request.json.get('description', ''), _ice_port(target), _ice_secret(target)): return jsonify({"status": "success"})
    return jsonify({"status": "failed"}), 500

@app.route('/api/server/<int:server_id>/welcome', methods=['POST'])
def api_set_welcome(server_id):
    target = next((s for s in load_servers() if s['id'] == server_id), None)
    if target and set_welcome_text(target['ip'], request.json.get('text', ''), _ice_port(target), _ice_secret(target)): return jsonify({"status": "success"})
    return jsonify({"status": "failed"}), 500

@app.route('/api/server/<int:server_id>/maxusers', methods=['POST'])
def api_set_maxusers(server_id):
    target = next((s for s in load_servers() if s['id'] == server_id), None)
    if target and set_max_users(target['ip'], request.json.get('max_users', 100), _ice_port(target), _ice_secret(target)): return jsonify({"status": "success"})
    return jsonify({"status": "failed"}), 500

@app.route('/api/server/<int:server_id>/mute_all/<int:channel_id>', methods=['POST'])
def api_mute_all(server_id, channel_id):
    target = next((s for s in load_servers() if s['id'] == server_id), None)
    if target and mute_all_in_channel(target['ip'], channel_id, _ice_port(target), _ice_secret(target)): return jsonify({"status": "success"})
    return jsonify({"status": "failed"}), 500

@app.route('/api/server/<int:server_id>/restart', methods=['POST'])
def api_restart(server_id):
    target = next((s for s in load_servers() if s['id'] == server_id), None)
    if target and restart_server(target['ip'], _ice_port(target), _ice_secret(target)): return jsonify({"status": "success"})
    return jsonify({"status": "failed"}), 500

@app.route('/api/server/<int:server_id>/channel', methods=['POST'])
def api_create_channel(server_id):
    data = request.json; target = next((s for s in load_servers() if s['id'] == server_id), None)
    if target and create_channel(target['ip'], data.get('name'), data.get('parent_id', 0), _ice_port(target), _ice_secret(target)): return jsonify({"status": "success"})
    return jsonify({"status": "failed"}), 500

@app.route('/api/server/<int:server_id>/password', methods=['POST'])
def api_set_password(server_id):
    new_password = request.json.get('password', ''); servers = load_servers()
    target = next((s for s in servers if s['id'] == server_id), None)
    if not target: return jsonify({"status": "failed"}), 404
    if set_server_password(target['ip'], new_password, _ice_port(target), _ice_secret(target)):
        for s in servers:
            if s['id'] == server_id: s['password'] = new_password; break
        save_servers(servers)
        return jsonify({"status": "success"})
    return jsonify({"status": "failed"}), 500

@app.route('/api/server/<int:server_id>/mute/<int:session>', methods=['POST'])
def api_mute(server_id, session):
    target = next((s for s in load_servers() if s['id'] == server_id), None)
    if target and set_user_mute(target['ip'], session, request.json.get('mute', True), _ice_port(target), _ice_secret(target)): return jsonify({"status": "success"})
    return jsonify({"status": "failed"}), 500

@app.route('/api/server/<int:server_id>/move/<int:session>', methods=['POST'])
def api_move_user(server_id, session):
    target = next((s for s in load_servers() if s['id'] == server_id), None)
    if target and move_user(target['ip'], session, request.json.get('channel_id'), _ice_port(target), _ice_secret(target)): return jsonify({"status": "success"})
    return jsonify({"status": "failed"}), 500

@app.route('/api/server/<int:server_id>/channel/<int:channel_id>', methods=['DELETE'])
def api_delete_channel(server_id, channel_id):
    target = next((s for s in load_servers() if s['id'] == server_id), None)
    if target and remove_channel(target['ip'], channel_id, _ice_port(target), _ice_secret(target)): return jsonify({"status": "success"})
    return jsonify({"status": "failed"}), 500

@app.route('/api/server/<int:server_id>/rename_user/<int:session>', methods=['POST'])
def api_rename_user(server_id, session):
    target = next((s for s in load_servers() if s['id'] == server_id), None)
    if target and rename_user(target['ip'], session, request.json.get('name', ''), _ice_port(target), _ice_secret(target)): return jsonify({"status": "success"})
    return jsonify({"status": "failed"}), 500

@app.route('/api/server/<int:server_id>/channel/<int:channel_id>/password', methods=['POST'])
def api_channel_password(server_id, channel_id):
    target = next((s for s in load_servers() if s['id'] == server_id), None)
    if target and set_channel_password(target['ip'], channel_id, request.json.get('password', ''), _ice_port(target), _ice_secret(target)): return jsonify({"status": "success"})
    return jsonify({"status": "failed"}), 500

@app.route('/api/server/<int:server_id>/channel/<int:channel_id>/maxusers', methods=['POST'])
def api_channel_maxusers(server_id, channel_id):
    target = next((s for s in load_servers() if s['id'] == server_id), None)
    if target and set_channel_max_users(target['ip'], channel_id, request.json.get('max_users', 0), _ice_port(target), _ice_secret(target)): return jsonify({"status": "success"})
    return jsonify({"status": "failed"}), 500

@app.route('/api/server/<int:server_id>/mumble_logs', methods=['GET'])
def api_mumble_logs(server_id):
    target = next((s for s in load_servers() if s['id'] == server_id), None)
    if not target: return jsonify({"error": "Not found"}), 404
    return jsonify({"logs": get_mumble_logs(target['ip'], _ice_port(target), _ice_secret(target))})

@app.route('/api/server/<int:server_id>/users/registered', methods=['GET'])
def api_get_registered_users(server_id):
    target = next((s for s in load_servers() if s['id'] == server_id), None)
    if not target: return jsonify({"error": "Not found"}), 404
    return jsonify({"users": get_registered_users(target['ip'], _ice_port(target), _ice_secret(target))})

@app.route('/api/server/<int:server_id>/users/register', methods=['POST'])
def api_register_user(server_id):
    target = next((s for s in load_servers() if s['id'] == server_id), None)
    uid = register_user(target['ip'], request.json.get('username', ''), request.json.get('password', ''), _ice_port(target), _ice_secret(target))
    if uid is not None: return jsonify({"status": "success", "uid": uid})
    return jsonify({"status": "failed"}), 500

@app.route('/api/server/<int:server_id>/users/unregister/<int:user_id>', methods=['POST'])
def api_unregister_user(server_id, user_id):
    target = next((s for s in load_servers() if s['id'] == server_id), None)
    if target and unregister_user(target['ip'], user_id, _ice_port(target), _ice_secret(target)): return jsonify({"status": "success"})
    return jsonify({"status": "failed"}), 500

@app.route('/api/transcripts/filter/<int:server_id>')
def api_transcript_filter(server_id):
    date_from = request.args.get('from', ''); date_to = request.args.get('to', ''); user_filter = request.args.get('user', '')
    conn = sqlite3.connect(DB_FILE); query = "SELECT time, bot, user, message FROM ai_transcripts WHERE server_id=?"; params = [server_id]
    if date_from: query += " AND time >= ?"; params.append(date_from)
    if date_to:   query += " AND time <= ?"; params.append(date_to + ' 23:59:59')
    if user_filter: query += " AND user LIKE ?"; params.append(f"%{user_filter}%")
    query += " ORDER BY time DESC LIMIT 200"
    rows = conn.execute(query, params).fetchall(); conn.close()
    return jsonify({"transcripts": [{"time": r[0], "bot": r[1], "user": r[2], "message": r[3]} for r in rows]})
@app.route('/api/fleet/cleanup', methods=['POST'])
def force_cleanup_containers():
    try:
        active_servers = load_servers()
        active_container_names = [
            str(s.get('ip') or '').strip() for s in active_servers
            if str(s.get('ip') or '').strip().startswith('roip-mumble')
        ]
        result = _control_request('/containers/cleanup', {"active_names": active_container_names})
        return jsonify({
            "status": "success",
            "message": f"ล้างคอนเทนเนอร์ที่ระบบจัดการเรียบร้อย ({result.get('removed_count', 0)} รายการ)",
            "removed": result.get('removed', []),
        })
    except Exception as e:
        return jsonify({"status": "failed", "error": str(e)}), 500

@app.route('/api/fleet/create', methods=['POST'])
def create_docker_server():
    data = request.json or {}
    name = str(data.get('name') or 'Station').strip()[:120]
    servers = load_servers()
    existing_ids = [s['id'] for s in servers]
    try:
        inventory = _control_request('/containers/inventory')
        container_names = {item['name'] for item in inventory.get('containers', [])}
    except Exception as e:
        return jsonify({"status": "failed", "error": f"Control service unavailable: {e}"}), 503

    new_id = 1
    while True:
        container_name = f"roip-mumble{new_id}"
        if new_id not in existing_ids and container_name not in container_names:
            break
        new_id += 1

    admin_pass = os.getenv('MUMBLE_ICE_SECRET', 'tactical1234')
    host_port = 64739 + new_id
    host_ice = 6501 + new_id

    try:
        _control_request('/containers/create', {
            "station_id": new_id,
            "container_name": container_name,
            "host_port": host_port,
            "host_ice_port": host_ice,
            "ice_secret": admin_pass,
        }, timeout=120)
        new_server = {
            "id": new_id,
            "name": name,
            "ip": container_name,
            "port": 64738,
            "ice_port": 6502,
            "external_port": host_port,
            "password": admin_pass
        }
        servers.append(new_server)
        save_servers(servers)
        sync_stations()
        return jsonify({
            "status": "success",
            "message": f"สร้างสถานี {container_name} สำเร็จ (MikroTik Port: {host_port})"
        })
    except Exception as e:
        return jsonify({"status": "failed", "error": str(e)}), 500

# ---------------------------------------------------------
# ฟังก์ชันสำหรับลบสถานี (ล้างฐานข้อมูล + ทำลาย Container ถาวร)
@app.route('/api/fleet/delete/<int:server_id>', methods=['POST'])
def delete_docker_server(server_id):
    servers = load_servers()
    target_server = next((s for s in servers if s['id'] == server_id), None)
    if not target_server:
        return jsonify({"status": "failed", "error": "ไม่พบสถานี"}), 404
    container_name = str(target_server.get('ip') or '').strip()
    if not container_name.startswith('roip-mumble'):
        return jsonify({"status": "failed", "error": "สถานีนี้ไม่ได้อยู่ภายใต้ Fleet Docker"}), 400
    try:
        _control_request('/containers/delete', {"container_name": container_name})
    except Exception as e:
        return jsonify({"status": "failed", "error": str(e)}), 502

    servers = [s for s in servers if s['id'] != server_id]
    save_servers(servers)
    sync_stations()
    return jsonify({"status": "success"})
    
@app.route('/api/admin/users', methods=['GET', 'POST'])
def api_admin_users():
    if request.method == 'GET':
        return jsonify({"users": list_users(), "rooms": list_admin_room_options()})
    data = request.get_json(silent=True) or {}
    try:
        user = create_user(
            data.get('username'),
            data.get('password'),
            data.get('role', 'user'),
            data.get('is_active', True),
        )
        audit_user_action(session.get('username'), 'user.create', user['username'], request.remote_addr, {"role": user['role']})
        return jsonify({"status": "success", "user": user}), 201
    except ValueError as exc:
        return jsonify({"status": "failed", "error": str(exc)}), 400


def list_admin_room_options():
    """Return current station/channel choices for assigning user search scope."""
    rooms = []
    for server in load_servers():
        try:
            station_id = int(server.get('id'))
        except (TypeError, ValueError):
            continue
        channels = []
        try:
            status = get_server_status(server['ip'], _ice_port(server), _ice_secret(server))
            channels = status.get('channels', []) if isinstance(status, dict) else []
        except Exception:
            channels = []
        seen = set()
        for channel in channels:
            try:
                channel_id = int(channel.get('id', 0))
            except (TypeError, ValueError):
                continue
            if channel_id in seen:
                continue
            seen.add(channel_id)
            rooms.append({
                "station_id": station_id,
                "station_name": str(server.get('name') or f"Station {station_id}"),
                "channel_id": channel_id,
                "channel_name": str(channel.get('name') or ('Root' if channel_id == 0 else f"ห้อง {channel_id}")),
            })
        if not channels:
            rooms.append({
                "station_id": station_id,
                "station_name": str(server.get('name') or f"Station {station_id}"),
                "channel_id": 0,
                "channel_name": "Root (ห้องหลัก)",
            })
    return rooms


@app.route('/api/admin/users/<int:user_id>/rooms', methods=['PUT'])
def api_admin_user_rooms(user_id):
    data = request.get_json(silent=True) or {}
    try:
        user = replace_user_room_permissions(user_id, data.get('rooms') or [])
        audit_user_action(
            session.get('username'),
            'user.rooms.update',
            user.get('username'),
            request.remote_addr,
            {"room_count": len(user.get('room_permissions') or [])},
        )
        return jsonify({"status": "success", "user": user})
    except ValueError as exc:
        return jsonify({"status": "failed", "error": str(exc)}), 400


@app.route('/api/admin/users/<int:user_id>', methods=['PATCH', 'DELETE'])
def api_admin_user(user_id):
    if request.method == 'DELETE':
        if int(session.get('user_id', 0)) == user_id:
            return jsonify({"status": "failed", "error": "ไม่สามารถลบบัญชีที่กำลังใช้งานอยู่"}), 400
        try:
            deleted = delete_user(user_id)
            audit_user_action(session.get('username'), 'user.delete', deleted['username'], request.remote_addr)
            return jsonify({"status": "success", "user": deleted})
        except ValueError as exc:
            return jsonify({"status": "failed", "error": str(exc)}), 400

    data = request.get_json(silent=True) or {}
    if int(session.get('user_id', 0)) == user_id:
        if data.get('is_active') is False or data.get('role') == 'user':
            return jsonify({"status": "failed", "error": "ไม่สามารถลดสิทธิ์หรือปิดใช้งานบัญชีตัวเอง"}), 400
    if data.get('role') == 'user' or data.get('is_active') is False:
        if count_active_admins() <= 1:
            return jsonify({"status": "failed", "error": "ต้องเหลือ Admin ที่ใช้งานได้อย่างน้อย 1 บัญชี"}), 400
    try:
        user = update_user(
            user_id,
            role=data.get('role') if 'role' in data else None,
            password=data.get('password') if 'password' in data else None,
            is_active=data.get('is_active') if 'is_active' in data else None,
        )
        audit_user_action(session.get('username'), 'user.update', user['username'], request.remote_addr, {"role": user['role'], "is_active": user['is_active']})
        return jsonify({"status": "success", "user": user})
    except ValueError as exc:
        return jsonify({"status": "failed", "error": str(exc)}), 400


@app.route('/api/session/check')
def api_session_check():
    logged_in = bool(session.get('logged_in') and session.get('role') in ('admin', 'user'))
    return jsonify({
        "logged_in": logged_in,
        "user": {
            "id": session.get('user_id'),
            "username": session.get('username'),
            "role": session.get('role'),
        } if logged_in else None,
    })

def auto_start_bots_on_boot():
    global active_ai_bots
    for s in load_servers():
        config = s.get('autobot_config', {}); mode = config.get('mode', 'off')
        if mode == 'off': continue
        channels_to_join = []
        if mode == 'all':
            try:
                status = get_server_status(s['ip'], _ice_port(s), _ice_secret(s))
                if status['online']: channels_to_join = list(set([0] + [c['id'] for c in status['channels']]))
                else: channels_to_join = [0]
            except: channels_to_join = [0]
        elif mode == 'specific': channels_to_join = config.get('channels', [])
            
        for ch_id in channels_to_join:
            rs = ''.join(random.choices(string.ascii_uppercase + string.digits, k=3))
            b_name = f"[AI-R-{rs}]"
            proc = subprocess.Popen([sys.executable, 'ai_bot.py', b_name, str(s['id']), s['ip'], str(s.get('port', 64738)), s.get('password', 'tactical1234'), str(ch_id)])
            active_ai_bots.append({"name": b_name, "proc": proc, "server_id": s['id']})
            time.sleep(1) 

threading.Timer(3.0, auto_start_bots_on_boot).start()

if __name__ == '__main__':
    # ✨ เพิ่ม ssl_context='adhoc' เข้าไป เพื่อสร้าง HTTPS จำลอง
    app.run(debug=False, host='0.0.0.0', port=5000)
