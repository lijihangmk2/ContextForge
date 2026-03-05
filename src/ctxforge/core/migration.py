"""Schema migration — interactive upgrade of profile.toml on version mismatch."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

from rich.console import Console

from ctxforge.spec.schema import (
    CURRENT_PROFILE_VERSION,
    ProfileCliSection,
    ProfileConfig,
    ProjectConfig,
)
from ctxforge.storage.profile_writer import write_profile

console = Console()

MigrateFn = Callable[[ProfileConfig, ProjectConfig], None]

# ── Interactive helpers ──────────────────────────────────────────────────────


def _confirm(text: str, default: bool = False) -> bool:
    hint = "Y/n" if default else "y/N"
    console.print(f"{text} \\[{hint}]: ", end="")
    value = sys.stdin.readline().strip().lower()
    if not value:
        return default
    return value in ("y", "yes")


def _select_cli(
    detected: list[str], default: str | None,
) -> str | None:
    """Let the user pick a CLI for a profile."""
    if not detected:
        return None
    if len(detected) == 1:
        console.print(f"  CLI: [bold]{detected[0]}[/bold]")
        return detected[0]
    # Multiple CLIs — ask
    console.print("  Select CLI for this profile:")
    for i, name in enumerate(detected, 1):
        marker = " (current)" if name == default else ""
        console.print(f"    [{i}] {name}{marker}")
    console.print(f"  Choice \\[{default or detected[0]}]: ", end="")
    value = sys.stdin.readline().strip()
    if not value:
        return default or detected[0]
    try:
        return detected[int(value) - 1]
    except (ValueError, IndexError):
        return default or detected[0]


# ── Migration steps ──────────────────────────────────────────────────────────
#
# Each entry: (target_version, interactive_migrate_fn)
# The function upgrades from (target - 1) → target, mutating config in place.


def _migrate_v1_to_v2(
    config: ProfileConfig,
    project_config: ProjectConfig,
) -> None:
    """v1 → v2: move CLI from project to profile, add auto_approve."""
    detected = project_config.cli.detected
    legacy_active = project_config.cli.active

    console.print(
        f"\n[bold]Upgrading profile '{config.profile.name}' "
        f"(v1 → v2)[/bold]"
    )

    cli_name = _select_cli(detected, legacy_active)
    auto_approve = _confirm(
        "  Auto-approve CLI operations (skip permission prompts)?",
    )
    if auto_approve:
        console.print(
            "  [yellow]CLI will run without permission prompts.[/yellow]"
        )

    config.cli = ProfileCliSection(
        name=cli_name, auto_approve=auto_approve,
    )


_MIGRATIONS: list[tuple[int, MigrateFn]] = [
    (2, _migrate_v1_to_v2),
]


# ── Public API ───────────────────────────────────────────────────────────────


def needs_migration(config: ProfileConfig) -> bool:
    """Check if a profile config needs migration."""
    return config.schema_version < CURRENT_PROFILE_VERSION


def migrate_profile(
    config: ProfileConfig,
    project_config: ProjectConfig,
    profile_path: Path,
) -> ProfileConfig:
    """Run all pending migrations and write back to disk.

    Interactive (tty): prompts user for each new setting.
    Non-interactive (piped stdin): uses safe defaults silently.
    """
    if config.schema_version >= CURRENT_PROFILE_VERSION:
        return config

    interactive = sys.stdin.isatty()

    for target, migrate_fn in _MIGRATIONS:
        if config.schema_version >= target:
            continue
        if interactive:
            migrate_fn(config, project_config)
        else:
            _apply_defaults(config, project_config, target)
        config.schema_version = target

    write_profile(profile_path, config)
    if interactive:
        console.print(
            f"  [green]Saved profile '{config.profile.name}' "
            f"(v{config.schema_version})[/green]\n"
        )
    return config


def _apply_defaults(
    config: ProfileConfig,
    project_config: ProjectConfig,
    target: int,
) -> None:
    """Apply non-interactive defaults for a specific migration step."""
    if target == 2:
        config.cli = ProfileCliSection(
            name=project_config.cli.active,
            auto_approve=False,
        )
