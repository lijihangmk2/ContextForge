"""AI CLI tool detection."""

from __future__ import annotations

import shutil

# AI CLI tools with runner support
AI_CLI_TOOLS = [
    "claude",
    "codex",
]


def detect_ai_clis(tools: list[str] | None = None) -> list[str]:
    """Detect which AI CLI tools are available on the system.

    Args:
        tools: List of tool names to check. Defaults to AI_CLI_TOOLS.

    Returns:
        List of detected tool names.
    """
    if tools is None:
        tools = AI_CLI_TOOLS

    return [name for name in tools if shutil.which(name) is not None]
