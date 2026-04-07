"""Tests for CodexRunner."""

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ctxforge.exceptions import RunnerError
from ctxforge.runner.codex import CodexRunner


class TestCodexRunner:
    def test_run_success(self):
        runner = CodexRunner()
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("ctxforge.runner.codex.subprocess.run", return_value=mock_result) as mock_run:
            result = runner.run("system context")
            mock_run.assert_called_once_with(
                ["codex", "system context"],
            )
        assert result.ok
        assert result.stdout == ""
        assert result.stderr == ""

    def test_run_with_initial_prompt(self):
        runner = CodexRunner()
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("ctxforge.runner.codex.subprocess.run", return_value=mock_result) as mock_run:
            result = runner.run("system context", "hello")
            mock_run.assert_called_once_with(
                ["codex", "system context\n\nhello"],
            )
        assert result.ok

    def test_run_auto_approve(self):
        runner = CodexRunner()
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("ctxforge.runner.codex.subprocess.run", return_value=mock_result) as mock_run:
            result = runner.run("system context", auto_approve=True)
            mock_run.assert_called_once_with(
                ["codex", "--dangerously-bypass-approvals-and-sandbox", "system context"],
            )
        assert result.ok

    def test_run_empty_system_prompt(self):
        runner = CodexRunner()
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("ctxforge.runner.codex.subprocess.run", return_value=mock_result) as mock_run:
            result = runner.run("")
            mock_run.assert_called_once_with(["codex"])
        assert result.ok

    def test_run_resume_session(self):
        runner = CodexRunner()
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("ctxforge.runner.codex.subprocess.run", return_value=mock_result) as mock_run:
            result = runner.run("system context", "hello", resume_id="abc-123")
            mock_run.assert_called_once_with(
                ["codex", "resume", "abc-123"],
            )
        assert result.ok

    def test_run_discovers_session_id(self):
        runner = CodexRunner()
        mock_result = MagicMock()
        mock_result.returncode = 0

        with (
            patch("ctxforge.runner.codex.subprocess.run", return_value=mock_result),
            patch.object(runner, "find_latest_session_id", return_value="sid-123") as mock_find,
        ):
            result = runner.run("system context")
        mock_find.assert_called_once()
        assert result.session_id == "sid-123"

    def test_run_resume_does_not_discover_session_id(self):
        runner = CodexRunner()
        mock_result = MagicMock()
        mock_result.returncode = 0

        with (
            patch("ctxforge.runner.codex.subprocess.run", return_value=mock_result),
            patch.object(runner, "find_latest_session_id") as mock_find,
        ):
            result = runner.run("system context", resume_id="abc-123")
        mock_find.assert_not_called()
        assert result.session_id is None

    def test_list_sessions_sorted_by_modified_time(self, tmp_path: Path):
        runner = CodexRunner()
        sessions_root = tmp_path / ".codex" / "sessions" / "2026" / "04" / "01"
        sessions_root.mkdir(parents=True)

        older = sessions_root / "older.jsonl"
        older.write_text(
            json.dumps(
                {
                    "type": "session_meta",
                    "payload": {
                        "id": "older-session",
                        "cwd": "/repo",
                        "timestamp": "2026-04-01T00:00:00Z",
                    },
                }
            ),
            encoding="utf-8",
        )
        newer = sessions_root / "newer.jsonl"
        newer.write_text(
            json.dumps(
                {
                    "type": "session_meta",
                    "payload": {
                        "id": "newer-session",
                        "cwd": "/repo",
                        "timestamp": "2026-03-20T00:00:00Z",
                    },
                }
            ),
            encoding="utf-8",
        )

        older_time = datetime(2026, 4, 1, 1, 0, tzinfo=timezone.utc).timestamp()
        newer_time = datetime(2026, 4, 1, 2, 0, tzinfo=timezone.utc).timestamp()
        older.touch()
        newer.touch()
        older.chmod(0o644)
        newer.chmod(0o644)
        import os
        os.utime(older, (older_time, older_time))
        os.utime(newer, (newer_time, newer_time))

        with patch("ctxforge.runner.codex.Path.home", return_value=tmp_path):
            sessions = runner.list_sessions(cwd=Path("/repo"))

        assert [session.session_id for session in sessions] == [
            "newer-session",
            "older-session",
        ]

    def test_list_sessions_extracts_preview_from_last_message(self, tmp_path: Path):
        runner = CodexRunner()
        sessions_root = tmp_path / ".codex" / "sessions" / "2026" / "04" / "01"
        sessions_root.mkdir(parents=True)

        session_file = sessions_root / "preview.jsonl"
        session_file.write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "type": "session_meta",
                            "payload": {
                                "id": "preview-session",
                                "cwd": "/repo",
                                "timestamp": "2026-04-01T00:00:00Z",
                            },
                        }
                    ),
                    json.dumps(
                        {
                            "type": "event_msg",
                            "payload": {
                                "type": "task_complete",
                                "last_agent_message": (
                                    "这是最后一条消息，用于展示给用户确认恢复哪个 session。"
                                ),
                            },
                        }
                    ),
                ]
            ),
            encoding="utf-8",
        )

        with patch("ctxforge.runner.codex.Path.home", return_value=tmp_path):
            sessions = runner.list_sessions(cwd=Path("/repo"))

        assert len(sessions) == 1
        assert "恢复哪个 session" in sessions[0].preview

    def test_run_failure(self):
        runner = CodexRunner()
        mock_result = MagicMock()
        mock_result.returncode = 1

        with patch("ctxforge.runner.codex.subprocess.run", return_value=mock_result):
            result = runner.run("system context")
        assert not result.ok
        assert result.exit_code == 1

    def test_run_not_found(self):
        runner = CodexRunner()
        with patch("ctxforge.runner.codex.subprocess.run", side_effect=FileNotFoundError):
            with pytest.raises(RunnerError, match="not found"):
                runner.run("test")

    def test_run_oneshot_success(self):
        runner = CodexRunner()
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("ctxforge.runner.codex.subprocess.run", return_value=mock_result) as mock_run:
            result = runner.run_oneshot("compress key files")
            mock_run.assert_called_once_with(
                ["codex", "compress key files"],
            )
        assert result.ok

    def test_run_oneshot_auto_approve(self):
        runner = CodexRunner()
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("ctxforge.runner.codex.subprocess.run", return_value=mock_result) as mock_run:
            result = runner.run_oneshot("compress key files", auto_approve=True)
            mock_run.assert_called_once_with(
                ["codex", "--dangerously-bypass-approvals-and-sandbox", "compress key files"],
            )
        assert result.ok

    def test_run_oneshot_not_found(self):
        runner = CodexRunner()
        with patch("ctxforge.runner.codex.subprocess.run", side_effect=FileNotFoundError):
            with pytest.raises(RunnerError, match="not found"):
                runner.run_oneshot("test")

    def test_name(self):
        assert CodexRunner.name == "codex"
