"""Runner registry — map CLI names to runner implementations."""

from __future__ import annotations

from typing import Any

from ctxforge.exceptions import CliNotFoundError
from ctxforge.runner.claude import ClaudeRunner
from ctxforge.runner.codex import CodexRunner

# Built-in runners keyed by CLI tool name.
_RUNNERS: dict[str, Any] = {
    "claude": ClaudeRunner,
    "codex": CodexRunner,
}


def get_runner(cli_name: str) -> Any:
    """Look up and instantiate a runner by CLI tool name.

    Raises:
        CliNotFoundError: If no runner is registered for the given name.
    """
    runner_cls = _RUNNERS.get(cli_name)
    if runner_cls is None:
        raise CliNotFoundError(
            f"No runner registered for '{cli_name}'. "
            f"Available: {', '.join(_RUNNERS)}"
        )
    return runner_cls()
