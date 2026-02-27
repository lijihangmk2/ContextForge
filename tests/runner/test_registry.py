"""Tests for runner registry."""

import pytest

from ctxforge.runner.registry import get_runner
from ctxforge.runner.claude import ClaudeRunner
from ctxforge.exceptions import CliNotFoundError


class TestRegistry:
    def test_get_claude(self):
        runner = get_runner("claude")
        assert isinstance(runner, ClaudeRunner)

    def test_unknown_runner(self):
        with pytest.raises(CliNotFoundError, match="nonexistent"):
            get_runner("nonexistent")

    def test_error_lists_available(self):
        with pytest.raises(CliNotFoundError, match="claude"):
            get_runner("unknown")
