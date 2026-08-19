import csv
import io
import time

from flask import Blueprint, jsonify, redirect, render_template, request, send_file, session, url_for

from .db import (
    audit_event,
    correct_transcript,
    create_case,
    get_audio_asset,
    get_bootstrap_data,
    get_message_context,
    resolve_audio_path,
    save_search,
    search_messages,
    upsert_bookmark,
)
from .utils import parse_csv_ints


chat_search_bp = Blueprint("chat_search", __name__)
ALLOWED_TYPES = {"voice_transcript", "text_chat", "tts", "ptt", "alert"}
ALLOWED_CASE_STATUSES = {"open", "acknowledged", "investigating", "closed"}


def _actor_id():
    return str(session.get("operator_id") or "command-console")


def _actor_role():
    return str(session.get("role") or "user")


def _filters_from_request():
    message_types = [
        item for item in request.args.get("types", "").split(",")
        if item in ALLOWED_TYPES
    ]
    return {
        "q": request.args.get("q", "")[:500],
        "fuzzy": request.args.get("fuzzy", "false"),
        "similarity": request.args.get("similarity", "0.25"),
        "station_ids": parse_csv_ints(request.args.get("station_ids")),
        "channel_ids": parse_csv_ints(request.args.get("channel_ids")),
        "speaker": request.args.get("speaker", "")[:200],
        "from": request.args.get("from", ""),
        "to": request.args.get("to", ""),
        "message_types": message_types,
        "has_audio": request.args.get("has_audio", ""),
        "min_confidence": request.args.get("min_confidence", ""),
        "keyword": request.args.get("keyword", "")[:200],
        "case_status": (
            request.args.get("case_status", "")
            if request.args.get("case_status", "") in ALLOWED_CASE_STATUSES
            else ""
        ),
        "sort": request.args.get("sort", "latest"),
        "cursor": request.args.get("cursor", ""),
        "limit": request.args.get("limit", "50"),
    }


@chat_search_bp.route("/chat-search")
def chat_search_page():
    if not session.get("logged_in") or session.get("role") not in ("admin", "user"):
        return redirect(url_for("index"))
    return render_template("chat_search.html")


@chat_search_bp.route("/api/chat/bootstrap")
def chat_bootstrap():
    return jsonify(get_bootstrap_data(_actor_id(), _actor_role()))


@chat_search_bp.route("/api/chat/search")
def chat_search():
    started = time.perf_counter()
    try:
        filters = _filters_from_request()
        result = search_messages(filters, actor_id=_actor_id(), actor_role=_actor_role())
    except (ValueError, TypeError) as exc:
        return jsonify({"status": "error", "error": str(exc)}), 400
    result["took_ms"] = round((time.perf_counter() - started) * 1000, 1)
    audit_event(
        _actor_id(),
        "chat.search",
        ip=request.remote_addr,
        details={
            "q_length": len(filters.get("q") or ""),
            "station_ids": filters.get("station_ids"),
            "returned": result["returned"],
        },
    )
    return jsonify(result)


@chat_search_bp.route("/api/chat/messages/<int:message_id>/context")
def chat_context(message_id):
    try:
        result = get_message_context(
            message_id,
            before=request.args.get("before", 10),
            after=request.args.get("after", 10),
            actor_id=_actor_id(),
            actor_role=_actor_role(),
        )
    except (TypeError, ValueError) as exc:
        return jsonify({"status": "error", "error": str(exc)}), 400
    if not result:
        return jsonify({"status": "error", "error": "ไม่พบข้อความ"}), 404
    return jsonify(result)


@chat_search_bp.route("/api/chat/messages/<int:message_id>/audio")
def chat_audio(message_id):
    asset = get_audio_asset(message_id, _actor_id(), _actor_role())
    if not asset:
        return jsonify({"status": "error", "error": "ไม่มีไฟล์เสียง"}), 404
    path = resolve_audio_path(asset["storage_key"])
    if not path:
        return jsonify({"status": "error", "error": "ไฟล์เสียงถูกย้ายหรือหมดอายุแล้ว"}), 410
    audit_event(
        _actor_id(), "chat.audio.view", "chat_message", message_id,
        ip=request.remote_addr, details={"sha256": asset["sha256"]},
    )
    return send_file(
        path,
        mimetype=asset["mime_type"],
        conditional=True,
        etag=asset["sha256"],
        download_name=path.name,
    )


@chat_search_bp.route("/api/chat/messages/<int:message_id>/correction", methods=["PATCH"])
def chat_correction(message_id):
    data = request.get_json(silent=True) or {}
    try:
        result = correct_transcript(
            message_id,
            str(data.get("corrected_text") or "")[:10000],
            str(data.get("reason") or "")[:500],
            _actor_id(),
            _actor_role(),
        )
    except ValueError as exc:
        return jsonify({"status": "error", "error": str(exc)}), 400
    if not result:
        return jsonify({"status": "error", "error": "ไม่พบข้อความ"}), 404
    audit_event(_actor_id(), "chat.transcript.correct", "chat_message", message_id, request.remote_addr)
    return jsonify({"status": "success", **result})


@chat_search_bp.route("/api/chat/bookmarks", methods=["POST"])
def chat_bookmark():
    data = request.get_json(silent=True) or {}
    try:
        message_id = int(data.get("message_id"))
        result = upsert_bookmark(
            _actor_id(),
            message_id,
            data.get("tags") or [],
            str(data.get("note") or "")[:2000],
            _actor_role(),
        )
    except (TypeError, ValueError) as exc:
        return jsonify({"status": "error", "error": str(exc)}), 400
    audit_event(_actor_id(), "chat.bookmark.upsert", "chat_message", message_id, request.remote_addr)
    return jsonify({"status": "success", "bookmark": result})


@chat_search_bp.route("/api/chat/cases", methods=["POST"])
def chat_case_create():
    data = request.get_json(silent=True) or {}
    try:
        result = create_case(
            _actor_id(),
            str(data.get("title") or ""),
            str(data.get("severity") or "medium"),
            data.get("message_ids") or [],
            str(data.get("note") or "")[:2000],
            _actor_role(),
        )
    except (TypeError, ValueError) as exc:
        return jsonify({"status": "error", "error": str(exc)}), 400
    audit_event(_actor_id(), "chat.case.create", "alert_case", result["id"], request.remote_addr)
    return jsonify({"status": "success", "case": result}), 201


@chat_search_bp.route("/api/chat/saved-searches", methods=["POST"])
def chat_saved_search():
    data = request.get_json(silent=True) or {}
    try:
        result = save_search(
            _actor_id(),
            str(data.get("name") or ""),
            data.get("query") or {},
            bool(data.get("notify_enabled", False)),
        )
    except ValueError as exc:
        return jsonify({"status": "error", "error": str(exc)}), 400
    audit_event(_actor_id(), "chat.saved_search.upsert", "saved_search", result["id"], request.remote_addr)
    return jsonify({"status": "success", "saved_search": result})


@chat_search_bp.route("/api/chat/export.csv")
def chat_export_csv():
    try:
        filters = _filters_from_request()
        filters["cursor"] = ""
        filters["limit"] = "10000"
        result = search_messages(
            filters,
            actor_id=_actor_id(),
            actor_role=_actor_role(),
            max_limit=10000,
        )
    except (ValueError, TypeError) as exc:
        return jsonify({"status": "error", "error": str(exc)}), 400

    text_buffer = io.StringIO(newline="")
    writer = csv.writer(text_buffer)
    writer.writerow([
        "message_id", "occurred_at_utc", "station", "channel", "speaker",
        "type", "message", "keywords", "has_audio", "audio_sha256",
    ])
    for item in result["items"]:
        writer.writerow([
            item["id"], item["occurred_at"], item.get("station_name"),
            item.get("channel_name") or item.get("channel_id"), item["speaker_name"],
            item["message_type"], item["display_text"], ", ".join(item["keywords"]),
            item["has_audio"], item.get("audio_sha256"),
        ])
    payload = io.BytesIO(text_buffer.getvalue().encode("utf-8-sig"))
    audit_event(
        _actor_id(), "chat.export.csv", "chat_search", None,
        request.remote_addr, {"row_count": result["returned"]},
    )
    return send_file(
        payload,
        mimetype="text/csv; charset=utf-8",
        as_attachment=True,
        download_name="ROIP_CHAT_SEARCH.csv",
    )
