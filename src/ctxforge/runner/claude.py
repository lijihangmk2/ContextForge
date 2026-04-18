"""Claude CLI runner — launch interactive ``claude`` session."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ctxforge.exceptions import RunnerError
from ctxforge.runner.base import RunResult


@dataclass(frozen=True)
class ClaudeSessionInfo:
    """Discovered Claude session metadata."""

    session_id: str
    cwd: str
    modified_at: datetime
    path: Path
    preview: str = ""


class ClaudeRunner:
    """Launch an interactive Claude CLI session with optional system prompt."""

    name: str = "claude"

    def run(
        self, system_prompt: str, initial_prompt: str = "",
        *, auto_approve: bool = False,
        mcp_config: Path | None = None,
        session_id: str | None = None,
        resume_id: str | None = None,
        on_session_started: Callable[[str], None] | None = None,
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

    def find_latest_session_id(self, cwd: Path) -> str | None:
        """Find the newest Claude session ID for *cwd*."""
        sessions = self.list_sessions(cwd=cwd)
        return sessions[0].session_id if sessions else None

    def list_sessions(self, *, cwd: Path) -> list[ClaudeSessionInfo]:
        """List Claude sessions for *cwd*, sorted by most recently modified first."""
        project_dir = self._project_sessions_dir(cwd)
        if not project_dir.exists():
            return []

        matches: list[ClaudeSessionInfo] = []
        for path in project_dir.glob("*.jsonl"):
            session_id = path.stem
            try:
                modified_at = datetime.fromtimestamp(
                    path.stat().st_mtime, tz=timezone.utc
                )
            except OSError:
                continue
            matches.append(
                ClaudeSessionInfo(
                    session_id=session_id,
                    cwd=str(cwd.resolve()),
                    modified_at=modified_at,
                    path=path,
                    preview=self._read_session_preview(path),
                )
            )

        matches.sort(key=lambda session: session.modified_at, reverse=True)
        return matches

    @staticmethod
    def _project_sessions_dir(cwd: Path) -> Path:
        """Resolve Claude's per-project session directory for *cwd*."""
        encoded = "-" + str(cwd.resolve()).strip("/").replace("/", "-")
        return Path.home() / ".claude" / "projects" / encoded

    @staticmethod
    def _read_session_preview(path: Path) -> str:
        """Read a short human-readable preview from the end of a Claude session log."""
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return ""

        for line in reversed(lines):
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue

            preview = ClaudeRunner._extract_preview_text(payload)
            if preview:
                return preview
        return ""

    @staticmethod
    def _extract_preview_text(payload: dict[str, object]) -> str:
        """Extract a useful preview string from one Claude session event."""
        event_type = payload.get("type")
        if event_type == "last-prompt":
            prompt = payload.get("lastPrompt")
            if isinstance(prompt, str):
                return ClaudeRunner._normalize_preview(prompt)

        message = payload.get("message")
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, str):
                return ClaudeRunner._normalize_preview(content)
            if isinstance(content, list):
                parts: list[str] = []
                for item in content:
                    if not isinstance(item, dict):
                        continue
                    text = item.get("text")
                    if isinstance(text, str):
                        parts.append(text)
                if parts:
                    return ClaudeRunner._normalize_preview(" ".join(parts))
        return ""

    @staticmethod
    def _normalize_preview(text: str, limit: int = 60) -> str:
        """Collapse whitespace and trim preview text for list display."""
        collapsed = " ".join(text.split())
        if len(collapsed) <= limit:
            return collapsed
        return collapsed[-limit:]
