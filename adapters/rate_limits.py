import json
import os
from datetime import datetime, timezone

from .types import RateLimits

STATUS_FILE = os.path.expanduser("~/.claude/usage-status.json")
LEGACY_STATUS_FILE = os.path.expanduser("~/.claude/usag-status.json")
TT_STATUS_FILE = os.path.expanduser("~/.claude/tt-status.json")


def _read_status() -> dict | None:
    for path in (STATUS_FILE, LEGACY_STATUS_FILE, TT_STATUS_FILE):
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
    return None


def load_rate_limits() -> RateLimits | None:
    data = _read_status()
    if data is None:
        return None

    rl = data.get("rate_limits") or {}
    five = rl.get("five_hour") or {}
    seven = rl.get("seven_day") or {}

    now_ts = datetime.now(timezone.utc).timestamp()
    five_pct = five.get("used_percentage")
    five_reset = five.get("resets_at")
    if five_reset and five_reset < now_ts:
        five_pct = 0.0

    seven_pct = seven.get("used_percentage")
    seven_reset = seven.get("resets_at")
    if seven_reset and seven_reset < now_ts:
        seven_pct = 0.0

    model_info = data.get("model") or {}
    model_name = model_info.get("display_name") or model_info.get("id") or ""

    if five_pct is None and seven_pct is None and not model_name:
        return None

    return RateLimits(
        five_hour_pct=five_pct,
        five_hour_resets_at=five_reset,
        seven_day_pct=seven_pct,
        seven_day_resets_at=seven_reset,
        model=model_name,
        updated_at=data.get("_received_at", ""),
    )
