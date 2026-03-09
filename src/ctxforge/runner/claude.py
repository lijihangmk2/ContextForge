"""Claude CLI runner — launch interactive ``claude`` session."""

from __future__ import annotations

import subprocess
from pathlib import Path

from ctxforge.exceptions import RunnerError
from ctxforge.runner.base import RunResult


class ClaudeRunner:
    """Launch an interactive Claude CLI session with optional system prompt."""

    name: str = "claude"

    def run(
        self, system_prompt: str, initial_prompt: str = "",
        *, auto_approve: bool = False,
        mcp_config: Path | None = None,
        session_id: str | None = None,
        resume_id: str | None = None,
    ) -> RunResult:
        """Start an interactive ``claude`` session.

        Session modes:
          - *resume_id*: resume a previous session (``--resume``).
            System prompt and greeting are NOT re-injected.
          - *session_id*: start a new session with explicit ID (``--session-id``).
          - Neither: let Claude pick the session.
        """
        cmd: list[str] = ["claude"]
        if resume_id:
            cmd.extend(["--resume", resume_id])
        elif session_id:
            cmd.extend(["--session-id", session_id])
        if auto_approve:
            cmd.append("--dangerously-skip-permissions")
        if mcp_config:
            cmd.extend(["--mcp-config", str(mcp_config)])
        # Only inject context for new sessions
        if not resume_id:
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

    def run_oneshot(
        self, prompt: str, *, auto_approve: bool = False,
        mcp_config: Path | None = None,
    ) -> RunResult:
        """Run a single non-interactive ``claude -p`` command."""
        cmd: list[str] = ["claude"]
        if auto_approve:
            cmd.append("--dangerously-skip-permissions")
        if mcp_config:
            cmd.extend(["--mcp-config", str(mcp_config)])
        # Prevent session persistence for oneshot commands
        cmd.extend(["--no-session-persistence", "-p", prompt])

        try:
            proc = subprocess.run(cmd)
        except FileNotFoundError as e:
            raise RunnerError("claude CLI not found on PATH") from e
        except Exception as e:
            raise RunnerError(f"Failed to run claude: {e}") from e

        return RunResult(exit_code=proc.returncode, stdout="", stderr="")
