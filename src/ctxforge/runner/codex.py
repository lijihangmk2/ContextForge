"""Codex CLI runner — launch interactive ``codex`` session."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ctxforge.exceptions import RunnerError
from ctxforge.runner.base import RunResult


@dataclass(frozen=True)
class CodexSessionInfo:
    """Discovered Codex session metadata."""

    session_id: str
    cwd: str
    created_at: datetime
    modified_at: datetime
    path: Path
    preview: str = ""


class CodexRunner:
    """Launch an interactive Codex CLI session with optional context injection.

    Codex does not support a ``--system-prompt`` flag, so the context is
    combined into the initial ``[PROMPT]`` positional argument.
    """

    name: str = "codex"

    def run(
        self, system_prompt: str, initial_prompt: str = "",
        *, auto_approve: bool = False,
        mcp_config: Path | None = None,
        session_id: str | None = None,
        resume_id: str | None = None,
    ) -> RunResult:
        """Start an interactive ``codex`` session.

        *system_prompt* and *initial_prompt* are merged into a single
        positional argument since Codex only accepts ``[PROMPT]``.
        """
        cmd: list[str] = ["codex"]
        if auto_approve:
            cmd.append("--dangerously-bypass-approvals-and-sandbox")
        started_at = datetime.now(UTC)

        if resume_id:
            cmd.extend(["resume", resume_id])
        else:
            combined = "\n\n".join(p for p in [system_prompt, initial_prompt] if p)
            if combined:
                cmd.append(combined)

        try:
            proc = subprocess.run(cmd)
        except FileNotFoundError as e:
            raise RunnerError("codex CLI not found on PATH") from e
        except Exception as e:
            raise RunnerError(f"Failed to run codex: {e}") from e

        discovered_session_id = None
        if not resume_id:
            discovered_session_id = self.find_latest_session_id(Path.cwd(), since=started_at)

        return RunResult(
            exit_code=proc.returncode,
            stdout="",
            stderr="",
            session_id=discovered_session_id,
        )

    def run_oneshot(
        self, prompt: str, *, auto_approve: bool = False,
        mcp_config: Path | None = None,
    ) -> RunResult:
        """Run a single non-interactive ``codex`` command."""
        cmd: list[str] = ["codex"]
        if auto_approve:
            cmd.append("--dangerously-bypass-approvals-and-sandbox")
        cmd.append(prompt)

        try:
            proc = subprocess.run(cmd)
        except FileNotFoundError as e:
            raise RunnerError("codex CLI not found on PATH") from e
        except Exception as e:
            raise RunnerError(f"Failed to run codex: {e}") from e

        return RunResult(exit_code=proc.returncode, stdout="", stderr="")

    def find_latest_session_id(
        self, cwd: Path, *, since: datetime | None = None,
    ) -> str | None:
        """Find the newest Codex session ID for *cwd*, optionally filtered by time."""
        sessions = self.list_sessions(cwd=cwd, since=since)
        return sessions[0].session_id if sessions else None

    def list_sessions(
        self, *, cwd: Path | None = None, since: datetime | None = None,
    ) -> list[CodexSessionInfo]:
        """List discovered Codex sessions sorted by most recently modified first."""
        sessions_root = Path.home() / ".codex" / "sessions"
        if not sessions_root.exists():
            return []

        cwd_str = str(cwd.resolve()) if cwd is not None else None
        matches: list[CodexSessionInfo] = []
        for path in sessions_root.rglob("*.jsonl"):
            session = self._read_session_meta(path)
            if session is None:
                continue
            session_id, session_cwd, created_at = session
            if cwd_str is not None and session_cwd != cwd_str:
                continue
            if since is not None and created_at < since:
                continue
            try:
                modified_at = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
            except OSError:
                continue
            matches.append(
                CodexSessionInfo(
                    session_id=session_id,
                    cwd=session_cwd,
                    created_at=created_at,
                    modified_at=modified_at,
                    path=path,
                    preview=self._read_session_preview(path),
                )
            )

        matches.sort(key=lambda session: session.modified_at, reverse=True)
        return matches

    @staticmethod
    def _read_session_meta(path: Path) -> tuple[str, str, datetime] | None:
        """Read session ID, cwd, and timestamp from the first JSONL line."""
        try:
            first_line = path.read_text(encoding="utf-8").splitlines()[0]
            payload = json.loads(first_line)
            if payload.get("type") != "session_meta":
                return None
            meta = payload.get("payload", {})
            session_id = meta.get("id")
            cwd = meta.get("cwd")
            timestamp = meta.get("timestamp")
            if not isinstance(session_id, str) or not isinstance(cwd, str) or not isinstance(timestamp, str):
                return None
            return session_id, cwd, datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except (IndexError, OSError, ValueError, json.JSONDecodeError):
            return None

    @staticmethod
    def _read_session_preview(path: Path) -> str:
        """Read a short human-readable preview from the end of a session log."""
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return ""

        for line in reversed(lines):
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue

            preview = CodexRunner._extract_preview_text(payload)
            if preview:
                return preview
        return ""

    @staticmethod
    def _extract_preview_text(payload: dict) -> str:
        """Extract the most useful preview text from one session event."""
        event_type = payload.get("type")
        data = payload.get("payload", {})

        if event_type == "event_msg":
            if data.get("type") == "task_complete":
                message = data.get("last_agent_message")
                if isinstance(message, str):
                    return CodexRunner._normalize_preview(message)
            message = data.get("message")
            if isinstance(message, str):
                return CodexRunner._normalize_preview(message)

        if event_type == "response_item" and data.get("type") == "message":
            content = data.get("content", [])
            if isinstance(content, list):
                parts: list[str] = []
                for item in content:
                    if not isinstance(item, dict):
                        continue
                    text = item.get("text")
                    if isinstance(text, str):
                        parts.append(text)
                if parts:
                    return CodexRunner._normalize_preview(" ".join(parts))

        return ""

    @staticmethod
    def _normalize_preview(text: str, limit: int = 60) -> str:
        """Collapse whitespace and trim preview text for list display."""
        collapsed = " ".join(text.split())
        if len(collapsed) <= limit:
            return collapsed
        return collapsed[-limit:]
