from __future__ import annotations

import os
from collections.abc import Mapping


def detect_lang(env: Mapping[str, str] | None = None) -> str:
    source = os.environ if env is None else env
    raw = ""
    for key in ("USAGE_LANG", "TT_LANG", "LANG"):
        value = source.get(key, "").strip()
        if value:
            raw = value
            break

    code = raw.split(".")[0].replace("_", "-")
    normalized = code.lower()

    if normalized in {"zh-tw", "zh-hk"}:
        return "zh-TW"
    if normalized in {"zh-cn", "zh-sg", "zh"}:
        return "zh-CN"
    if normalized.startswith("en"):
        return "en"
    if normalized.startswith("ja"):
        return "ja"
    if normalized.startswith("ko"):
        return "ko"
    return "en"
