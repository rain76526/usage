from __future__ import annotations

import sys
from datetime import UTC, datetime
from importlib import import_module
from typing import Any

import pytest

from adapters.types import AgentInfo, RateLimits, UsageEntry

usage_cli: Any = import_module("usage_cli")


def _entry() -> UsageEntry:
    return UsageEntry(
        timestamp=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        session_id="session-1",
        message_id="message-1",
        request_id="request-1",
        model="gpt-test",
        input_tokens=10,
        output_tokens=5,
        cache_creation_tokens=2,
        cache_read_tokens=3,
        cost_usd=0.01,
        project="project",
        agent_id="codex",
    )


def test_parse_sort_args_extracts_major_flags() -> None:
    remaining, sort_key, descending = usage_cli._parse_sort_args(
        ["30", "--sort", "cost", "--asc"]
    )

    assert remaining == ["30"]
    assert sort_key == "cost"
    assert descending is False


def test_main_dashboard_uses_mocked_loaders_without_touching_agent_dirs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agent = AgentInfo("codex", "Codex", "~/.codex", True)
    rendered: dict[str, Any] = {}

    monkeypatch.setattr(sys, "argv", ["usage", "dashboard"])
    monkeypatch.setattr(usage_cli, "detect_agents", lambda: [agent])
    monkeypatch.setattr(usage_cli, "is_setup", lambda: True)
    monkeypatch.setattr(usage_cli, "needs_update", lambda: False)
    monkeypatch.setattr(usage_cli, "_load_entries", lambda agent_id: [_entry()])
    monkeypatch.setattr(
        usage_cli,
        "RATE_LIMIT_LOADERS",
        {"codex": lambda: RateLimits(five_hour_pct=12, seven_day_pct=34)},
    )
    monkeypatch.setattr(usage_cli, "render_dashboard", lambda **kwargs: rendered.update(kwargs))

    usage_cli.main()

    assert rendered["agents"] == ["Codex"]
    assert len(rendered["daily_stats"]) == 1
    assert rendered["rate_limits"] == RateLimits(five_hour_pct=12, seven_day_pct=34)


def test_main_daily_sort_flag_controls_render_order(monkeypatch: pytest.MonkeyPatch) -> None:
    agent = AgentInfo("codex", "Codex", "~/.codex", True)
    high = _entry()
    low = _entry()
    high.input_tokens = 100
    high.timestamp = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    low.input_tokens = 1
    low.timestamp = datetime(2026, 1, 2, 12, 0, tzinfo=UTC)
    rendered: dict[str, Any] = {}

    monkeypatch.setattr(sys, "argv", ["usage", "daily", "--sort", "tokens", "--asc"])
    monkeypatch.setattr(usage_cli, "detect_agents", lambda: [agent])
    monkeypatch.setattr(usage_cli, "is_setup", lambda: True)
    monkeypatch.setattr(usage_cli, "needs_update", lambda: False)
    monkeypatch.setattr(usage_cli, "_load_entries", lambda agent_id: [high, low])
    monkeypatch.setattr(
        usage_cli,
        "render_daily",
        lambda stats, agents: rendered.update(stats=stats),
    )

    usage_cli.main()

    assert [stat.total_tokens for stat in rendered["stats"]] == [11, 110]


def test_main_exits_when_no_agents_detected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["usage", "dashboard"])
    monkeypatch.setattr(usage_cli, "detect_agents", lambda: [])

    with pytest.raises(SystemExit) as exc_info:
        usage_cli.main()

    assert exc_info.value.code == 1
