"""Manage ctxforge-owned Claude Code settings snippets."""

from __future__ import annotations

import json
import shlex
import shutil
import sys
from pathlib import Path

from ctxforge.core.memory import MemoryBinding

HOOK_MARKER = "ctxforge hook memory"


def sync_claude_memory_hooks(
    project_root: Path,
    binding: MemoryBinding | None,
) -> None:
    """Synchronize ctxforge-managed memory hooks into Claude settings."""
    settings_path = project_root / ".claude" / "settings.local.json"
    data = _load_settings(settings_path)
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        hooks = {}
        data["hooks"] = hooks

    _remove_managed_hooks(hooks)

    if binding is not None:
        hooks["Stop"] = hooks.get("Stop", [])
        hooks["PreCompact"] = hooks.get("PreCompact", [])
        if not isinstance(hooks["Stop"], list):
            hooks["Stop"] = []
        if not isinstance(hooks["PreCompact"], list):
            hooks["PreCompact"] = []
        hooks["Stop"].append(_build_stop_hook(binding))
        hooks["PreCompact"].append(_build_precompact_hook(binding))

    _cleanup_empty_hooks(data)
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _build_stop_hook(binding: MemoryBinding) -> dict[str, object]:
    return {
        "matcher": "*",
        "hooks": [
            {
                "type": "command",
                "command": _hook_command(
                    event="stop",
                    binding=binding,
                ),
                "timeout": 30,
            }
        ],
    }


def _build_precompact_hook(binding: MemoryBinding) -> dict[str, object]:
    return {
        "hooks": [
            {
                "type": "command",
                "command": _hook_command(
                    event="precompact",
                    binding=binding,
                ),
                "timeout": 30,
            }
        ],
    }


def _hook_command(event: str, binding: MemoryBinding) -> str:
    runner = _ctxforge_hook_runner()
    parts = [
        *runner,
        "hook",
        "memory",
        "--event",
        event,
        "--harness",
        "claude-code",
        "--interval",
        str(binding.checkpoint_interval),
        "--palace-path",
        str(binding.palace_path),
        "--namespace",
        binding.namespace,
        "--wing",
        binding.wing,
    ]
    return " ".join(shlex.quote(part) for part in parts)


def _ctxforge_hook_runner() -> list[str]:
    ctxforge_cmd = shutil.which("ctxforge")
    if ctxforge_cmd:
        return [ctxforge_cmd]
    return [sys.executable, "-m", "ctxforge"]


def _load_settings(settings_path: Path) -> dict[str, object]:
    if not settings_path.exists():
        return {}
    try:
        raw = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _remove_managed_hooks(hooks: dict[str, object]) -> None:
    for key in ("Stop", "PreCompact"):
        entries = hooks.get(key)
        if not isinstance(entries, list):
            continue
        kept_entries: list[dict[str, object]] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            hook_list = entry.get("hooks")
            if not isinstance(hook_list, list):
                kept_entries.append(entry)
                continue
            filtered = [
                hook
                for hook in hook_list
                if not _is_managed_hook(hook)
            ]
            if filtered:
                updated = dict(entry)
                updated["hooks"] = filtered
                kept_entries.append(updated)
        if kept_entries:
            hooks[key] = kept_entries
        else:
            hooks.pop(key, None)


def _is_managed_hook(hook: object) -> bool:
    if not isinstance(hook, dict):
        return False
    command = hook.get("command")
    return isinstance(command, str) and HOOK_MARKER in command


def _cleanup_empty_hooks(data: dict[str, object]) -> None:
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        data.pop("hooks", None)
        return
    if not hooks:
        data.pop("hooks", None)
