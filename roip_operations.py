"""Operational monitoring, background maintenance and reporting for ROIP."""

import csv
import io
import json
import os
import shutil
import threading
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import psutil
import redis
from psycopg.types.json import Jsonb

from roip_search.db import DATABASE_URL, RECORDS_DIR, database_health, get_pool


REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
STATUS_CHECK_SECONDS = max(5, int(os.getenv("STATUS_CHECK_SECONDS", "15")))
RETENTION_MINUTES = max(5, int(os.getenv("AUDIO_RETENTION_CHECK_MINUTES", "60")))
RETENTION_DAYS = max(1, int(os.getenv("AUDIO_RETENTION_DAYS", "30")))
STORAGE_WARN_PERCENT = max(1, min(99, int(os.getenv("AUDIO_STORAGE_WARN_PERCENT", "80"))))
QUEUE_KEY = "roip:operations:queue"
CACHE_TTL_SECONDS = max(STATUS_CHECK_SECONDS * 3, 60)


def _utc_iso(value=None):
    return (value or datetime.now(timezone.utc)).isoformat()


class OperationalWorker:
    """A small Redis-backed worker kept intentionally dependency-light for Docker installs."""

    def __init__(self, load_servers, probe_station, emit_event, log_event):
        self.load_servers = load_servers
        self.probe_station = probe_station
        self.emit_event = emit_event
        self.log_event = log_event
        self._redis = None
        self._started = False

    def redis_client(self):
        if self._redis is None:
            self._redis = redis.Redis.from_url(
                REDIS_URL, decode_responses=True, socket_connect_timeout=2, socket_timeout=2
            )
        return self._redis

    def redis_available(self):
        try:
            return bool(self.redis_client().ping())
        except Exception:
            return False

    def cache_get_json(self, key, default=None):
        try:
            value = self.redis_client().get(key)
            return json.loads(value) if value else default
        except Exception:
            return default

    def cache_set_json(self, key, value, ttl=CACHE_TTL_SECONDS):
        try:
            self.redis_client().set(key, json.dumps(value, ensure_ascii=False), ex=ttl)
        except Exception:
            pass

    def enqueue(self, task, payload=None):
        job = {"task": task, "payload": payload or {}, "queued_at": _utc_iso()}
        try:
            self.redis_client().rpush(QUEUE_KEY, json.dumps(job, ensure_ascii=False))
            return True
        except Exception:
            # Keep monitoring available in a degraded Redis state.
            self._run_job(job)
            return False

    def start(self):
        if self._started:
            return
        self._started = True
        threading.Thread(target=self._scheduler_loop, name="roip-ops-scheduler", daemon=True).start()
        threading.Thread(target=self._worker_loop, name="roip-ops-worker", daemon=True).start()

    def _scheduler_loop(self):
        next_retention = 0.0
        while True:
            self.enqueue("monitor_stations")
            now = time.monotonic()
            if now >= next_retention:
                self.enqueue("cleanup_audio")
                next_retention = now + RETENTION_MINUTES * 60
            time.sleep(STATUS_CHECK_SECONDS)

    def _worker_loop(self):
        while True:
            try:
                item = self.redis_client().blpop(QUEUE_KEY, timeout=5)
                if not item:
                    continue
                _, raw = item
                self._run_job(json.loads(raw))
            except Exception:
                time.sleep(3)

    def _run_job(self, job):
        task = job.get("task")
        if task == "monitor_stations":
            self.monitor_stations()
        elif task == "cleanup_audio":
            self.cleanup_audio()

    def monitor_stations(self):
        previous = self.cache_get_json("roip:health:stations", []) or []
        previous_by_id = {str(item.get("id")): item for item in previous}
        stations = []
        for server in self.load_servers():
            station_id = server.get("id")
            try:
                result = self.probe_station(server) or {}
                online = bool(result.get("online"))
                detail = result.get("detail") or {}
            except Exception as exc:
                online, detail = False, {"error": str(exc)[:300]}
            item = {
                "id": station_id,
                "name": server.get("name") or f"Station {station_id}",
                "online": online,
                "detail": detail,
                "checked_at": _utc_iso(),
            }
            stations.append(item)
            before = previous_by_id.get(str(station_id))
            if before is not None and bool(before.get("online")) != online:
                status = "online" if online else "offline"
                self._record_station_transition(item, "online" if before.get("online") else "offline")
                self.log_event(station_id, f"{'🟢' if online else '🔴'} สถานี [{item['name']}] {status.upper()}")
                self.emit_event("station:status", item)
                self.emit_event("system:alert", {
                    "level": "info" if online else "critical",
                    "message": f"สถานี {item['name']} {status.upper()}",
                    "station_id": station_id,
                    "at": item["checked_at"],
                })
        self.cache_set_json("roip:health:stations", stations)
        return stations

    def _record_station_transition(self, station, previous_status):
        try:
            with get_pool().connection() as conn:
                conn.execute(
                    """
                    INSERT INTO station_health_events
                        (station_id, station_name, status, previous_status, detail)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        station.get("id"), station.get("name"),
                        "online" if station.get("online") else "offline",
                        previous_status, Jsonb(station.get("detail") or {}),
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO audit_events (actor_id, action, target_type, target_id, details)
                    VALUES ('system-monitor', %s, 'station', %s, %s)
                    """,
                    (
                        "station.online" if station.get("online") else "station.offline",
                        str(station.get("id")), Jsonb(station),
                    ),
                )
                conn.commit()
        except Exception:
            pass

    def cleanup_audio(self):
        cutoff = time.time() - RETENTION_DAYS * 86400
        deleted_files, deleted_bytes = [], 0
        records_root = RECORDS_DIR.resolve()
        allowed_extensions = {".wav", ".mp3", ".ogg", ".flac", ".m4a", ".aac"}
        try:
            for path in records_root.rglob("*"):
                if not path.is_file() or path.suffix.lower() not in allowed_extensions:
                    continue
                try:
                    resolved = path.resolve()
                    if records_root not in resolved.parents or path.stat().st_mtime >= cutoff:
                        continue
                    size = path.stat().st_size
                    path.unlink()
                    deleted_files.append(str(path.relative_to(records_root)))
                    deleted_bytes += size
                except OSError:
                    continue
            if deleted_files:
                with get_pool().connection() as conn:
                    conn.execute(
                        "UPDATE audio_assets SET deleted_at=NOW() WHERE storage_key = ANY(%s) AND deleted_at IS NULL",
                        (deleted_files,),
                    )
                    conn.execute(
                        """
                        INSERT INTO audit_events (actor_id, action, target_type, details)
                        VALUES ('retention-worker', 'audio.retention.cleanup', 'audio_asset', %s)
                        """,
                        (Jsonb({"retention_days": RETENTION_DAYS, "files": len(deleted_files), "bytes": deleted_bytes}),),
                    )
                    conn.commit()
            result = {
                "completed_at": _utc_iso(), "retention_days": RETENTION_DAYS,
                "deleted_files": len(deleted_files), "deleted_bytes": deleted_bytes,
            }
            self.cache_set_json("roip:storage:last_cleanup", result, ttl=RETENTION_MINUTES * 120)
            if deleted_files:
                self.emit_event("storage:cleanup", result)
            return result
        except Exception as exc:
            return {"completed_at": _utc_iso(), "error": str(exc)[:300]}

    def health_snapshot(self):
        disk = shutil.disk_usage(str(RECORDS_DIR))
        records_bytes, record_files = 0, 0
        try:
            for path in RECORDS_DIR.rglob("*"):
                if path.is_file():
                    record_files += 1
                    records_bytes += path.stat().st_size
        except OSError:
            pass
        stations = self.cache_get_json("roip:health:stations", []) or []
        return {
            "generated_at": _utc_iso(),
            "cpu": {"percent": psutil.cpu_percent(interval=0.05), "cores": psutil.cpu_count() or 1},
            "memory": {"percent": psutil.virtual_memory().percent, "total_bytes": psutil.virtual_memory().total},
            "disk": {
                "percent": round(disk.used / disk.total * 100, 1) if disk.total else 0,
                "free_bytes": disk.free, "total_bytes": disk.total,
                "warning": (disk.used / disk.total * 100) >= STORAGE_WARN_PERCENT if disk.total else False,
            },
            "database": {"online": database_health(), "engine": "PostgreSQL"},
            "redis": {"online": self.redis_available(), "role": "cache + background queue"},
            "audio_storage": {
                "files": record_files, "bytes": records_bytes, "retention_days": RETENTION_DAYS,
                "last_cleanup": self.cache_get_json("roip:storage:last_cleanup", {}),
            },
            "stations": stations,
            "station_summary": {
                "total": len(stations), "online": sum(1 for item in stations if item.get("online")),
                "offline": sum(1 for item in stations if not item.get("online")),
            },
        }


def parse_report_dates(start_text, end_text):
    today = date.today()
    try:
        start = date.fromisoformat(start_text) if start_text else today - timedelta(days=6)
        end = date.fromisoformat(end_text) if end_text else today
    except ValueError as exc:
        raise ValueError("วันที่ต้องอยู่ในรูปแบบ YYYY-MM-DD") from exc
    if end < start or (end - start).days > 366:
        raise ValueError("เลือกรายงานได้ไม่เกิน 366 วัน และวันสิ้นสุดต้องไม่ก่อนวันเริ่ม")
    return start, end


def build_daily_report(start_text="", end_text="", station_id=None):
    start, end = parse_report_dates(start_text, end_text)
    station_id = int(station_id) if station_id not in (None, "", "all") else None
    with get_pool().connection() as conn:
        rows = conn.execute(
            """
            WITH days AS (
                SELECT generate_series(%s::date, %s::date, interval '1 day')::date AS day
            ), chat AS (
                SELECT occurred_at::date AS day,
                    COUNT(*) FILTER (WHERE message_type = 'text_chat') AS messages,
                    COUNT(*) FILTER (WHERE message_type IN ('voice_transcript', 'ptt', 'tts')) AS voice,
                    COUNT(*) FILTER (WHERE audio_asset_id IS NOT NULL) AS audio
                FROM chat_messages
                WHERE deleted_at IS NULL AND occurred_at >= %s::date AND occurred_at < (%s::date + interval '1 day')
                    AND (%s::integer IS NULL OR station_id = %s::integer)
                GROUP BY occurred_at::date
            ), events AS (
                SELECT occurred_at::date AS day, COUNT(*) AS events
                FROM audit_events
                WHERE occurred_at >= %s::date AND occurred_at < (%s::date + interval '1 day')
                    AND (%s::integer IS NULL OR COALESCE(details->>'station_id', '') = %s::text)
                GROUP BY occurred_at::date
            )
            SELECT days.day, COALESCE(chat.messages, 0) AS messages, COALESCE(chat.voice, 0) AS voice,
                COALESCE(chat.audio, 0) AS audio, COALESCE(events.events, 0) AS events
            FROM days LEFT JOIN chat ON chat.day=days.day LEFT JOIN events ON events.day=days.day
            ORDER BY days.day
            """,
            (start, end, start, end, station_id, station_id, start, end, station_id, station_id),
        ).fetchall()
    daily = [{"date": row["day"].isoformat(), **{key: int(row[key]) for key in ("messages", "voice", "audio", "events")}} for row in rows]
    totals = {key: sum(row[key] for row in daily) for key in ("messages", "voice", "audio", "events")}
    return {"from": start.isoformat(), "to": end.isoformat(), "station_id": station_id, "daily": daily, "totals": totals}


def report_csv(report):
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(["date", "messages", "voice_events", "audio_records", "audit_events"])
    for row in report["daily"]:
        writer.writerow([row["date"], row["messages"], row["voice"], row["audio"], row["events"]])
    writer.writerow(["TOTAL", report["totals"]["messages"], report["totals"]["voice"], report["totals"]["audio"], report["totals"]["events"]])
    return buffer.getvalue().encode("utf-8-sig")
