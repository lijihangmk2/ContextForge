"""Tests for ctxforge.llm.provider module."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from ctxforge.llm.provider import (
    DEFAULT_MODEL,
    PROVIDER_ANTHROPIC,
    PROVIDER_GOOGLE,
    PROVIDER_OPENAI,
    SDKNotInstalledError,
    call_llm,
    detect_provider,
    get_default_model,
)


class TestDetectProvider:
    @pytest.mark.parametrize(
        ("model", "expected"),
        [
            ("gpt-4o", PROVIDER_OPENAI),
            ("gpt-4o-mini", PROVIDER_OPENAI),
            ("o1-preview", PROVIDER_OPENAI),
            ("o3-mini", PROVIDER_OPENAI),
            ("o4-mini", PROVIDER_OPENAI),
            ("claude-sonnet-4-20250514", PROVIDER_ANTHROPIC),
            ("claude-3-haiku-20240307", PROVIDER_ANTHROPIC),
            ("gemini-1.5-pro", PROVIDER_GOOGLE),
            ("gemini-2.0-flash", PROVIDER_GOOGLE),
        ],
    )
    def test_known_prefixes(self, model: str, expected: str) -> None:
        assert detect_provider(model) == expected

    def test_case_insensitive(self) -> None:
        assert detect_provider("GPT-4o") == PROVIDER_OPENAI
        assert detect_provider("Claude-Sonnet-4-20250514") == PROVIDER_ANTHROPIC
        assert detect_provider("GEMINI-2.0-flash") == PROVIDER_GOOGLE

    def test_unknown_model_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown model prefix"):
            detect_provider("llama-3")


class TestGetDefaultModel:
    def test_claude_cli(self) -> None:
        assert get_default_model("claude") == "claude-sonnet-4-20250514"

    def test_codex_cli(self) -> None:
        assert get_default_model("codex") == "o4-mini"

    def test_copilot_cli(self) -> None:
        assert get_default_model("copilot") == "gpt-4o"

    def test_unknown_cli(self) -> None:
        assert get_default_model("unknown-tool") == DEFAULT_MODEL

    def test_none_cli(self) -> None:
        assert get_default_model(None) == DEFAULT_MODEL


class TestCallLlm:
    def test_dispatches_to_openai(self) -> None:
        with patch("ctxforge.llm.provider._call_openai", return_value="ok") as mock:
            result = call_llm("gpt-4o", "sys", "user")
        assert result == "ok"
        mock.assert_called_once_with("gpt-4o", "sys", "user")

    def test_dispatches_to_anthropic(self) -> None:
        with patch("ctxforge.llm.provider._call_anthropic", return_value="ok") as mock:
            result = call_llm("claude-sonnet-4-20250514", "sys", "user")
        assert result == "ok"
        mock.assert_called_once_with("claude-sonnet-4-20250514", "sys", "user")

    def test_dispatches_to_google(self) -> None:
        with patch("ctxforge.llm.provider._call_google", return_value="ok") as mock:
            result = call_llm("gemini-2.0-flash", "sys", "user")
        assert result == "ok"
        mock.assert_called_once_with("gemini-2.0-flash", "sys", "user")

    def test_unknown_model_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown model prefix"):
            call_llm("llama-3", "sys", "user")

    def test_openai_sdk_not_installed(self) -> None:
        with patch.dict("sys.modules", {"openai": None}):
            with pytest.raises(SDKNotInstalledError, match="openai SDK is not installed"):
                call_llm("gpt-4o", "sys", "user")

    def test_anthropic_sdk_not_installed(self) -> None:
        with (
            patch.dict("sys.modules", {"anthropic": None}),
            patch(
                "ctxforge.llm.cli_fallback.is_cli_available", return_value=False
            ),
        ):
            with pytest.raises(SDKNotInstalledError, match="anthropic SDK is not installed"):
                call_llm("claude-sonnet-4-20250514", "sys", "user")

    def test_google_sdk_not_installed(self) -> None:
        with patch.dict("sys.modules", {"google.generativeai": None, "google": None}):
            with pytest.raises(
                SDKNotInstalledError, match="google SDK is not installed"
            ):
                call_llm("gemini-2.0-flash", "sys", "user")


class TestCallLlmFallback:
    """Tests for SDK-missing → CLI fallback in call_llm."""

    def test_sdk_missing_cli_available_succeeds(self) -> None:
        with (
            patch.dict("sys.modules", {"anthropic": None}),
            patch(
                "ctxforge.llm.cli_fallback.is_cli_available", return_value=True
            ),
            patch(
                "ctxforge.llm.cli_fallback.call_via_cli",
                return_value="cli-response",
            ),
        ):
            result = call_llm("claude-sonnet-4-20250514", "sys", "user")
        assert result == "cli-response"

    def test_sdk_and_cli_both_missing_raises(self) -> None:
        with (
            patch.dict("sys.modules", {"anthropic": None}),
            patch(
                "ctxforge.llm.cli_fallback.is_cli_available", return_value=False
            ),
        ):
            with pytest.raises(SDKNotInstalledError, match="anthropic SDK is not installed"):
                call_llm("claude-sonnet-4-20250514", "sys", "user")

    def test_cli_failure_raises(self) -> None:
        from ctxforge.llm.cli_fallback import CLIFallbackError

        with (
            patch.dict("sys.modules", {"anthropic": None}),
            patch(
                "ctxforge.llm.cli_fallback.is_cli_available", return_value=True
            ),
            patch(
                "ctxforge.llm.cli_fallback.call_via_cli",
                side_effect=CLIFallbackError("cli boom"),
            ),
        ):
            with pytest.raises(SDKNotInstalledError, match="CLI fallback also failed"):
                call_llm("claude-sonnet-4-20250514", "sys", "user")
