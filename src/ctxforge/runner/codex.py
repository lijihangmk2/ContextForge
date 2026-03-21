"""Codex CLI runner — launch interactive ``codex`` session."""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from ctxforge.exceptions import RunnerError
from ctxforge.runner.base import RunResult


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
            if initial_prompt:
                cmd.append(initial_prompt)
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
            discovered_session_id = self._find_latest_session_id(Path.cwd(), started_at)

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

    def _find_latest_session_id(self, cwd: Path, started_at: datetime) -> str | None:
        """Find the newest Codex session ID created for this cwd since *started_at*."""
        sessions_root = Path.home() / ".codex" / "sessions"
        if not sessions_root.exists():
            return None

        cwd_str = str(cwd.resolve())
        latest_match: tuple[datetime, str] | None = None
        for path in sessions_root.rglob("*.jsonl"):
            session = self._read_session_meta(path)
            if session is None:
                continue
            session_id, session_cwd, session_time = session
            if session_cwd != cwd_str or session_time < started_at:
                continue
            if latest_match is None or session_time > latest_match[0]:
                latest_match = (session_time, session_id)

        return latest_match[1] if latest_match else None

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
