"""Tests for CodexRunner."""

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

    def test_run_empty_system_prompt(self):
        runner = CodexRunner()
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("ctxforge.runner.codex.subprocess.run", return_value=mock_result) as mock_run:
            result = runner.run("")
            mock_run.assert_called_once_with(["codex"])
        assert result.ok

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

    def test_name(self):
        assert CodexRunner.name == "codex"
