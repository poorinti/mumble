import base64
import binascii
import json
import re
import unicodedata
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


BANGKOK = ZoneInfo("Asia/Bangkok")
ZERO_WIDTH_RE = re.compile(r"[\u200b-\u200d\ufeff]")
WHITESPACE_RE = re.compile(r"\s+")
RADIO_CODE_RE = re.compile(r"(?<!\w)ว\s*[.]?\s*(\d+)", re.IGNORECASE)


def normalize_text(value):
    """Create a safe, deterministic search representation for Thai text."""
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = ZERO_WIDTH_RE.sub("", text)
    text = RADIO_CODE_RE.sub(lambda match: f"ว{match.group(1)}", text)
    text = WHITESPACE_RE.sub(" ", text).strip().casefold()
    return text


def parse_csv_ints(value, maximum=100):
    if not value:
        return []
    result = []
    for item in str(value).split(","):
        item = item.strip()
        if not item:
            continue
        number = int(item)
        if number not in result:
            result.append(number)
        if len(result) >= maximum:
            break
    return result


def parse_datetime(value, end_of_day=False):
    if not value:
        return None
    raw = str(value).strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        if len(raw) == 10 and end_of_day:
            parsed = parsed.replace(hour=23, minute=59, second=59, microsecond=999999)
        parsed = parsed.replace(tzinfo=BANGKOK)
    return parsed.astimezone(timezone.utc)


def parse_legacy_datetime(value):
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=BANGKOK)
    return parsed.astimezone(timezone.utc)


def encode_cursor(occurred_at, message_id):
    payload = json.dumps(
        {"at": occurred_at.astimezone(timezone.utc).isoformat(), "id": int(message_id)},
        separators=(",", ":"),
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def decode_cursor(value):
    if not value:
        return None
    try:
        padding = "=" * (-len(value) % 4)
        payload = json.loads(base64.urlsafe_b64decode(value + padding).decode("utf-8"))
        return parse_datetime(payload["at"]), int(payload["id"])
    except (binascii.Error, UnicodeDecodeError, ValueError, TypeError, KeyError) as exc:
        raise ValueError("cursor การค้นหาไม่ถูกต้อง") from exc
