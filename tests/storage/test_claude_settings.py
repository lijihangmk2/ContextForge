"""Tests for Claude settings sync."""

import json
from pathlib import Path

from ctxforge.core.memory import MemoryBinding
from ctxforge.storage.claude_settings import sync_claude_memory_hooks


def _binding(tmp_path: Path) -> MemoryBinding:
    return MemoryBinding(
        provider="mempalace",
        namespace="profile/default",
        wing="profile-default",
        palace_path=tmp_path / ".ctxforge" / "memory" / "mempalace",
        checkpoint_interval=12,
        cross_profile_search=False,
    )


def test_sync_claude_memory_hooks_writes_managed_hooks(tmp_path: Path) -> None:
    sync_claude_memory_hooks(tmp_path, _binding(tmp_path))
    settings = json.loads(
        (tmp_path / ".claude" / "settings.local.json").read_text(encoding="utf-8")
    )
    assert "hooks" in settings
    stop_hooks = settings["hooks"]["Stop"][0]["hooks"]
    precompact_hooks = settings["hooks"]["PreCompact"][0]["hooks"]
    assert "ctxforge hook memory" in stop_hooks[0]["command"]
    assert "--interval 12" in stop_hooks[0]["command"]
    assert "ctxforge hook memory" in precompact_hooks[0]["command"]


def test_sync_claude_memory_hooks_preserves_unmanaged_hooks(tmp_path: Path) -> None:
    settings_path = tmp_path / ".claude" / "settings.local.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        json.dumps(
            {
                "hooks": {
                    "Stop": [
                        {
                            "matcher": "*",
                            "hooks": [
                                {"type": "command", "command": "custom-hook", "timeout": 10}
                            ],
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    sync_claude_memory_hooks(tmp_path, _binding(tmp_path))
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    commands = [hook["command"] for entry in settings["hooks"]["Stop"] for hook in entry["hooks"]]
    assert "custom-hook" in commands
    assert any("ctxforge hook memory" in command for command in commands)


def test_sync_claude_memory_hooks_removes_managed_hooks_when_disabled(tmp_path: Path) -> None:
    sync_claude_memory_hooks(tmp_path, _binding(tmp_path))
    sync_claude_memory_hooks(tmp_path, None)
    settings = json.loads(
        (tmp_path / ".claude" / "settings.local.json").read_text(encoding="utf-8")
    )
    assert "hooks" not in settings
