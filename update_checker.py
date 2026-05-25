from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

GITHUB_RELEASES_API = "https://api.github.com/repos/aqua5230/usage/releases/latest"


@dataclass(frozen=True, slots=True)
class ReleaseInfo:
    version: str
    html_url: str
    body: str


@dataclass(frozen=True, slots=True)
class ReleaseCheckResult:
    release: ReleaseInfo | None
    failed: bool = False


def _parse_version(version: str) -> tuple[int, int, int] | None:
    parts = version.split(".")
    if len(parts) != 3:
        return None
    parsed: list[int] = []
    for part in parts:
        if not part.isdigit():
            return None
        parsed.append(int(part))
    return (parsed[0], parsed[1], parsed[2])


def compare_versions(a: str, b: str) -> int:
    parsed_a = _parse_version(a)
    parsed_b = _parse_version(b)
    if parsed_a is None or parsed_b is None:
        raise ValueError("versions must use MAJOR.MINOR.PATCH numeric format")
    if parsed_a < parsed_b:
        return -1
    if parsed_a > parsed_b:
        return 1
    return 0


def check_latest_release(current_version: str, *, timeout: float = 5.0) -> ReleaseInfo | None:
    return check_latest_release_result(current_version, timeout=timeout).release


def check_latest_release_result(
    current_version: str,
    *,
    timeout: float = 5.0,
) -> ReleaseCheckResult:
    if _parse_version(current_version) is None:
        return ReleaseCheckResult(None)

    request = urllib.request.Request(
        GITHUB_RELEASES_API,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"usage/{current_version}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        urllib.error.URLError,
        urllib.error.HTTPError,
    ):
        return ReleaseCheckResult(None, failed=True)

    release = _release_from_payload(payload)
    if release is None:
        return ReleaseCheckResult(None)
    try:
        if compare_versions(current_version, release.version) >= 0:
            return ReleaseCheckResult(None)
    except ValueError:
        return ReleaseCheckResult(None)
    return ReleaseCheckResult(release)


def _release_from_payload(payload: Any) -> ReleaseInfo | None:
    if not isinstance(payload, dict):
        return None

    tag_name = payload.get("tag_name")
    html_url = payload.get("html_url")
    body = payload.get("body", "")
    if not isinstance(tag_name, str) or not isinstance(html_url, str):
        return None
    if not isinstance(body, str):
        body = ""

    version = tag_name.removeprefix("v")
    if _parse_version(version) is None:
        return None
    return ReleaseInfo(version=version, html_url=html_url, body=body)
