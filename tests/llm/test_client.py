"""Tests for ctxforge.llm.client module."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from ctxforge.llm.client import (
    LLMNotAvailableError,
    _parse_file_list,
    suggest_key_files,
)
from ctxforge.llm.provider import SDKNotInstalledError


class TestParseFileList:
    def test_parse_json_array(self):
        assert _parse_file_list('["src/main.py", "README.md"]') == [
            "src/main.py",
            "README.md",
        ]

    def test_parse_json_with_surrounding_text(self):
        content = 'Here are the files:\n["a.py", "b.py"]\nDone.'
        assert _parse_file_list(content) == ["a.py", "b.py"]

    def test_parse_empty_array(self):
        assert _parse_file_list("[]") == []

    def test_parse_invalid_json(self):
        assert _parse_file_list("not json at all") == []

    def test_parse_filters_non_strings(self):
        assert _parse_file_list('["a.py", 123, "b.py"]') == ["a.py", "b.py"]


class TestSuggestKeyFiles:
    def test_sdk_not_installed(self):
        """SDKNotInstalledError propagates as LLMNotAvailableError."""
        with patch(
            "ctxforge.llm.client.call_llm",
            side_effect=SDKNotInstalledError("openai is not installed"),
        ):
            with pytest.raises(LLMNotAvailableError, match="openai is not installed"):
                suggest_key_files(
                    model="gpt-4o",
                    project_name="test",
                    languages=["python"],
                    dir_tree=["src"],
                    config_files=["pyproject.toml"],
                )

    def test_successful_suggestion(self):
        with patch(
            "ctxforge.llm.client.call_llm",
            return_value='["README.md", "docs/architecture.md", "pyproject.toml"]',
        ):
            result = suggest_key_files(
                model="gpt-4o",
                project_name="myproject",
                languages=["python"],
                dir_tree=["src", "tests"],
                config_files=["pyproject.toml"],
                language="English",
            )

        assert result == ["README.md", "docs/architecture.md", "pyproject.toml"]

    def test_empty_response(self):
        with patch("ctxforge.llm.client.call_llm", return_value=""):
            result = suggest_key_files(
                model="gpt-4o",
                project_name="test",
                languages=[],
                dir_tree=[],
                config_files=[],
            )

        assert result == []
