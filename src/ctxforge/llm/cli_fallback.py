"""CLI fallback — call LLM via CLI tools when native SDK is not installed."""

from __future__ import annotations

import shutil
import subprocess

_PROVIDER_CLI_MAP: dict[str, str] = {
    "anthropic": "claude",
}


class CLIFallbackError(Exception):
    """Raised when CLI fallback invocation fails."""


def get_fallback_cli(provider: str) -> str | None:
    """Return the CLI tool name for a provider, or ``None`` if unmapped."""
    return _PROVIDER_CLI_MAP.get(provider)


def is_cli_available(cli_name: str) -> bool:
    """Check whether *cli_name* is on ``PATH``."""
    return shutil.which(cli_name) is not None


def call_via_cli(
    cli_name: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
) -> str:
    """Invoke an LLM via its CLI tool and return the text output.

    Raises:
        CLIFallbackError: If the subprocess fails or the CLI is not found.
    """
    combined = _combine_prompts(system_prompt, user_prompt)
    try:
        result = subprocess.run(
            [cli_name, "-p", combined, "--model", model],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        msg = f"CLI tool '{cli_name}' not found"
        raise CLIFallbackError(msg) from exc

    if result.returncode != 0:
        stderr = result.stderr.strip()
        msg = f"CLI tool '{cli_name}' exited with code {result.returncode}: {stderr}"
        raise CLIFallbackError(msg)

    return result.stdout.strip()


def _combine_prompts(system_prompt: str, user_prompt: str) -> str:
    """Merge system and user prompts into a single string for CLI usage."""
    return f"[System]\n{system_prompt}\n\n[User]\n{user_prompt}"
