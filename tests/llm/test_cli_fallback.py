"""Tests for ctxforge.llm.cli_fallback module."""

from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest

from ctxforge.llm.cli_fallback import (
    CLIFallbackError,
    _combine_prompts,
    call_via_cli,
    get_fallback_cli,
    is_cli_available,
)


class TestGetFallbackCli:
    def test_anthropic_maps_to_claude(self) -> None:
        assert get_fallback_cli("anthropic") == "claude"

    def test_openai_returns_none(self) -> None:
        assert get_fallback_cli("openai") is None

    def test_unknown_returns_none(self) -> None:
        assert get_fallback_cli("some-unknown") is None


class TestIsCliAvailable:
    def test_available(self) -> None:
        with patch("ctxforge.llm.cli_fallback.shutil.which", return_value="/usr/bin/claude"):
            assert is_cli_available("claude") is True

    def test_not_available(self) -> None:
        with patch("ctxforge.llm.cli_fallback.shutil.which", return_value=None):
            assert is_cli_available("claude") is False


class TestCallViaCli:
    def test_success(self) -> None:
        fake = subprocess.CompletedProcess(
            args=["claude"], returncode=0, stdout="hello\n", stderr=""
        )
        with patch("ctxforge.llm.cli_fallback.subprocess.run", return_value=fake):
            result = call_via_cli("claude", "model-x", "sys", "usr")
        assert result == "hello"

    def test_nonzero_exit_raises(self) -> None:
        fake = subprocess.CompletedProcess(
            args=["claude"], returncode=1, stdout="", stderr="bad request"
        )
        with patch("ctxforge.llm.cli_fallback.subprocess.run", return_value=fake):
            with pytest.raises(CLIFallbackError, match="exited with code 1"):
                call_via_cli("claude", "model-x", "sys", "usr")

    def test_file_not_found_raises(self) -> None:
        with patch(
            "ctxforge.llm.cli_fallback.subprocess.run",
            side_effect=FileNotFoundError("not found"),
        ):
            with pytest.raises(CLIFallbackError, match="not found"):
                call_via_cli("claude", "model-x", "sys", "usr")


class TestCombinePrompts:
    def test_format(self) -> None:
        result = _combine_prompts("You are helpful.", "What is 1+1?")
        assert result == "[System]\nYou are helpful.\n\n[User]\nWhat is 1+1?"

    def test_empty_system(self) -> None:
        result = _combine_prompts("", "question")
        assert result == "[System]\n\n\n[User]\nquestion"
