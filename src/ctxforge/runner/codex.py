"""Codex CLI runner — launch interactive ``codex`` session."""

from __future__ import annotations

import subprocess

from ctxforge.exceptions import RunnerError
from ctxforge.runner.base import RunResult


class CodexRunner:
    """Launch an interactive Codex CLI session with optional context injection.

    Codex does not support a ``--system-prompt`` flag, so the context is
    combined into the initial ``[PROMPT]`` positional argument.
    """

    name: str = "codex"

    def run(self, system_prompt: str, initial_prompt: str = "") -> RunResult:
        """Start an interactive ``codex`` session.

        *system_prompt* and *initial_prompt* are merged into a single
        positional argument since Codex only accepts ``[PROMPT]``.
        """
        cmd: list[str] = ["codex"]

        combined = "\n\n".join(p for p in [system_prompt, initial_prompt] if p)
        if combined:
            cmd.append(combined)

        try:
            proc = subprocess.run(cmd)
        except FileNotFoundError as e:
            raise RunnerError("codex CLI not found on PATH") from e
        except Exception as e:
            raise RunnerError(f"Failed to run codex: {e}") from e

        return RunResult(exit_code=proc.returncode, stdout="", stderr="")
