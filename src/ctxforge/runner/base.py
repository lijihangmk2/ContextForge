"""CLI runner protocol and result type."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass
class RunResult:
    """Result of running an AI CLI command."""

    exit_code: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


class CliRunner(Protocol):
    """Protocol that all CLI runners must implement."""

    name: str

    def run(
        self,
        system_prompt: str,
        initial_prompt: str = "",
        *,
        auto_approve: bool = False,
        mcp_config: Path | None = None,
        session_id: str | None = None,
        resume_id: str | None = None,
    ) -> RunResult:
        """Execute the AI CLI with the given system prompt."""
        ...

    def run_oneshot(
        self,
        prompt: str,
        *,
        auto_approve: bool = False,
        mcp_config: Path | None = None,
    ) -> RunResult:
        """Run a single non-interactive prompt."""
        ...
