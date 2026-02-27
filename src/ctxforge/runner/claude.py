"""Claude CLI runner — launch interactive ``claude`` session."""

from __future__ import annotations

import subprocess

from ctxforge.exceptions import RunnerError
from ctxforge.runner.base import RunResult


class ClaudeRunner:
    """Launch an interactive Claude CLI session with optional system prompt."""

    name: str = "claude"

    def run(self, system_prompt: str, initial_prompt: str = "") -> RunResult:
        """Start an interactive ``claude`` session.

        When *system_prompt* is non-empty it is passed via
        ``--append-system-prompt`` so that Claude Code's built-in capabilities
        (CLAUDE.md, tools, etc.) are preserved.

        When *initial_prompt* is non-empty it is passed as a positional
        argument so Claude immediately processes it on session start.
        """
        cmd: list[str] = ["claude"]
        if system_prompt:
            cmd.extend(["--append-system-prompt", system_prompt])
        if initial_prompt:
            cmd.append(initial_prompt)

        try:
            proc = subprocess.run(cmd)
        except FileNotFoundError as e:
            raise RunnerError("claude CLI not found on PATH") from e
        except Exception as e:
            raise RunnerError(f"Failed to run claude: {e}") from e

        return RunResult(exit_code=proc.returncode, stdout="", stderr="")
