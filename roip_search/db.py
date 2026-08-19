import hashlib
import json
import os
import sqlite3
import threading
import wave
from datetime import datetime, timezone
from pathlib import Path

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from .utils import decode_cursor, encode_cursor, normalize_text, parse_datetime, parse_legacy_datetime


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://roip:roip-change-me@postgres:5432/roip",
)
LEGACY_DB_FILE = Path(os.getenv("LEGACY_DB_FILE", "tactical.db"))
SERVERS_FILE = Path(os.getenv("SERVERS_FILE", "servers.json"))
RECORDS_DIR = Path(os.getenv("RECORDS_DIR", "static/records")).resolve()
SCHEMA_FILE = Path(__file__).with_name("schema.sql")

_pool = None
_pool_lock = threading.Lock()


def _like_contains(value):
    escaped = str(value).replace("!", "!!").replace("%", "!%").replace("_", "!_")
    return f"%{escaped}%"


def get_pool():
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                pool = ConnectionPool(
                    conninfo=DATABASE_URL,
                    min_size=1,
                    max_size=int(os.getenv("POSTGRES_POOL_SIZE", "8")),
                    kwargs={"row_factory": dict_row},
                    open=False,
                )
                pool.open(wait=True, timeout=45)
                _pool = pool
    return _pool


def initialize_database():
    RECORDS_DIR.mkdir(parents=True, exist_ok=True)
    pool = get_pool()
    with pool.connection() as conn:
        conn.execute(SCHEMA_FILE.read_text(encoding="utf-8"))
        conn.commit()
    sync_stations()
    migrate_legacy_data()


def database_health():
    try:
        with get_pool().connection() as conn:
            row = conn.execute("SELECT 1 AS ok").fetchone()
            return bool(row and row["ok"] == 1)
    except Exception:
        return False


def _load_servers():
    if not SERVERS_FILE.exists():
        return []
    try:
        return json.loads(SERVERS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []


def sync_stations():
    servers = _load_servers()
    with get_pool().connection() as conn:
        for server in servers:
            station_id = int(server["id"])
            conn.execute(
                """
                INSERT INTO stations (id, name, container_name)
                VALUES (%s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    container_name = EXCLUDED.container_name,
                    updated_at = NOW()
                """,
                (
                    station_id,
                    str(server.get("name") or f"Station {station_id}").strip(),
                    str(server.get("ip") or "").strip() or None,
                ),
            )
        conn.commit()


def _ensure_station(conn, station_id):
    station_id = int(station_id)
    conn.execute(
        """
        INSERT INTO stations (id, name)
        VALUES (%s, %s)
        ON CONFLICT (id) DO NOTHING
        """,
        (station_id, f"Station {station_id}"),
    )
    return station_id


def _audio_duration_ms(path):
    try:
        with wave.open(str(path), "rb") as handle:
            if handle.getframerate() <= 0:
                return None
            return int(handle.getnframes() * 1000 / handle.getframerate())
    except (wave.Error, OSError):
        return None


def _register_audio_asset(conn, filename):
    if not filename:
        return None
    storage_key = Path(str(filename)).name
    path = (RECORDS_DIR / storage_key).resolve()
    if path.parent != RECORDS_DIR or not path.is_file():
        return None
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    row = conn.execute(
        """
        INSERT INTO audio_assets
            (storage_key, mime_type, size_bytes, sha256, duration_ms)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (storage_key) DO UPDATE SET
            size_bytes = EXCLUDED.size_bytes,
            sha256 = EXCLUDED.sha256,
            duration_ms = EXCLUDED.duration_ms,
            deleted_at = NULL
        RETURNING id
        """,
        (storage_key, "audio/wav", path.stat().st_size, digest, _audio_duration_ms(path)),
    ).fetchone()
    return row["id"]


def _upsert_message(
    conn,
    *,
    source_event_id,
    station_id,
    occurred_at,
    speaker_name,
    content,
    bot_name=None,
    channel_id=None,
    channel_name=None,
    message_type="voice_transcript",
    confidence=None,
    language="th-TH",
    duration_ms=None,
    audio_asset_id=None,
    metadata=None,
):
    station_id = _ensure_station(conn, station_id)
    row = conn.execute(
        """
        INSERT INTO chat_messages (
            source_event_id, station_id, channel_id, channel_name,
            speaker_name, bot_name, message_type, content_raw,
            content_normalized, occurred_at, confidence, language,
            duration_ms, audio_asset_id, metadata
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        ON CONFLICT (source_event_id) DO UPDATE SET
            channel_id = COALESCE(EXCLUDED.channel_id, chat_messages.channel_id),
            channel_name = COALESCE(EXCLUDED.channel_name, chat_messages.channel_name),
            confidence = COALESCE(EXCLUDED.confidence, chat_messages.confidence),
            duration_ms = COALESCE(EXCLUDED.duration_ms, chat_messages.duration_ms),
            audio_asset_id = COALESCE(EXCLUDED.audio_asset_id, chat_messages.audio_asset_id),
            metadata = chat_messages.metadata || EXCLUDED.metadata
        RETURNING id
        """,
        (
            str(source_event_id),
            station_id,
            int(channel_id) if channel_id not in (None, "") else None,
            channel_name,
            str(speaker_name or "Unknown")[:200],
            bot_name,
            message_type,
            str(content or ""),
            normalize_text(content),
            occurred_at,
            confidence,
            language,
            duration_ms,
            audio_asset_id,
            Jsonb(metadata or {}),
        ),
    ).fetchone()
    return row["id"]


def ingest_chat_message(
    *,
    source_event_id,
    station_id,
    occurred_at,
    speaker_name,
    content,
    bot_name=None,
    channel_id=None,
    channel_name=None,
    confidence=None,
    audio_filename=None,
    keywords=None,
    metadata=None,
):
    with get_pool().connection() as conn:
        audio_asset_id = _register_audio_asset(conn, audio_filename)
        message_id = _upsert_message(
            conn,
            source_event_id=source_event_id,
            station_id=station_id,
            occurred_at=occurred_at,
            speaker_name=speaker_name,
            content=content,
            bot_name=bot_name,
            channel_id=channel_id,
            channel_name=channel_name,
            confidence=confidence,
            audio_asset_id=audio_asset_id,
            metadata=metadata,
        )
        for keyword in keywords or []:
            conn.execute(
                """
                INSERT INTO keyword_hits (message_id, keyword, matched_text, detected_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (message_id, keyword) DO NOTHING
                """,
                (message_id, keyword, keyword, occurred_at),
            )
        conn.commit()
        return message_id


def migrate_legacy_data():
    if not LEGACY_DB_FILE.exists():
        return {"transcripts": 0, "alerts": 0}

    legacy = sqlite3.connect(f"file:{LEGACY_DB_FILE.resolve()}?mode=ro", uri=True)
    legacy.row_factory = sqlite3.Row
    with get_pool().connection() as conn:
        import_state = {
            row["source_table"]: int(row["last_source_id"])
            for row in conn.execute(
                "SELECT source_table, last_source_id FROM legacy_import_state"
            ).fetchall()
        }
    transcript_rows = legacy.execute(
        "SELECT id, server_id, time, bot, user, message FROM ai_transcripts WHERE id > ? ORDER BY id",
        (import_state.get("ai_transcripts", 0),),
    ).fetchall()
    alert_rows = legacy.execute(
        "SELECT id, server_id, time, bot, user, message, keyword, audio_file FROM keyword_alerts WHERE id > ? ORDER BY id",
        (import_state.get("keyword_alerts", 0),),
    ).fetchall()

    with get_pool().connection() as conn:
        for row in transcript_rows:
            _upsert_message(
                conn,
                source_event_id=f"legacy-ai:{row['id']}",
                station_id=row["server_id"],
                occurred_at=parse_legacy_datetime(row["time"]),
                speaker_name=row["user"],
                content=row["message"],
                bot_name=row["bot"],
                metadata={"legacy_table": "ai_transcripts", "legacy_id": row["id"]},
            )

        for row in alert_rows:
            occurred_at = parse_legacy_datetime(row["time"])
            audio_asset_id = _register_audio_asset(conn, row["audio_file"])
            existing = conn.execute(
                """
                SELECT id FROM chat_messages
                WHERE station_id = %s AND occurred_at = %s
                  AND speaker_name = %s AND content_raw = %s
                ORDER BY id LIMIT 1
                """,
                (row["server_id"], occurred_at, row["user"], row["message"]),
            ).fetchone()
            if existing:
                message_id = existing["id"]
                if audio_asset_id:
                    conn.execute(
                        "UPDATE chat_messages SET audio_asset_id = COALESCE(audio_asset_id, %s) WHERE id = %s",
                        (audio_asset_id, message_id),
                    )
            else:
                message_id = _upsert_message(
                    conn,
                    source_event_id=f"legacy-alert:{row['id']}",
                    station_id=row["server_id"],
                    occurred_at=occurred_at,
                    speaker_name=row["user"],
                    content=row["message"],
                    bot_name=row["bot"],
                    message_type="alert",
                    audio_asset_id=audio_asset_id,
                    metadata={"legacy_table": "keyword_alerts", "legacy_id": row["id"]},
                )
            conn.execute(
                """
                INSERT INTO keyword_hits (message_id, keyword, matched_text, detected_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (message_id, keyword) DO NOTHING
                """,
                (message_id, row["keyword"], row["keyword"], occurred_at),
            )
        if transcript_rows:
            conn.execute(
                """
                INSERT INTO legacy_import_state (source_table, last_source_id)
                VALUES ('ai_transcripts', %s)
                ON CONFLICT (source_table) DO UPDATE SET
                    last_source_id=GREATEST(legacy_import_state.last_source_id, EXCLUDED.last_source_id),
                    updated_at=NOW()
                """,
                (transcript_rows[-1]["id"],),
            )
        if alert_rows:
            conn.execute(
                """
                INSERT INTO legacy_import_state (source_table, last_source_id)
                VALUES ('keyword_alerts', %s)
                ON CONFLICT (source_table) DO UPDATE SET
                    last_source_id=GREATEST(legacy_import_state.last_source_id, EXCLUDED.last_source_id),
                    updated_at=NOW()
                """,
                (alert_rows[-1]["id"],),
            )
        conn.commit()
    legacy.close()
    return {"transcripts": len(transcript_rows), "alerts": len(alert_rows)}


def _message_access_sql(alias, actor_id, actor_role):
    """Return the SQL predicate that scopes a message to the current user."""
    if actor_role == "admin":
        return "TRUE", []
    return (
        f"EXISTS ("
        f"SELECT 1 FROM user_room_permissions urp "
        f"WHERE urp.username=%s "
        f"AND urp.station_id={alias}.station_id "
        f"AND urp.channel_id=COALESCE({alias}.channel_id, 0))"
    ), [actor_id]


def _build_search(filters, actor_id, actor_role="user", max_limit=100):
    q = normalize_text(filters.get("q"))
    fuzzy = str(filters.get("fuzzy", "false")).lower() in {"1", "true", "yes"}
    if fuzzy and q and len(q) < 3:
        raise ValueError("การค้นหาคำใกล้เคียงต้องมีอย่างน้อย 3 ตัวอักษร")

    try:
        requested_limit = int(filters.get("limit", 50))
    except (TypeError, ValueError):
        requested_limit = 50
    limit = max(1, min(requested_limit, max_limit))
    sort = "oldest" if filters.get("sort") == "oldest" else "latest"

    select_params = [actor_id]
    if q:
        score_sql = "similarity(m.content_normalized, %s)"
        select_params.append(q)
    else:
        score_sql = "NULL::real"

    where = ["m.deleted_at IS NULL"]
    params = []
    access_sql, access_params = _message_access_sql("m", actor_id, actor_role)
    where.append(access_sql)
    params.extend(access_params)
    if q:
        if fuzzy:
            where.append("(m.content_normalized ILIKE %s ESCAPE '!' OR similarity(m.content_normalized, %s) >= %s)")
            params.extend([_like_contains(q), q, float(filters.get("similarity", 0.25))])
        else:
            where.append("m.content_normalized ILIKE %s ESCAPE '!'")
            params.append(_like_contains(q))

    station_ids = filters.get("station_ids") or []
    if station_ids:
        where.append("m.station_id = ANY(%s)")
        params.append(station_ids)
    channel_ids = filters.get("channel_ids") or []
    if channel_ids:
        where.append("m.channel_id = ANY(%s)")
        params.append(channel_ids)
    if filters.get("speaker"):
        where.append("LOWER(m.speaker_name) = LOWER(%s)")
        params.append(str(filters["speaker"]))
    if filters.get("from"):
        where.append("m.occurred_at >= %s")
        params.append(parse_datetime(filters["from"]))
    if filters.get("to"):
        where.append("m.occurred_at <= %s")
        params.append(parse_datetime(filters["to"], end_of_day=True))
    if filters.get("message_types"):
        where.append("m.message_type = ANY(%s)")
        params.append(filters["message_types"])
    if filters.get("has_audio") in (True, "true", "1"):
        where.append("m.audio_asset_id IS NOT NULL")
    if filters.get("has_audio") in (False, "false", "0"):
        where.append("m.audio_asset_id IS NULL")
    if filters.get("min_confidence") not in (None, ""):
        where.append("m.confidence >= %s")
        params.append(float(filters["min_confidence"]))
    if filters.get("keyword"):
        where.append("EXISTS (SELECT 1 FROM keyword_hits khf WHERE khf.message_id=m.id AND khf.keyword ILIKE %s ESCAPE '!')")
        params.append(_like_contains(filters["keyword"]))
    if filters.get("case_status"):
        where.append(
            "EXISTS (SELECT 1 FROM case_messages cm JOIN alert_cases ac ON ac.id=cm.case_id "
            "WHERE cm.message_id=m.id AND ac.status=%s)"
        )
        params.append(filters["case_status"])

    cursor = decode_cursor(filters.get("cursor"))
    if cursor:
        operator = ">" if sort == "oldest" else "<"
        where.append(f"(m.occurred_at, m.id) {operator} (%s, %s)")
        params.extend(cursor)

    direction = "ASC" if sort == "oldest" else "DESC"
    statement = f"""
        SELECT
            m.id, m.station_id, s.name AS station_name,
            m.channel_id, m.channel_name, m.speaker_name, m.bot_name,
            m.message_type, m.content_raw, m.content_corrected,
            COALESCE(m.content_corrected, m.content_raw) AS display_text,
            m.occurred_at, m.ingested_at, m.confidence, m.language,
            m.duration_ms, m.audio_asset_id,
            a.storage_key AS audio_name, a.size_bytes AS audio_size_bytes,
            a.sha256 AS audio_sha256, a.retention_until AS audio_retention_until,
            COALESCE((SELECT array_agg(kh.keyword ORDER BY kh.keyword)
                      FROM keyword_hits kh WHERE kh.message_id=m.id), ARRAY[]::text[]) AS keywords,
            b.tags AS bookmark_tags, b.note AS bookmark_note,
            {score_sql} AS similarity_score
        FROM chat_messages m
        LEFT JOIN stations s ON s.id=m.station_id
        LEFT JOIN audio_assets a ON a.id=m.audio_asset_id AND a.deleted_at IS NULL
        LEFT JOIN message_bookmarks b ON b.message_id=m.id AND b.actor_id=%s
        WHERE {' AND '.join(where)}
        ORDER BY m.occurred_at {direction}, m.id {direction}
        LIMIT %s
    """
    all_params = select_params[1:] + [select_params[0]] + params + [limit + 1]
    return statement, all_params, limit


def search_messages(filters, actor_id="command-console", actor_role="user", max_limit=100):
    statement, params, limit = _build_search(
        filters, actor_id, actor_role=actor_role, max_limit=max_limit
    )
    with get_pool().connection() as conn:
        rows = conn.execute(statement, params).fetchall()
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = encode_cursor(rows[-1]["occurred_at"], rows[-1]["id"]) if has_more and rows else None
    for row in rows:
        row["occurred_at"] = row["occurred_at"].isoformat()
        row["ingested_at"] = row["ingested_at"].isoformat()
        if row.get("audio_retention_until"):
            row["audio_retention_until"] = row["audio_retention_until"].isoformat()
        if row.get("similarity_score") is not None:
            row["similarity_score"] = round(float(row["similarity_score"]), 4)
        row["has_audio"] = bool(row.get("audio_asset_id") and row.get("audio_name"))
    return {"items": rows, "next_cursor": next_cursor, "returned": len(rows), "has_more": has_more}


def get_bootstrap_data(actor_id, actor_role="user"):
    with get_pool().connection() as conn:
        room_permissions = conn.execute(
            """
            SELECT station_id, channel_id, channel_name
            FROM user_room_permissions
            WHERE username=%s
            ORDER BY station_id, channel_id
            """,
            (actor_id,),
        ).fetchall()
        if actor_role == "admin":
            stations = conn.execute("SELECT id, name FROM stations ORDER BY name, id").fetchall()
        else:
            stations = conn.execute(
                """
                SELECT DISTINCT s.id, s.name
                FROM stations s
                JOIN user_room_permissions urp ON urp.station_id=s.id
                WHERE urp.username=%s
                ORDER BY s.name, s.id
                """,
                (actor_id,),
            ).fetchall()

        access_sql, access_params = _message_access_sql("m", actor_id, actor_role)
        speakers = conn.execute(
            f"""
            SELECT m.speaker_name, COUNT(*) AS message_count, MAX(m.occurred_at) AS last_seen
            FROM chat_messages m
            WHERE m.deleted_at IS NULL AND {access_sql}
            GROUP BY m.speaker_name ORDER BY MAX(m.occurred_at) DESC LIMIT 300
            """,
            access_params,
        ).fetchall()
        keywords = conn.execute(
            f"""
            SELECT kh.keyword, COUNT(*) AS hit_count
            FROM keyword_hits kh
            JOIN chat_messages m ON m.id=kh.message_id
            WHERE m.deleted_at IS NULL AND {access_sql}
            GROUP BY kh.keyword ORDER BY COUNT(*) DESC, kh.keyword
            """,
            access_params,
        ).fetchall()
        saved = conn.execute(
            "SELECT id, name, query_json, notify_enabled FROM saved_searches WHERE owner_id=%s ORDER BY name",
            (actor_id,),
        ).fetchall()
    for speaker in speakers:
        speaker["last_seen"] = speaker["last_seen"].isoformat()
    return {
        "stations": stations,
        "speakers": speakers,
        "keywords": keywords,
        "saved_searches": saved,
        "room_permissions": room_permissions,
        "scope": {
            "role": actor_role,
            "all_rooms": actor_role == "admin",
            "room_count": len(room_permissions),
        },
    }


def get_message_context(message_id, before=10, after=10, actor_id="command-console", actor_role="user"):
    before = max(0, min(int(before), 50))
    after = max(0, min(int(after), 50))
    with get_pool().connection() as conn:
        access_sql, access_params = _message_access_sql("m", actor_id, actor_role)
        target = conn.execute(
            f"SELECT m.id, m.station_id, m.channel_id, m.occurred_at "
            f"FROM chat_messages m WHERE m.id=%s AND m.deleted_at IS NULL AND {access_sql}",
            (message_id, *access_params),
        ).fetchone()
        if not target:
            return None
        previous = conn.execute(
            f"""
            SELECT id, speaker_name, COALESCE(content_corrected, content_raw) AS display_text,
                   occurred_at, message_type, audio_asset_id IS NOT NULL AS has_audio
            FROM chat_messages m
            WHERE m.deleted_at IS NULL AND m.station_id IS NOT DISTINCT FROM %s
              AND m.channel_id IS NOT DISTINCT FROM %s
              AND (m.occurred_at, m.id) < (%s, %s)
              AND {access_sql}
            ORDER BY m.occurred_at DESC, m.id DESC LIMIT %s
            """,
            (target["station_id"], target["channel_id"], target["occurred_at"], target["id"], *access_params, before),
        ).fetchall()
        current = conn.execute(
            f"""
            SELECT id, speaker_name, COALESCE(content_corrected, content_raw) AS display_text,
                   occurred_at, message_type, audio_asset_id IS NOT NULL AS has_audio
            FROM chat_messages m WHERE id=%s AND deleted_at IS NULL AND {access_sql}
            """,
            (message_id, *access_params),
        ).fetchone()
        following = conn.execute(
            f"""
            SELECT id, speaker_name, COALESCE(content_corrected, content_raw) AS display_text,
                   occurred_at, message_type, audio_asset_id IS NOT NULL AS has_audio
            FROM chat_messages m
            WHERE m.deleted_at IS NULL AND m.station_id IS NOT DISTINCT FROM %s
              AND m.channel_id IS NOT DISTINCT FROM %s
              AND (m.occurred_at, m.id) > (%s, %s)
              AND {access_sql}
            ORDER BY m.occurred_at ASC, m.id ASC LIMIT %s
            """,
            (target["station_id"], target["channel_id"], target["occurred_at"], target["id"], *access_params, after),
        ).fetchall()
    items = list(reversed(previous)) + [current] + following
    for item in items:
        item["occurred_at"] = item["occurred_at"].isoformat()
        item["selected"] = item["id"] == int(message_id)
    return {"items": items}


def get_audio_asset(message_id, actor_id="command-console", actor_role="user"):
    access_sql, access_params = _message_access_sql("m", actor_id, actor_role)
    with get_pool().connection() as conn:
        return conn.execute(
            f"""
            SELECT a.storage_key, a.mime_type, a.sha256
            FROM chat_messages m JOIN audio_assets a ON a.id=m.audio_asset_id
            WHERE m.id=%s AND m.deleted_at IS NULL AND a.deleted_at IS NULL AND {access_sql}
            """,
            (message_id, *access_params),
        ).fetchone()


def resolve_audio_path(storage_key):
    path = (RECORDS_DIR / Path(storage_key).name).resolve()
    if path.parent != RECORDS_DIR or not path.is_file():
        return None
    return path


def correct_transcript(message_id, corrected_text, reason, editor_id, actor_role="user"):
    normalized = normalize_text(corrected_text)
    if not normalized:
        raise ValueError("ข้อความแก้ไขต้องไม่ว่าง")
    with get_pool().connection() as conn:
        access_sql, access_params = _message_access_sql("m", editor_id, actor_role)
        current = conn.execute(
            f"SELECT m.id FROM chat_messages m WHERE m.id=%s AND m.deleted_at IS NULL AND {access_sql} FOR UPDATE",
            (message_id, *access_params),
        ).fetchone()
        if not current:
            raise ValueError("ไม่มีสิทธิ์เข้าถึงข้อความในห้องนี้")
        revision = conn.execute(
            "SELECT COALESCE(MAX(revision_no), 0) + 1 AS next_no FROM transcript_revisions WHERE message_id=%s",
            (message_id,),
        ).fetchone()["next_no"]
        conn.execute(
            """
            INSERT INTO transcript_revisions (message_id, revision_no, corrected_text, reason, editor_id)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (message_id, revision, corrected_text, reason, editor_id),
        )
        conn.execute(
            "UPDATE chat_messages SET content_corrected=%s, content_normalized=%s WHERE id=%s",
            (corrected_text, normalized, message_id),
        )
        conn.commit()
    return {"message_id": int(message_id), "revision_no": revision, "corrected_text": corrected_text}


def upsert_bookmark(actor_id, message_id, tags, note, actor_role="user"):
    cleaned_tags = sorted({str(tag).strip()[:50] for tag in tags or [] if str(tag).strip()})[:20]
    with get_pool().connection() as conn:
        access_sql, access_params = _message_access_sql("m", actor_id, actor_role)
        visible = conn.execute(
            f"SELECT 1 FROM chat_messages m WHERE m.id=%s AND m.deleted_at IS NULL AND {access_sql}",
            (message_id, *access_params),
        ).fetchone()
        if not visible:
            raise ValueError("ไม่มีสิทธิ์เข้าถึงข้อความในห้องนี้")
        row = conn.execute(
            """
            INSERT INTO message_bookmarks (actor_id, message_id, tags, note)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (actor_id, message_id) DO UPDATE SET
                tags=EXCLUDED.tags, note=EXCLUDED.note, updated_at=NOW()
            RETURNING actor_id, message_id, tags, note, updated_at
            """,
            (actor_id, message_id, cleaned_tags, note),
        ).fetchone()
        conn.commit()
    row["updated_at"] = row["updated_at"].isoformat()
    return row


def create_case(actor_id, title, severity, message_ids, note=None, actor_role="user"):
    if severity not in {"low", "medium", "high", "critical"}:
        raise ValueError("severity ไม่ถูกต้อง")
    unique_ids = sorted({int(item) for item in message_ids})
    if not title or not unique_ids:
        raise ValueError("ต้องมีชื่อเหตุการณ์และข้อความอย่างน้อยหนึ่งรายการ")
    with get_pool().connection() as conn:
        access_sql, access_params = _message_access_sql("m", actor_id, actor_role)
        visible = conn.execute(
            f"SELECT COUNT(*) AS count FROM chat_messages m "
            f"WHERE m.id = ANY(%s) AND m.deleted_at IS NULL AND {access_sql}",
            (unique_ids, *access_params),
        ).fetchone()["count"]
        if int(visible) != len(unique_ids):
            raise ValueError("ไม่มีสิทธิ์เข้าถึงข้อความอย่างน้อยหนึ่งรายการ")
        case = conn.execute(
            "INSERT INTO alert_cases (title, severity, created_by) VALUES (%s, %s, %s) RETURNING id, title, status, severity, opened_at",
            (title.strip()[:300], severity, actor_id),
        ).fetchone()
        for message_id in unique_ids:
            conn.execute(
                "INSERT INTO case_messages (case_id, message_id, added_by, note) VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING",
                (case["id"], message_id, actor_id, note),
            )
        conn.commit()
    case["opened_at"] = case["opened_at"].isoformat()
    return case


def save_search(actor_id, name, query_data, notify_enabled=False):
    if not name or len(name.strip()) > 120:
        raise ValueError("ชื่อชุดค้นหาไม่ถูกต้อง")
    allowed_keys = {
        "q", "fuzzy", "station_ids", "channel_ids", "speaker", "from", "to",
        "message_types", "has_audio", "min_confidence", "keyword", "case_status", "sort",
    }
    cleaned = {key: value for key, value in dict(query_data or {}).items() if key in allowed_keys}
    with get_pool().connection() as conn:
        row = conn.execute(
            """
            INSERT INTO saved_searches (owner_id, name, query_json, notify_enabled)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (owner_id, name) DO UPDATE SET
                query_json=EXCLUDED.query_json,
                notify_enabled=EXCLUDED.notify_enabled,
                updated_at=NOW()
            RETURNING id, name, query_json, notify_enabled, updated_at
            """,
            (actor_id, name.strip(), Jsonb(cleaned), bool(notify_enabled)),
        ).fetchone()
        conn.commit()
    row["updated_at"] = row["updated_at"].isoformat()
    return row


def audit_event(actor_id, action, target_type=None, target_id=None, ip=None, details=None):
    try:
        with get_pool().connection() as conn:
            conn.execute(
                """
                INSERT INTO audit_events (actor_id, action, target_type, target_id, ip, details)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (actor_id, action, target_type, str(target_id) if target_id is not None else None, ip, Jsonb(details or {})),
            )
            conn.commit()
    except Exception:
        # Audit must not turn a read-only screen into an outage; database monitoring catches failures.
        pass
