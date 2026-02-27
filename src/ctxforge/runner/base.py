"""CLI runner protocol and result type."""

from __future__ import annotations

from dataclasses import dataclass
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

    def run(self, system_prompt: str, initial_prompt: str = "") -> RunResult:
        """Execute the AI CLI with the given system prompt."""
        ...
