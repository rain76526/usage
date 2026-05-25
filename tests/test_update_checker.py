from __future__ import annotations

import urllib.error
import urllib.request
from typing import Any

import pytest

import update_checker


class FakeResponse:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.body


def test_compare_versions_orders_numeric_versions() -> None:
    assert update_checker.compare_versions("0.10.1", "0.10.2") == -1
    assert update_checker.compare_versions("0.10.1", "0.10.1") == 0
    assert update_checker.compare_versions("0.9.10", "0.10.0") == -1


def test_check_latest_release_parses_newer_release(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_urlopen(request: Any, *, timeout: float) -> FakeResponse:
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse(
            b'{"tag_name":"v0.10.2","html_url":"https://example.test/release","body":"notes"}'
        )

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    release = update_checker.check_latest_release("0.10.1", timeout=1.5)

    assert release == update_checker.ReleaseInfo(
        version="0.10.2",
        html_url="https://example.test/release",
        body="notes",
    )
    assert captured["timeout"] == 1.5
    assert captured["request"].headers["User-agent"] == "usage/0.10.1"


def test_check_latest_release_returns_none_when_remote_is_not_newer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda request, *, timeout: FakeResponse(
            b'{"tag_name":"v0.10.1","html_url":"https://example.test/release","body":"notes"}'
        ),
    )

    assert update_checker.check_latest_release("0.10.1") is None
    assert update_checker.check_latest_release("0.10.2") is None


@pytest.mark.parametrize(
    "response_body",
    [
        b"not json",
        b'{"tag_name":"v0.10.2-beta.1","html_url":"https://example.test/release"}',
    ],
)
def test_check_latest_release_returns_none_for_invalid_payloads(
    monkeypatch: pytest.MonkeyPatch,
    response_body: bytes,
) -> None:
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda request, *, timeout: FakeResponse(response_body),
    )

    assert update_checker.check_latest_release("0.10.1") is None


def test_check_latest_release_returns_none_for_network_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_urlopen(request: Any, *, timeout: float) -> FakeResponse:
        raise urllib.error.URLError("offline")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    assert update_checker.check_latest_release("0.10.1") is None
    assert update_checker.check_latest_release_result("0.10.1").failed is True
