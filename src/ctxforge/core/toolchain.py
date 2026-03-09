"""Toolchain — tool availability checks and MCP config generation."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from ctxforge.spec.schema import ProfileConfig, ProjectConfig, ToolDefinition


class ToolStatus(Enum):
    AVAILABLE = "available"
    MISSING_COMMAND = "missing_command"
    MISSING_ENV = "missing_env"


@dataclass
class ToolCheckResult:
    name: str
    status: ToolStatus
    missing_env: list[str]

    @property
    def ok(self) -> bool:
        return self.status == ToolStatus.AVAILABLE


def check_tool(name: str, tool: ToolDefinition) -> ToolCheckResult:
    """Check if a tool's requirements are met."""
    if not shutil.which(tool.command):
        return ToolCheckResult(name=name, status=ToolStatus.MISSING_COMMAND, missing_env=[])
    missing = [var for var in tool.env if var not in os.environ]
    if missing:
        return ToolCheckResult(name=name, status=ToolStatus.MISSING_ENV, missing_env=missing)
    return ToolCheckResult(name=name, status=ToolStatus.AVAILABLE, missing_env=[])


def _active_tool_names(
    profile: ProfileConfig, project: ProjectConfig,
) -> list[str]:
    """Return project tool names that are not disabled for this profile."""
    disabled = set(profile.tools.disabled)
    return [name for name in project.tools if name not in disabled]


def resolve_tools(
    profile: ProfileConfig, project: ProjectConfig,
) -> list[ToolCheckResult]:
    """Resolve active tools (all project tools minus profile-disabled).

    Returns check results for each active tool.
    """
    results: list[ToolCheckResult] = []
    for name in _active_tool_names(profile, project):
        results.append(check_tool(name, project.tools[name]))
    return results


def build_mcp_config(
    profile: ProfileConfig, project: ProjectConfig,
) -> Path | None:
    """Generate a temporary MCP config JSON for available tools.

    Returns the path to the temp file, or None if no tools are available.
    The caller is responsible for cleanup (though the OS will clean /tmp).
    """
    servers: dict[str, dict[str, object]] = {}
    for name in _active_tool_names(profile, project):
        tool = project.tools[name]
        result = check_tool(name, tool)
        if not result.ok:
            continue
        server: dict[str, object] = {"command": tool.command}
        if tool.args:
            server["args"] = tool.args
        servers[name] = server

    if not servers:
        return None

    config = {"mcpServers": servers}
    fd, path = tempfile.mkstemp(prefix="ctxforge-mcp-", suffix=".json")
    with os.fdopen(fd, "w") as f:
        json.dump(config, f, indent=2)
    return Path(path)
