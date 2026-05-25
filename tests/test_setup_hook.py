from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import setup_hook

LEGACY_NAME = "usag"


def _norm(p: str | Path) -> str:
    """Normalize path separators to forward slashes for cross-platform comparison."""
    return str(p).replace("\\", "/")


def _patch_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> tuple[Path, Path, Path]:
    claude_dir = tmp_path / ".claude"
    settings = claude_dir / "settings.json"
    hook_target = claude_dir / "usage-statusline.py"
    forwarder_target = claude_dir / "usage-statusline-forwarder.py"
    status_file = claude_dir / "usage-status.json"
    hook_source = tmp_path / "hook_source.py"
    forwarder_source = tmp_path / "forwarder_source.py"
    hook_source.write_text("print('hook')\n", encoding="utf-8")
    forwarder_source.write_text("print('forwarder')\n", encoding="utf-8")
    claude_dir.mkdir()
    monkeypatch.setattr(setup_hook, "CLAUDE_SETTINGS", settings)
    monkeypatch.setattr(setup_hook, "HOOK_TARGET", hook_target)
    monkeypatch.setattr(setup_hook, "FORWARDER_TARGET", forwarder_target)
    monkeypatch.setattr(setup_hook, "STATUS_FILE", status_file)
    monkeypatch.setattr(
        setup_hook,
        "LEGACY_HOOK_TARGET",
        claude_dir / f"{LEGACY_NAME}-statusline.py",
    )
    monkeypatch.setattr(setup_hook, "LEGACY_STATUS_FILE", claude_dir / f"{LEGACY_NAME}-status.json")
    monkeypatch.setattr(setup_hook, "_resolve_hook_source", lambda: hook_source)
    monkeypatch.setattr(setup_hook, "_resolve_forwarder_source", lambda: forwarder_source)
    monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/python3")
    return settings, hook_target, status_file


def test_setup_creates_new_settings_with_usage_statusline(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    settings, hook_target, _ = _patch_paths(monkeypatch, tmp_path)

    exit_code = setup_hook.setup()
    data = json.loads(settings.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert data["statusLine"]["type"] == "command"
    # On Windows the command uses forward slashes; normalize before comparing.
    assert _norm(hook_target) in _norm(data["statusLine"]["command"])
    assert hook_target.exists()


def test_setup_backs_up_existing_statusline_and_is_idempotent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    settings, hook_target, _ = _patch_paths(monkeypatch, tmp_path)
    original = {"type": "command", "command": "echo original"}
    settings.write_text(json.dumps({"statusLine": original}), encoding="utf-8")

    assert setup_hook.setup() == 0
    assert setup_hook.setup() == 0

    data = json.loads(settings.read_text(encoding="utf-8"))
    assert _norm(data["statusLine"]["command"]) == f"/usr/bin/python3 {_norm(setup_hook.FORWARDER_TARGET)}"
    assert data["usage"]["previousStatusLine"] == original
    assert hook_target.exists()
    assert setup_hook.FORWARDER_TARGET.exists()


def test_unsetup_restores_backup_and_removes_hook_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    settings, hook_target, status_file = _patch_paths(monkeypatch, tmp_path)
    previous = {"type": "command", "command": "echo original"}
    settings.write_text(
        json.dumps(
            {
                "statusLine": {"type": "command", "command": f"/usr/bin/python3 {hook_target}"},
                "usage": {"previousStatusLine": previous},
            }
        ),
        encoding="utf-8",
    )
    hook_target.write_text("print('hook')\n", encoding="utf-8")
    setup_hook.FORWARDER_TARGET.write_text("print('forwarder')\n", encoding="utf-8")
    status_file.write_text("{}", encoding="utf-8")

    exit_code = setup_hook.unsetup()
    data = json.loads(settings.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert data["statusLine"] == previous
    assert "usage" not in data
    assert not hook_target.exists()
    assert not setup_hook.FORWARDER_TARGET.exists()
    assert not status_file.exists()


def test_unsetup_without_install_is_safe_and_is_usage_hook_detects_commands(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_paths(monkeypatch, tmp_path)

    assert setup_hook.unsetup() == 0
    assert setup_hook._is_usage_hook({"command": "python3 /tmp/usage-statusline.py"})
    assert not setup_hook._is_usage_hook({"command": "python3 /tmp/other.py"})


def test_migration_removes_legacy_files_and_moves_backup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    settings, _, _ = _patch_paths(monkeypatch, tmp_path)
    legacy_hook = setup_hook.LEGACY_HOOK_TARGET
    legacy_status = setup_hook.LEGACY_STATUS_FILE
    legacy_hook.write_text("legacy hook\n", encoding="utf-8")
    legacy_status.write_text("{}", encoding="utf-8")
    previous = {"type": "command", "command": "echo original"}
    settings.write_text(
        json.dumps(
            {
                "statusLine": {
                    "type": "command",
                    "command": f"python3 {legacy_hook}",
                },
                LEGACY_NAME: {"previousStatusLine": previous},
            }
        ),
        encoding="utf-8",
    )

    setup_hook._migrate_from_legacy_usage()
    data = json.loads(settings.read_text(encoding="utf-8"))

    assert not legacy_hook.exists()
    assert not legacy_status.exists()
    assert "statusLine" not in data
    assert LEGACY_NAME not in data
    assert data["usage"]["previousStatusLine"] == previous


@pytest.mark.skipif(sys.platform == "win32", reason="/bin/sh not available on Windows")
def test_statusline_command_quotes_paths_with_spaces(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import subprocess

    bin_dir = tmp_path / "含 空格" / "bin"
    hook_dir = tmp_path / "Claude Code 小工具"
    bin_dir.mkdir(parents=True)
    hook_dir.mkdir()
    argv_file = tmp_path / "argv.txt"
    fake_python = bin_dir / "python3"
    hook_file = hook_dir / "usage statusline.py"
    fake_python.write_text(
        f"#!/bin/sh\nprintf '%s\\n' \"$1\" > {setup_hook._shell_arg(str(argv_file))}\n",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)
    hook_file.write_text("print('unused')\n", encoding="utf-8")

    monkeypatch.setattr(shutil, "which", lambda _: str(fake_python))
    monkeypatch.setattr(setup_hook, "HOOK_TARGET", hook_file)

    cmd = setup_hook._statusline_command()

    result = subprocess.run(["/bin/sh", "-c", cmd], capture_output=True)
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    assert argv_file.read_text(encoding="utf-8").strip() == str(hook_file)
