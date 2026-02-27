"""ctxforge clean command."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import typer
from rich.console import Console

console = Console()

CTXFORGE_DIR = ".ctxforge"
_COMMAND_FILES = ["ctx-profile.md", "ctx-files.md", "ctx-update.md", "ctx-compress.md"]


def _confirm(text: str, default: bool = False) -> bool:
    """Yes/no prompt bypassing readline."""
    hint = "Y/n" if default else "y/N"
    console.print(f"{text} \\[{hint}]: ", end="")
    value = sys.stdin.readline().strip().lower()
    if not value:
        return default
    return value in ("y", "yes")


def clean_command(
    path: Path = typer.Argument(
        Path("."),
        help="Project root directory.",
        exists=True,
        file_okay=False,
        resolve_path=True,
    ),
) -> None:
    """Remove all ctxforge configuration (.ctxforge/ directory)."""
    ctxforge_dir = path / CTXFORGE_DIR

    if not ctxforge_dir.exists():
        console.print(f"[yellow]Nothing to clean:[/yellow] {CTXFORGE_DIR}/ not found.")
        return

    if not _confirm(f"Delete {ctxforge_dir} and all its contents?"):
        console.print("Cancelled.")
        return

    shutil.rmtree(ctxforge_dir)
    console.print(f"[bold green]Removed[/bold green] {CTXFORGE_DIR}/")

    # Clean up generated slash commands
    commands_dir = path / ".claude" / "commands"
    if commands_dir.is_dir():
        removed = []
        for name in _COMMAND_FILES:
            cmd_file = commands_dir / name
            if cmd_file.exists():
                cmd_file.unlink()
                removed.append(name)
        if removed:
            console.print(
                f"[bold green]Removed[/bold green] {len(removed)} slash command(s) "
                f"from .claude/commands/"
            )
