from __future__ import annotations

import time
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

import windows_widget
from history_loader import UsageEntry


def _entry(session_id: str, year: int, month: int, cost: float | None) -> UsageEntry:
    ts = datetime(year, month, 15, 12, 0, 0, tzinfo=UTC)
    return UsageEntry(
        timestamp=ts,
        session_id=session_id,
        message_id="msg1",
        request_id="req1",
        model="claude-sonnet-4-6",
        input_tokens=100,
        output_tokens=50,
        cache_creation_tokens=0,
        cache_read_tokens=0,
        cost_usd=cost,
        project="test",
    )


def test_format_reset_minutes_only() -> None:
    resets_at = time.time() + 45 * 60
    assert windows_widget.format_reset(resets_at) == "45min"


def test_format_reset_hours_and_minutes() -> None:
    resets_at = time.time() + 2 * 3600 + 30 * 60
    assert windows_widget.format_reset(resets_at) == "2hr 30min"


def test_format_reset_days_and_hours() -> None:
    resets_at = time.time() + 2 * 86400 + 3 * 3600
    assert windows_widget.format_reset(resets_at) == "2d 3hr"


def test_format_reset_past_returns_zero() -> None:
    resets_at = time.time() - 100
    assert windows_widget.format_reset(resets_at) == "0min"


def test_compute_month_stats_sums_current_month(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime(2026, 5, 20, 12, 0, 0, tzinfo=UTC)
    monkeypatch.setattr("windows_widget._utcnow", lambda: now)

    entries = [
        _entry("s1", 2026, 5, 1.50),
        _entry("s2", 2026, 5, 2.00),
        _entry("s3", 2026, 4, 5.00),  # last month — excluded
    ]
    cost, sessions = windows_widget.compute_month_stats(entries)

    assert abs(cost - 3.50) < 0.001
    assert sessions == 2


def test_compute_month_stats_deduplicates_sessions(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime(2026, 5, 20, 12, 0, 0, tzinfo=UTC)
    monkeypatch.setattr("windows_widget._utcnow", lambda: now)

    entries = [
        _entry("same-session", 2026, 5, 1.00),
        _entry("same-session", 2026, 5, 1.00),
    ]
    _cost, sessions = windows_widget.compute_month_stats(entries)

    assert sessions == 1


def test_compute_month_stats_handles_none_cost(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime(2026, 5, 20, 12, 0, 0, tzinfo=UTC)
    monkeypatch.setattr("windows_widget._utcnow", lambda: now)

    entries = [_entry("s1", 2026, 5, None)]
    cost, sessions = windows_widget.compute_month_stats(entries)

    assert cost >= 0.0  # None cost_usd → estimated from token counts via pricing.py
    assert sessions == 1


# ── _fetch_codex_data ──────────────────────────────────────────────────────────

def test_fetch_codex_data_mock_returns_codex_keys() -> None:
    data = windows_widget._fetch_codex_data(mock=True)
    assert "codex_five_pct" in data
    assert "codex_five_reset" in data
    assert "codex_seven_pct" in data
    assert "codex_seven_reset" in data
    assert "status" in data


def test_fetch_codex_data_mock_has_no_claude_keys() -> None:
    data = windows_widget._fetch_codex_data(mock=True)
    assert "five_pct" not in data
    assert "seven_pct" not in data
    assert "month_cost" not in data


def test_fetch_codex_data_live_returns_defaults_when_no_rate_limits() -> None:
    with patch("windows_widget.codex_loader") as mock_loader:
        mock_loader.load_rate_limits.return_value = None
        data = windows_widget._fetch_codex_data(mock=False)
    assert data["codex_five_pct"] == 0
    assert data["codex_five_reset"] == "--"
    assert data["codex_seven_pct"] == 0
    assert data["codex_seven_reset"] == "--"


def test_fetch_codex_data_live_reads_rate_limits() -> None:
    rl = MagicMock()
    rl.five_hour_pct = 42.7
    rl.five_hour_resets_at = time.time() + 3600  # 1 hr from now
    rl.seven_day_pct = 18.3
    rl.seven_day_resets_at = time.time() + 2 * 86400  # 2 days

    with patch("windows_widget.codex_loader") as mock_loader:
        mock_loader.load_rate_limits.return_value = rl
        data = windows_widget._fetch_codex_data(mock=False)

    assert data["codex_five_pct"] == 43  # round(42.7)
    assert data["codex_seven_pct"] == 18  # round(18.3)
    assert data["codex_five_reset"] != "--"
    assert data["codex_seven_reset"] != "--"


def test_fetch_codex_data_live_handles_exception() -> None:
    with patch("windows_widget.codex_loader") as mock_loader:
        mock_loader.load_rate_limits.side_effect = RuntimeError("disk error")
        data = windows_widget._fetch_codex_data(mock=False)
    # Should not raise; returns defaults
    assert data["codex_five_pct"] == 0
    assert data["codex_seven_pct"] == 0


# ── _fetch_claude_data ─────────────────────────────────────────────────────────

def test_fetch_claude_data_mock_returns_claude_keys() -> None:
    data = windows_widget._fetch_claude_data(mock=True)
    assert "five_pct" in data
    assert "five_reset" in data
    assert "seven_pct" in data
    assert "seven_reset" in data
    assert "month_cost" in data
    assert "month_sessions" in data
    assert "status" in data


def test_fetch_claude_data_mock_has_no_codex_keys() -> None:
    data = windows_widget._fetch_claude_data(mock=True)
    assert "codex_five_pct" not in data
    assert "codex_seven_pct" not in data
