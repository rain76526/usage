from __future__ import annotations

import io
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

import usage_statusline


def test_save_writes_status_json_with_received_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    status_file = tmp_path / "usage-status.json"
    now = datetime(2026, 1, 1, 12, 30, tzinfo=UTC)
    monkeypatch.setattr(usage_statusline, "STATUS_FILE", str(status_file))

    usage_statusline.save({"rate_limits": {"status": "ok"}}, now)

    data = json.loads(status_file.read_text(encoding="utf-8"))
    assert data["rate_limits"] == {"status": "ok"}
    assert data["_received_at"] == now.isoformat()
    assert data["_received_at_ts"] == now.timestamp()


def test_save_cleans_temp_file_when_atomic_replace_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    status_file = tmp_path / "usage-status.json"
    monkeypatch.setattr(usage_statusline, "STATUS_FILE", str(status_file))

    def fail_replace(src: str, dst: str) -> None:
        _ = src, dst
        raise OSError("replace failed")

    monkeypatch.setattr(os, "replace", fail_replace)

    with pytest.raises(OSError, match="replace failed"):
        usage_statusline.save({"ok": True}, datetime(2026, 1, 1, tzinfo=UTC))

    assert not status_file.exists()
    assert list(tmp_path.glob("*.tmp")) == []


@pytest.mark.parametrize("stdin_text", ["", "   \n", "{bad json", "[1, 2, 3]"])
def test_main_ignores_invalid_or_empty_stdin(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    stdin_text: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    status_file = tmp_path / "usage-status.json"
    monkeypatch.setattr(usage_statusline, "STATUS_FILE", str(status_file))
    monkeypatch.setattr(sys, "stdin", io.StringIO(stdin_text))

    usage_statusline.main()

    assert not status_file.exists()
    captured = capsys.readouterr()
    if stdin_text.strip():
        assert captured.out == "usage\n"
    else:
        assert captured.out == ""


def test_main_writes_valid_json_object(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    status_file = tmp_path / "usage-status.json"
    monkeypatch.setattr(usage_statusline, "STATUS_FILE", str(status_file))
    monkeypatch.setattr(sys, "stdin", io.StringIO('{"rate_limits": {"status": "ok"}}'))

    usage_statusline.main()

    data = json.loads(status_file.read_text(encoding="utf-8"))
    assert data["rate_limits"] == {"status": "ok"}
    assert isinstance(data["_received_at"], str)
    assert isinstance(data["_received_at_ts"], int | float)
    assert capsys.readouterr().out == "usage\n"


def test_main_returns_when_stdin_read_raises(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class BrokenStdin:
        def read(self) -> str:
            raise RuntimeError("read failed")

    status_file = tmp_path / "usage-status.json"
    monkeypatch.setattr(usage_statusline, "STATUS_FILE", str(status_file))
    monkeypatch.setattr(sys, "stdin", BrokenStdin())

    usage_statusline.main()

    assert not status_file.exists()
    assert capsys.readouterr().out == ""


def test_main_logs_invalid_json_in_debug_mode(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    status_file = tmp_path / "usage-status.json"
    monkeypatch.setattr(usage_statusline, "STATUS_FILE", str(status_file))
    monkeypatch.setattr(sys, "stdin", io.StringIO("{bad json"))
    monkeypatch.setenv("USAGE_DEBUG", "1")

    usage_statusline.main()

    captured = capsys.readouterr()
    assert "usage_statusline: invalid stdin JSON" in captured.err
    assert captured.out == "usage\n"
    assert not status_file.exists()


def test_render_outputs_multiline_colored_statusline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TT_LANG", "en")
    monkeypatch.setattr(usage_statusline, "get_width", lambda: 116)
    payload = {
        "model": {"display_name": "Sonnet 4.6"},
        "effort": {"level": "high"},
        "fast_mode": True,
        "context_window": {
            "used_percentage": 12,
            "context_window_size": 200000,
            "total_input_tokens": 123456,
            "total_output_tokens": 7890,
            "current_usage": {
                "input_tokens": 1200,
                "cache_creation_input_tokens": 300,
                "cache_read_input_tokens": 4567,
                "output_tokens": 890,
            },
        },
        "rate_limits": {
            "five_hour": {"used_percentage": 85},
            "seven_day": {"used_percentage": 33},
        },
        "cost": {"total_cost_usd": 38.73, "total_duration_ms": 3723000},
    }

    output = usage_statusline.render(payload, datetime(2026, 1, 1, tzinfo=UTC))

    assert "\n" in output
    assert "\033[" in output
    assert "█" in output
    assert "5h" in output
    assert "7d" in output
    assert "Context" in output
    assert "Sonnet 4.6" in output
    assert "$" not in output  # cost line removed in v0.10.0


def test_main_prints_fallback_when_render_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    status_file = tmp_path / "usage-status.json"
    monkeypatch.setattr(usage_statusline, "STATUS_FILE", str(status_file))
    monkeypatch.setattr(sys, "stdin", io.StringIO('{"model": {"display_name": "Sonnet"}}'))

    def fail_render(data: dict[str, object], now: datetime) -> str:
        _ = data, now
        raise RuntimeError("render failed")

    monkeypatch.setattr(usage_statusline, "render", fail_render)

    usage_statusline.main()

    assert status_file.exists()
    assert capsys.readouterr().out == "usage\n"
