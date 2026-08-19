import copy
import Ice, os, sys, traceback, time
import threading

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

ice_file = os.path.join(current_dir, 'MumbleServer.ice')
if not os.path.exists(ice_file):
    print("❌ Critical Error: ไม่พบไฟล์แปลน MumbleServer.ice ในฐานทัพ!")
    sys.exit(1)

ice_slice_dir = Ice.getSliceDir()

try:
    # 1. ลองแบบมาตรฐานใหม่ (Windows / Python 3.13+)
    Ice.loadSlice([f'-I{ice_slice_dir}', f'-I{current_dir}', ice_file])
except TypeError:
    # 2. ถ้าโดนด่า (TypeError) ให้สลับมาใช้มาตรฐานเก่า (Linux / Docker)
    Ice.loadSlice(f'-I{ice_slice_dir} -I{current_dir} {ice_file}')

try:
    import MumbleServer as MumbleCore
except ImportError:
    print("❌ Critical Error: โหลด MumbleServer ไม่สำเร็จ!")
    sys.exit(1)

ICE_SECRET = "tactical1234"
DEFAULT_ICE_PORT = 6502
_STATUS_CACHE_TTL = float(os.getenv("MUMBLE_STATUS_CACHE_TTL", "1.5"))
_status_cache = {}
_status_cache_lock = threading.Lock()


def get_proxy(ip, ice_port=DEFAULT_ICE_PORT, secret=ICE_SECRET):
    init_data = Ice.InitializationData()
    init_data.properties = Ice.createProperties()
    init_data.properties.setProperty("Ice.MessageSizeMax", "65536")
    ic = Ice.initialize([], init_data)
    proxy_string = f"Meta:tcp -h {ip.strip()} -p {ice_port} -t 10000"
    try:
        base = ic.stringToProxy(proxy_string)
        meta = MumbleCore.MetaPrx.uncheckedCast(base)
        ctx = {"secret": secret} if secret else {}
        return ic, meta, ctx
    except Exception as e:
        if ic: ic.destroy()
        raise e


def get_server_status(ip, ice_port=DEFAULT_ICE_PORT, secret=ICE_SECRET):
    cache_key = (str(ip).strip(), int(ice_port), str(secret or ""))
    now = time.monotonic()
    with _status_cache_lock:
        cached = _status_cache.get(cache_key)
        if cached and now - cached[0] < _STATUS_CACHE_TTL:
            return copy.deepcopy(cached[1])
    status_data = {"online": False, "users": [], "channels": [], "server_password": "", "error": ""}
    ic = None
    try:
        ic, meta, ctx = get_proxy(ip, ice_port, secret)
        server = meta.getServer(1, ctx)
        if not server: raise RuntimeError("หา Virtual Server ID 1 ไม่พบ")
        users = server.getUsers(ctx)
        channels = server.getChannels(ctx)
        for c_id, c in channels.items():
            status_data["channels"].append({"id": c_id, "name": getattr(c, 'name', 'Unknown')})
        for id, u in users.items():
            ch_id = getattr(u, 'channel', -1)
            ch_name = channels[ch_id].name if ch_id in channels else "Unknown"
            ping = int(getattr(u, 'tcpPing', 0))
            status_data["users"].append({
                "session": getattr(u, 'session', 0),
                "name": getattr(u, 'name', 'Unknown User'),
                "channel": ch_name,
                "channel_id": ch_id,
                "mute": getattr(u, 'mute', False) or getattr(u, 'selfMute', False),
                "deaf": getattr(u, 'deaf', False) or getattr(u, 'selfDeaf', False),
                "ping": ping
            })
        status_data["online"] = True
    except Exception as e:
        status_data["error"] = f"ICE Error: {str(e)}"
        print(f"❌ [get_server_status] {ip}:{ice_port} ERROR: {e}")
    finally:
        if ic: ic.destroy()
    with _status_cache_lock:
        _status_cache[cache_key] = (time.monotonic(), copy.deepcopy(status_data))
    return status_data


def kick_user(ip, session, ice_port=DEFAULT_ICE_PORT, secret=ICE_SECRET):
    ic = None
    try:
        ic, meta, ctx = get_proxy(ip, ice_port, secret)
        meta.getServer(1, ctx).kickUser(session, "Kicked by Admin", ctx)
        return True
    except Exception as e:
        return False
    finally:
        if ic: ic.destroy()


def ban_user(ip, session, ice_port=DEFAULT_ICE_PORT, secret=ICE_SECRET):
    ic = None
    try:
        ic, meta, ctx = get_proxy(ip, ice_port, secret)
        server = meta.getServer(1, ctx)
        user = server.getState(session, ctx)
        ban = MumbleCore.Ban()
        ban.address = user.address
        ban.bits = 128
        ban.reason = "Banned by Tactical Command"
        current_bans = server.getBans(ctx)
        current_bans.append(ban)
        server.setBans(current_bans, ctx)
        server.kickUser(session, "You have been banned.", ctx)
        return True
    except Exception as e:
        return False
    finally:
        if ic: ic.destroy()


def get_ban_list(ip, ice_port=DEFAULT_ICE_PORT, secret=ICE_SECRET):
    ic = None
    try:
        ic, meta, ctx = get_proxy(ip, ice_port, secret)
        server = meta.getServer(1, ctx)
        bans = server.getBans(ctx)
        result = []
        for b in bans:
            result.append({
                "address": list(b.address) if b.address else [],
                "bits": b.bits,
                "reason": b.reason,
                "name": getattr(b, 'name', ''),
                "start": str(getattr(b, 'start', '')),
                "duration": getattr(b, 'duration', 0)
            })
        return result
    except Exception as e:
        return []
    finally:
        if ic: ic.destroy()


def unban_user(ip, index, ice_port=DEFAULT_ICE_PORT, secret=ICE_SECRET):
    ic = None
    try:
        ic, meta, ctx = get_proxy(ip, ice_port, secret)
        server = meta.getServer(1, ctx)
        bans = server.getBans(ctx)
        if 0 <= index < len(bans):
            bans.pop(index)
            server.setBans(bans, ctx)
            return True
        return False
    except Exception as e:
        return False
    finally:
        if ic: ic.destroy()


def set_user_deaf(ip, session, deaf_status, ice_port=DEFAULT_ICE_PORT, secret=ICE_SECRET):
    ic = None
    try:
        ic, meta, ctx = get_proxy(ip, ice_port, secret)
        server = meta.getServer(1, ctx)
        user = server.getState(session, ctx)
        user.selfDeaf = False
        user.deaf = deaf_status
        server.setState(user, ctx)
        return True
    except Exception as e:
        return False
    finally:
        if ic: ic.destroy()


def send_message_to_user(ip, session, message, ice_port=DEFAULT_ICE_PORT, secret=ICE_SECRET):
    ic = None
    try:
        ic, meta, ctx = get_proxy(ip, ice_port, secret)
        server = meta.getServer(1, ctx)
        msg = f"<b style='color:orange;'>[ADMIN → YOU]:</b> {message}"
        server.sendMessage(session, msg, ctx)
        return True
    except Exception as e:
        return False
    finally:
        if ic: ic.destroy()


def rename_channel(ip, channel_id, new_name, ice_port=DEFAULT_ICE_PORT, secret=ICE_SECRET):
    ic = None
    try:
        ic, meta, ctx = get_proxy(ip, ice_port, secret)
        server = meta.getServer(1, ctx)
        channels = server.getChannels(ctx)
        if channel_id not in channels:
            return False
        ch = channels[channel_id]
        ch.name = new_name
        server.setChannelState(ch, ctx)
        return True
    except Exception as e:
        return False
    finally:
        if ic: ic.destroy()


def set_channel_description(ip, channel_id, description, ice_port=DEFAULT_ICE_PORT, secret=ICE_SECRET):
    ic = None
    try:
        ic, meta, ctx = get_proxy(ip, ice_port, secret)
        server = meta.getServer(1, ctx)
        channels = server.getChannels(ctx)
        if channel_id not in channels: return False
        ch = channels[channel_id]
        ch.description = description
        server.setChannelState(ch, ctx)
        return True
    except Exception as e:
        return False
    finally:
        if ic: ic.destroy()


def set_welcome_text(ip, text, ice_port=DEFAULT_ICE_PORT, secret=ICE_SECRET):
    ic = None
    try:
        ic, meta, ctx = get_proxy(ip, ice_port, secret)
        meta.getServer(1, ctx).setConf("welcometext", text, ctx)
        return True
    except Exception as e:
        return False
    finally:
        if ic: ic.destroy()


def set_max_users(ip, max_users, ice_port=DEFAULT_ICE_PORT, secret=ICE_SECRET):
    ic = None
    try:
        ic, meta, ctx = get_proxy(ip, ice_port, secret)
        meta.getServer(1, ctx).setConf("users", str(max_users), ctx)
        return True
    except Exception as e:
        return False
    finally:
        if ic: ic.destroy()


def mute_all_in_channel(ip, channel_id, ice_port=DEFAULT_ICE_PORT, secret=ICE_SECRET):
    ic = None
    try:
        ic, meta, ctx = get_proxy(ip, ice_port, secret)
        server = meta.getServer(1, ctx)
        users = server.getUsers(ctx)
        for uid, u in users.items():
            if getattr(u, 'channel', -1) == channel_id:
                u.selfMute = False; u.mute = True
                server.setState(u, ctx)
        return True
    except Exception as e:
        return False
    finally:
        if ic: ic.destroy()


def create_channel(ip, name, parent_id=0, ice_port=DEFAULT_ICE_PORT, secret=ICE_SECRET):
    ic = None
    try:
        ic, meta, ctx = get_proxy(ip, ice_port, secret)
        meta.getServer(1, ctx).addChannel(name, parent_id, ctx)
        return True
    except Exception as e:
        return False
    finally:
        if ic: ic.destroy()


def set_user_mute(ip, session, mute_status, ice_port=DEFAULT_ICE_PORT, secret=ICE_SECRET):
    ic = None
    try:
        ic, meta, ctx = get_proxy(ip, ice_port, secret)
        server = meta.getServer(1, ctx)
        user = server.getState(session, ctx)
        user.selfMute = False; user.mute = mute_status
        server.setState(user, ctx)
        return True
    except Exception as e:
        return False
    finally:
        if ic: ic.destroy()


def move_user(ip, session, channel_id, ice_port=DEFAULT_ICE_PORT, secret=ICE_SECRET):
    ic = None
    try:
        ic, meta, ctx = get_proxy(ip, ice_port, secret)
        server = meta.getServer(1, ctx)
        user = server.getState(session, ctx)
        user.channel = channel_id
        server.setState(user, ctx)
        return True
    except Exception as e:
        return False
    finally:
        if ic: ic.destroy()


def remove_channel(ip, channel_id, ice_port=DEFAULT_ICE_PORT, secret=ICE_SECRET):
    ic = None
    try:
        ic, meta, ctx = get_proxy(ip, ice_port, secret)
        meta.getServer(1, ctx).removeChannel(channel_id, ctx)
        return True
    except Exception as e:
        return False
    finally:
        if ic: ic.destroy()


def restart_server(ip, ice_port=DEFAULT_ICE_PORT, secret=ICE_SECRET):
    ic = None
    try:
        ic, meta, ctx = get_proxy(ip, ice_port, secret)
        server = meta.getServer(1, ctx)
        server.stop(ctx)
        time.sleep(2)
        server.start(ctx)
        return True
    except Exception as e:
        return False
    finally:
        if ic: ic.destroy()

# ✨ อัปเกรดฟังก์ชันส่งแชท ให้เลือกระบุห้องได้
def broadcast_message(ip, message, channel_id=0, tree=True, ice_port=DEFAULT_ICE_PORT, secret=ICE_SECRET):
    ic = None
    try:
        ic, meta, ctx = get_proxy(ip, ice_port, secret)
        server = meta.getServer(1, ctx)
        msg = f"<b style='color:red;'>[ADMIN]:</b> {message}"
        server.sendMessageChannel(channel_id, tree, msg, ctx)
        return True
    except Exception as e:
        return False
    finally:
        if ic: ic.destroy()


def set_server_password(ip, new_password, ice_port=DEFAULT_ICE_PORT, secret=ICE_SECRET):
    ic = None
    try:
        ic, meta, ctx = get_proxy(ip, ice_port, secret)
        server = meta.getServer(1, ctx)
        server.setConf("password", new_password, ctx)
        return True
    except Exception as e:
        return False
    finally:
        if ic: ic.destroy()


def rename_user(ip, session, new_name, ice_port=DEFAULT_ICE_PORT, secret=ICE_SECRET):
    ic = None
    try:
        ic, meta, ctx = get_proxy(ip, ice_port, secret)
        server = meta.getServer(1, ctx)
        user = server.getState(session, ctx)
        user.name = new_name
        server.setState(user, ctx)
        return True
    except Exception as e:
        return False
    finally:
        if ic: ic.destroy()


def set_channel_password(ip, channel_id, password, ice_port=DEFAULT_ICE_PORT, secret=ICE_SECRET):
    ic = None
    try:
        ic, meta, ctx = get_proxy(ip, ice_port, secret)
        server = meta.getServer(1, ctx)
        channels = server.getChannels(ctx)
        if channel_id not in channels: return False
        ch = channels[channel_id]
        ch.password = password
        server.setChannelState(ch, ctx)
        return True
    except Exception as e:
        return False
    finally:
        if ic: ic.destroy()


def set_channel_max_users(ip, channel_id, max_users, ice_port=DEFAULT_ICE_PORT, secret=ICE_SECRET):
    ic = None
    try:
        ic, meta, ctx = get_proxy(ip, ice_port, secret)
        server = meta.getServer(1, ctx)
        channels = server.getChannels(ctx)
        if channel_id not in channels: return False
        ch = channels[channel_id]
        ch.maxUsers = max_users
        server.setChannelState(ch, ctx)
        return True
    except Exception as e:
        return False
    finally:
        if ic: ic.destroy()


def get_mumble_logs(ip, ice_port=DEFAULT_ICE_PORT, secret=ICE_SECRET):
    ic = None
    try:
        ic, meta, ctx = get_proxy(ip, ice_port, secret)
        server = meta.getServer(1, ctx)
        logs = server.getLog(0, 50, ctx)
        result = []
        for entry in logs:
            result.append({
                "timestamp": str(getattr(entry, 'timestamp', '')),
                "txt": getattr(entry, 'txt', '')
            })
        return list(reversed(result))
    except Exception as e:
        return []
    finally:
        if ic: ic.destroy()


def register_user(ip, username, password="", ice_port=DEFAULT_ICE_PORT, secret=ICE_SECRET):
    ic = None
    try:
        ic, meta, ctx = get_proxy(ip, ice_port, secret)
        server = meta.getServer(1, ctx)
        info = {
            MumbleCore.UserInfo.UserName: username,
            MumbleCore.UserInfo.UserPassword: password,
            MumbleCore.UserInfo.UserEmail: "",
        }
        uid = server.registerUser(info, ctx)
        return uid
    except Exception as e:
        return None
    finally:
        if ic: ic.destroy()


def get_registered_users(ip, ice_port=DEFAULT_ICE_PORT, secret=ICE_SECRET):
    ic = None
    try:
        ic, meta, ctx = get_proxy(ip, ice_port, secret)
        server = meta.getServer(1, ctx)
        users = server.getRegisteredUsers("", ctx)
        return [{"id": uid, "name": name} for uid, name in users.items() if uid > 0]
    except Exception as e:
        return []
    finally:
        if ic: ic.destroy()


def unregister_user(ip, user_id, ice_port=DEFAULT_ICE_PORT, secret=ICE_SECRET):
    ic = None
    try:
        ic, meta, ctx = get_proxy(ip, ice_port, secret)
        server = meta.getServer(1, ctx)
        server.unregisterUser(user_id, ctx)
        return True
    except Exception as e:
        return False
    finally:
        if ic: ic.destroy()
