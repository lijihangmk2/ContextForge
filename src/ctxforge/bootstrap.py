"""Lightweight CLI bootstrap with startup diagnostics."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _format_startup_diagnostics() -> list[str]:
    executable = Path(sys.executable).resolve()
    prefix = Path(sys.prefix).resolve()
    virtual_env_raw = os.environ.get("VIRTUAL_ENV", "").strip()

    lines = [
        "[ctxforge] Startup failed before CLI initialization.",
        f"[ctxforge] sys.executable = {executable}",
        f"[ctxforge] sys.prefix     = {prefix}",
    ]

    if virtual_env_raw:
        virtual_env = Path(virtual_env_raw).resolve()
        lines.append(f"[ctxforge] VIRTUAL_ENV    = {virtual_env}")
        if virtual_env != prefix:
            lines.append(
                "[ctxforge] Environment mismatch detected: "
                "VIRTUAL_ENV does not match the interpreter environment."
            )
    else:
        lines.append("[ctxforge] VIRTUAL_ENV    = <unset>")

    lines.extend(
        [
            "[ctxforge] This usually means the shell activation state and the actual "
            "Python environment are not aligned.",
            "[ctxforge] Suggested checks:",
            "[ctxforge]   - which ctxforge",
            "[ctxforge]   - python -c \"import sys; print(sys.executable); print(sys.prefix)\"",
            "[ctxforge]   - echo $VIRTUAL_ENV",
            "[ctxforge]   - pipx reinstall ctxforge",
        ]
    )
    return lines


def _print_startup_diagnostics() -> None:
    for line in _format_startup_diagnostics():
        print(line, file=sys.stderr)


def main() -> None:
    try:
        from ctxforge.console.application import main as app_main
    except KeyboardInterrupt:
        _print_startup_diagnostics()
        raise SystemExit(130) from None
    except Exception:
        _print_startup_diagnostics()
        raise

    app_main()
