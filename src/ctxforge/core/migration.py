"""Schema migration — interactive upgrade of profile.toml on version mismatch."""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

from rich.console import Console

from ctxforge.spec.schema import (
    CURRENT_PROFILE_VERSION,
    CURRENT_PROJECT_VERSION,
    DEFAULT_WORK_RECORD,
    ProfileCliSection,
    ProfileConfig,
    ProjectConfig,
    ToolsSection,
    WorkRecordSection,
)
from ctxforge.storage.profile_writer import write_profile
from ctxforge.storage.project_writer import write_project

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


def _migrate_v2_to_v3(
    config: ProfileConfig,
    project_config: ProjectConfig,
) -> None:
    """v2 → v3: add work_record section with default files."""
    console.print(
        f"\n[bold]Upgrading profile '{config.profile.name}' "
        f"(v2 → v3)[/bold]"
    )
    console.print("  Adding work record: journal.md, pitfalls.md")
    config.work_record = WorkRecordSection(files=dict(DEFAULT_WORK_RECORD))


def _migrate_v3_to_v4(
    config: ProfileConfig,
    project_config: ProjectConfig,
) -> None:
    """v3 → v4: add tools section."""
    console.print(
        f"\n[bold]Upgrading profile '{config.profile.name}' "
        f"(v3 → v4)[/bold]"
    )
    console.print("  Adding tools section (empty)")
    config.tools = ToolsSection()


def _migrate_v4_to_v5(
    config: ProfileConfig,
    project_config: ProjectConfig,
) -> None:
    """v4 → v5: tools.enabled → tools.disabled (all tools active by default)."""
    console.print(
        f"\n[bold]Upgrading profile '{config.profile.name}' "
        f"(v4 → v5)[/bold]"
    )
    # Previously enabled tools become the default (all active),
    # so disabled = all project tools MINUS the old enabled list.
    old_enabled = getattr(config.tools, "enabled", None) or []
    if old_enabled and project_config.tools:
        disabled = [t for t in project_config.tools if t not in old_enabled]
    else:
        disabled = []
    config.tools = ToolsSection(disabled=disabled)
    if disabled:
        console.print(f"  Disabled tools: {', '.join(disabled)}")
    else:
        console.print("  All project tools active by default")


def _migrate_v5_to_v6(
    config: ProfileConfig,
    project_config: ProjectConfig,
) -> None:
    """v5 → v6: add usermemo.md to work record files."""
    console.print(
        f"\n[bold]Upgrading profile '{config.profile.name}' "
        f"(v5 → v6)[/bold]"
    )
    memo_key = "usermemo.md"
    memo_desc = DEFAULT_WORK_RECORD[memo_key]
    if memo_key not in config.work_record.files:
        config.work_record.files[memo_key] = memo_desc
        console.print(f"  Adding work record: {memo_key}")
    else:
        console.print(f"  {memo_key} already present")


_MIGRATIONS: list[tuple[int, MigrateFn]] = [
    (2, _migrate_v1_to_v2),
    (3, _migrate_v2_to_v3),
    (4, _migrate_v3_to_v4),
    (5, _migrate_v4_to_v5),
    (6, _migrate_v5_to_v6),
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
    elif target == 3:
        config.work_record = WorkRecordSection(
            files=dict(DEFAULT_WORK_RECORD),
        )
    elif target == 4:
        config.tools = ToolsSection()
    elif target == 5:
        config.tools = ToolsSection()
    elif target == 6:
        memo_key = "usermemo.md"
        if memo_key not in config.work_record.files:
            config.work_record.files[memo_key] = DEFAULT_WORK_RECORD[memo_key]


# ── Project migration ───────────────────────────────────────────────────────


def needs_project_migration(config: ProjectConfig) -> bool:
    """Check if a project config needs migration."""
    return config.schema_version < CURRENT_PROJECT_VERSION


def migrate_project(
    config: ProjectConfig,
    project_path: Path,
) -> ProjectConfig:
    """Run project migrations and write back to disk."""
    if config.schema_version >= CURRENT_PROJECT_VERSION:
        return config

    if config.schema_version < 2:
        config.tools = {}
        config.schema_version = 2
        write_project(project_path, config)
        if sys.stdin.isatty():
            console.print(
                "  [green]Upgraded project.toml (v1 → v2): "
                "added tools registry[/green]\n"
            )

    return config
