"""Tests for ClaudeRunner."""

from unittest.mock import MagicMock, patch

import pytest

from ctxforge.exceptions import RunnerError
from ctxforge.runner.claude import ClaudeRunner


def _get_cmd(mock_run: MagicMock) -> list[str]:
    """Extract the command list from a subprocess.run mock call."""
    return mock_run.call_args[0][0]


class TestClaudeRunner:
    def test_run_success(self):
        runner = ClaudeRunner()
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("ctxforge.runner.claude.subprocess.run", return_value=mock_result) as mock_run:
            result = runner.run("system context", session_id="test-id")
            cmd = _get_cmd(mock_run)
        assert cmd[0] == "claude"
        assert "--session-id" in cmd
        assert cmd[cmd.index("--session-id") + 1] == "test-id"
        assert "--append-system-prompt" in cmd
        assert "system context" in cmd
        assert result.ok

    def test_run_with_initial_prompt(self):
        runner = ClaudeRunner()
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("ctxforge.runner.claude.subprocess.run", return_value=mock_result) as mock_run:
            result = runner.run("system context", "hello", session_id="test-id")
            cmd = _get_cmd(mock_run)
        assert "--session-id" in cmd
        assert "--append-system-prompt" in cmd
        assert "hello" in cmd
        assert result.ok

    def test_run_auto_approve(self):
        runner = ClaudeRunner()
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("ctxforge.runner.claude.subprocess.run", return_value=mock_result) as mock_run:
            result = runner.run("system context", auto_approve=True, session_id="test-id")
            cmd = _get_cmd(mock_run)
        assert "--dangerously-skip-permissions" in cmd
        assert "--session-id" in cmd
        assert "--append-system-prompt" in cmd
        assert result.ok

    def test_run_empty_system_prompt(self):
        runner = ClaudeRunner()
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("ctxforge.runner.claude.subprocess.run", return_value=mock_result) as mock_run:
            result = runner.run("")
            cmd = _get_cmd(mock_run)
        assert cmd[0] == "claude"
        assert "--append-system-prompt" not in cmd
        assert result.ok

    def test_run_no_session_flags_by_default(self):
        """Without session_id or resume_id, no session flags are added."""
        runner = ClaudeRunner()
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("ctxforge.runner.claude.subprocess.run", return_value=mock_result) as mock_run:
            runner.run("prompt")
            cmd = _get_cmd(mock_run)
        assert "--session-id" not in cmd
        assert "--resume" not in cmd

    def test_run_resume_session(self):
        """resume_id passes --resume and skips system prompt injection."""
        runner = ClaudeRunner()
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("ctxforge.runner.claude.subprocess.run", return_value=mock_result) as mock_run:
            result = runner.run("system context", "greeting", resume_id="abc-123")
            cmd = _get_cmd(mock_run)
        assert "--resume" in cmd
        assert cmd[cmd.index("--resume") + 1] == "abc-123"
        assert "--session-id" not in cmd
        assert "--append-system-prompt" not in cmd
        assert "greeting" not in cmd
        assert result.ok

    def test_run_resume_with_mcp(self):
        """MCP config is still passed when resuming."""
        runner = ClaudeRunner()
        mock_result = MagicMock()
        mock_result.returncode = 0
        from pathlib import Path

        with patch("ctxforge.runner.claude.subprocess.run", return_value=mock_result) as mock_run:
            runner.run("ctx", resume_id="abc", mcp_config=Path("/tmp/mcp.json"))
            cmd = _get_cmd(mock_run)
        assert "--resume" in cmd
        assert "--mcp-config" in cmd
        assert "--append-system-prompt" not in cmd

    def test_run_failure(self):
        runner = ClaudeRunner()
        mock_result = MagicMock()
        mock_result.returncode = 1

        with patch("ctxforge.runner.claude.subprocess.run", return_value=mock_result):
            result = runner.run("system context")
        assert not result.ok
        assert result.exit_code == 1

    def test_run_not_found(self):
        runner = ClaudeRunner()
        with patch("ctxforge.runner.claude.subprocess.run", side_effect=FileNotFoundError):
            with pytest.raises(RunnerError, match="not found"):
                runner.run("test")

    def test_run_oneshot_success(self):
        runner = ClaudeRunner()
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("ctxforge.runner.claude.subprocess.run", return_value=mock_result) as mock_run:
            result = runner.run_oneshot("update key files")
            cmd = _get_cmd(mock_run)
        assert "--no-session-persistence" in cmd
        assert "-p" in cmd
        assert "update key files" in cmd
        assert result.ok

    def test_run_oneshot_auto_approve(self):
        runner = ClaudeRunner()
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("ctxforge.runner.claude.subprocess.run", return_value=mock_result) as mock_run:
            result = runner.run_oneshot("update key files", auto_approve=True)
            cmd = _get_cmd(mock_run)
        assert "--dangerously-skip-permissions" in cmd
        assert "--no-session-persistence" in cmd
        assert "-p" in cmd
        assert result.ok

    def test_run_oneshot_not_found(self):
        runner = ClaudeRunner()
        with patch("ctxforge.runner.claude.subprocess.run", side_effect=FileNotFoundError):
            with pytest.raises(RunnerError, match="not found"):
                runner.run_oneshot("test")

    def test_name(self):
        assert ClaudeRunner.name == "claude"
