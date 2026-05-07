"""Codex CLI runner — launch interactive ``codex`` session."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
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

    On Windows, npm's ``codex.cmd`` shim expands ``%*`` without preserving
    multi-line arguments. Launching the underlying Node entrypoint directly
    keeps the combined prompt intact.
    """

    name: str = "codex"

    def run(
        self, system_prompt: str, initial_prompt: str = "",
        *, auto_approve: bool = False,
        mcp_config: Path | None = None,
        session_id: str | None = None,
        resume_id: str | None = None,
        on_session_started: Callable[[str], None] | None = None,
    ) -> RunResult:
        """Start an interactive ``codex`` session.

        *system_prompt* and *initial_prompt* are merged into a single
        positional argument since Codex only accepts ``[PROMPT]``.
        """
        cmd: list[str] = self._base_command()
        if auto_approve:
            cmd.append("--dangerously-bypass-approvals-and-sandbox")
        started_at = datetime.now(timezone.utc)

        if resume_id:
            cmd.extend(["resume", resume_id])
        else:
            combined = "\n\n".join(p for p in [system_prompt, initial_prompt] if p)
            if combined:
                cmd.append(combined)

        try:
            proc = subprocess.Popen(cmd)
        except FileNotFoundError as e:
            raise RunnerError("codex CLI not found on PATH") from e
        except Exception as e:
            raise RunnerError(f"Failed to run codex: {e}") from e

        discovered_session_id = None
        if not resume_id:
            discovered_session_id = self._wait_for_session_id(
                proc,
                cwd=Path.cwd(),
                since=started_at,
            )
            if discovered_session_id and on_session_started is not None:
                on_session_started(discovered_session_id)

        return_code = proc.wait()

        if not resume_id and discovered_session_id is None:
            discovered_session_id = self.find_latest_session_id(Path.cwd(), since=started_at)
            if discovered_session_id and on_session_started is not None:
                on_session_started(discovered_session_id)

        return RunResult(
            exit_code=return_code,
            stdout="",
            stderr="",
            session_id=discovered_session_id,
        )

    def run_oneshot(
        self, prompt: str, *, auto_approve: bool = False,
        mcp_config: Path | None = None,
    ) -> RunResult:
        """Run a single non-interactive ``codex`` command."""
        cmd: list[str] = self._base_command()
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

    @staticmethod
    def _base_command() -> list[str]:
        """Return a Codex command that preserves argv on the current platform."""
        if sys.platform != "win32":
            return ["codex"]

        codex_cmd = shutil.which("codex.cmd") or shutil.which("codex")
        if not codex_cmd:
            return ["codex"]

        basedir = Path(codex_cmd).parent
        script = basedir / "node_modules" / "@openai" / "codex" / "bin" / "codex.js"
        if not script.exists():
            return ["codex"]

        local_node = basedir / "node.exe"
        if local_node.exists():
            node = str(local_node)
        else:
            node = shutil.which("node.exe") or shutil.which("node") or "node"
        return [node, str(script)]

    def find_latest_session_id(
        self, cwd: Path, *, since: datetime | None = None,
    ) -> str | None:
        """Find the newest Codex session ID for *cwd*, optionally filtered by time."""
        sessions = self.list_sessions(cwd=cwd, since=since)
        return sessions[0].session_id if sessions else None

    def _wait_for_session_id(
        self,
        proc: subprocess.Popen[bytes],
        *,
        cwd: Path,
        since: datetime,
        poll_interval: float = 0.2,
        max_wait: float = 15.0,
    ) -> str | None:
        """Poll for a newly created session while the interactive CLI is starting."""
        deadline = time.monotonic() + max_wait
        while proc.poll() is None and time.monotonic() < deadline:
            session_id = self.find_latest_session_id(cwd, since=since)
            if session_id:
                return session_id
            time.sleep(poll_interval)
        return None

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
                modified_at = datetime.fromtimestamp(
                    path.stat().st_mtime, tz=timezone.utc
                )
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
            if not (
                isinstance(session_id, str)
                and isinstance(cwd, str)
                and isinstance(timestamp, str)
            ):
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
    def _extract_preview_text(payload: dict[str, object]) -> str:
        """Extract the most useful preview text from one session event."""
        event_type = payload.get("type")
        data = payload.get("payload")
        if not isinstance(data, dict):
            return ""

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
