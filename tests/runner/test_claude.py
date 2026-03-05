"""Tests for ClaudeRunner."""

from unittest.mock import MagicMock, patch

import pytest

from ctxforge.exceptions import RunnerError
from ctxforge.runner.claude import ClaudeRunner


class TestClaudeRunner:
    def test_run_success(self):
        runner = ClaudeRunner()
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("ctxforge.runner.claude.subprocess.run", return_value=mock_result) as mock_run:
            result = runner.run("system context")
            mock_run.assert_called_once_with(
                ["claude", "--append-system-prompt", "system context"],
            )
        assert result.ok
        assert result.stdout == ""
        assert result.stderr == ""

    def test_run_with_initial_prompt(self):
        runner = ClaudeRunner()
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("ctxforge.runner.claude.subprocess.run", return_value=mock_result) as mock_run:
            result = runner.run("system context", "hello")
            mock_run.assert_called_once_with(
                ["claude", "--append-system-prompt", "system context", "hello"],
            )
        assert result.ok

    def test_run_auto_approve(self):
        runner = ClaudeRunner()
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("ctxforge.runner.claude.subprocess.run", return_value=mock_result) as mock_run:
            result = runner.run("system context", auto_approve=True)
            mock_run.assert_called_once_with(
                ["claude", "--dangerously-skip-permissions", "--append-system-prompt", "system context"],
            )
        assert result.ok

    def test_run_empty_system_prompt(self):
        runner = ClaudeRunner()
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("ctxforge.runner.claude.subprocess.run", return_value=mock_result) as mock_run:
            result = runner.run("")
            mock_run.assert_called_once_with(["claude"])
        assert result.ok

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
            mock_run.assert_called_once_with(
                ["claude", "-p", "update key files"],
            )
        assert result.ok

    def test_run_oneshot_auto_approve(self):
        runner = ClaudeRunner()
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("ctxforge.runner.claude.subprocess.run", return_value=mock_result) as mock_run:
            result = runner.run_oneshot("update key files", auto_approve=True)
            mock_run.assert_called_once_with(
                ["claude", "--dangerously-skip-permissions", "-p", "update key files"],
            )
        assert result.ok

    def test_run_oneshot_not_found(self):
        runner = ClaudeRunner()
        with patch("ctxforge.runner.claude.subprocess.run", side_effect=FileNotFoundError):
            with pytest.raises(RunnerError, match="not found"):
                runner.run_oneshot("test")

    def test_name(self):
        assert ClaudeRunner.name == "claude"
