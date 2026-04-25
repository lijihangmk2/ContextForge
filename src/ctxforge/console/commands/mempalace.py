"""ctxforge mempalace — manage project-level MemPalace integration."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console

from ctxforge.core.memory import (
    MemoryBinding,
    build_mempalace_mcp_server,
    load_memory_preload,
    resolve_memory_binding,
    validate_mempalace_installation,
)
from ctxforge.core.profile import ProfileManager
from ctxforge.core.project import Project
from ctxforge.exceptions import CForgeError
from ctxforge.storage.claude_settings import sync_claude_memory_hooks
from ctxforge.storage.project_writer import write_project

console = Console()
app = typer.Typer(help="Manage MemPalace integration.", no_args_is_help=True)
set_app = typer.Typer(help="Configure MemPalace settings.", no_args_is_help=True)


def _load_project() -> Project:
    try:
        return Project.load()
    except CForgeError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


def _runtime_status_text(ok: bool, message: str = "") -> str:
    if ok:
        return "[green]available[/green]"
    return f"[red]unavailable[/red] {message}"


@app.command("enable")
def enable_command() -> None:
    """Enable project-level MemPalace integration."""
    project = _load_project()
    project.config.mempalace.enabled = True
    runtime = validate_mempalace_installation()
    if not runtime.ok:
        console.print(f"[red]Error:[/red] {runtime.message}")
        project.config.mempalace.enabled = False
        raise typer.Exit(1)

    write_project(project.ctxforge_dir / "project.toml", project.config)
    sync_claude_memory_hooks(project.root, None)
    console.print("[green]Enabled MemPalace for this project.[/green]")
    console.print(f"  Runtime: {_runtime_status_text(runtime.ok, runtime.message)}")
    console.print(
        f"  Checkpoint interval: {project.config.mempalace.checkpoint_interval}"
    )


@app.command("disable")
def disable_command() -> None:
    """Disable project-level MemPalace integration."""
    project = _load_project()
    project.config.mempalace.enabled = False
    write_project(project.ctxforge_dir / "project.toml", project.config)
    sync_claude_memory_hooks(project.root, None)
    console.print("[green]Disabled MemPalace for this project.[/green]")


@app.command("status")
def status_command() -> None:
    """Show project-level MemPalace status and availability."""
    project = _load_project()
    binding = resolve_memory_binding_for_status(project)
    runtime = validate_mempalace_installation()
    mempalace = project.config.mempalace

    console.print("[bold]MemPalace[/bold]")
    console.print(f"  Enabled: {'yes' if mempalace.enabled else 'no'}")
    palace_path = binding.palace_path if binding is not None else (
        project.root / ".ctxforge" / "memory" / "mempalace"
        if not project.config.mempalace.palace_path
        else project.config.mempalace.palace_path
    )
    console.print(f"  Palace path: {palace_path}")
    console.print(f"  Runtime: {_runtime_status_text(runtime.ok, runtime.message)}")
    console.print(f"  Autoload: {'yes' if mempalace.autoload else 'no'}")
    console.print(f"  Checkpoint interval: {mempalace.checkpoint_interval}")
    console.print(f"  Save on precompact: {'yes' if mempalace.save_on_precompact else 'no'}")


@app.command("debug")
def debug_command(
    profile: str | None = typer.Argument(
        None,
        help="Profile name to inspect (required when multiple profiles exist).",
    ),
) -> None:
    """Inspect MemPalace wiring and likely failure points."""
    project = _load_project()
    pm = ProfileManager(project.ctxforge_dir / "profiles")
    try:
        profile_name = pm.resolve(profile)
    except CForgeError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    profile_config = pm.load(profile_name)
    binding = resolve_memory_binding(project.root, profile_name, project.config)
    runtime = validate_mempalace_installation()
    preload = load_memory_preload(binding)
    hook_status = _inspect_claude_hooks(project.root)
    cli_name = profile_config.cli.name or "unknown"
    palace_path = (
        binding.palace_path
        if binding is not None
        else project.root / ".ctxforge" / "memory" / "mempalace"
    )
    mcp_server = build_mempalace_mcp_server(binding)

    console.print("[bold]MemPalace Debug[/bold]")
    console.print(f"  Profile: {profile_name}")
    console.print(f"  CLI: {cli_name}")
    console.print(f"  Project enabled: {'yes' if project.config.mempalace.enabled else 'no'}")
    console.print(f"  Runtime: {_runtime_status_text(runtime.ok, runtime.message)}")
    console.print(f"  Palace path: {palace_path}")
    console.print(f"  Palace exists: {'yes' if palace_path.exists() else 'no'}")
    if binding is None:
        console.print("  Binding: disabled")
    else:
        console.print(f"  Namespace: {binding.namespace}")
        console.print(f"  Wing: {binding.wing}")
        console.print(f"  Preload: {preload.status}")
    console.print(
        f"  Claude hooks: {'managed' if hook_status.managed else 'not managed'}"
    )
    console.print(f"  Claude settings: {hook_status.settings_path}")
    console.print(
        "  MemPalace MCP handoff: "
        + ("configured" if mcp_server else "not configured")
    )
    if cli_name == "claude":
        console.print("  Autosave support: yes (Claude hooks)")
    else:
        console.print("  Autosave support: no (currently only Claude hooks are supported)")
    if cli_name == "codex":
        console.print("  Codex MCP support: no (current CodexRunner does not pass mcp_config)")

    reasons = _likely_causes(
        cli_name=cli_name,
        palace_exists=palace_path.exists(),
        runtime_ok=runtime.ok,
        preload_status=preload.status,
        hooks_managed=hook_status.managed,
    )
    if reasons:
        console.print("  Likely issues:")
        for reason in reasons:
            console.print(f"    - {reason}")


def resolve_memory_binding_for_status(project: Project) -> MemoryBinding | None:
    return resolve_memory_binding(project.root, "status", project.config)


@set_app.command("interval")
def set_interval_command(
    value: int = typer.Argument(..., help="Save every N user messages."),
) -> None:
    """Set the MemPalace checkpoint interval for this project."""
    project = _load_project()
    if not project.config.mempalace.enabled:
        console.print(
            "[red]Error:[/red] MemPalace is not enabled for this project. "
            "Run [bold]ctxforge mempalace enable[/bold] first."
        )
        raise typer.Exit(1)
    if value < 1:
        console.print("[red]Error:[/red] Interval must be >= 1.")
        raise typer.Exit(1)

    project.config.mempalace.checkpoint_interval = value
    write_project(project.ctxforge_dir / "project.toml", project.config)
    # Hooks are profile-scoped; writing a synthetic "status" binding produces the
    # wrong namespace. The active Claude profile refreshes hooks on next run.
    sync_claude_memory_hooks(project.root, None)
    console.print(f"[green]Updated MemPalace checkpoint interval to {value}.[/green]")


app.add_typer(set_app, name="set")


class _ClaudeHookStatus:
    def __init__(self, settings_path: Path, managed: bool) -> None:
        self.settings_path = settings_path
        self.managed = managed


def _inspect_claude_hooks(project_root: Path) -> _ClaudeHookStatus:
    settings_path = project_root / ".claude" / "settings.local.json"
    if not settings_path.exists():
        return _ClaudeHookStatus(settings_path, False)
    try:
        raw = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _ClaudeHookStatus(settings_path, False)
    hooks = raw.get("hooks") if isinstance(raw, dict) else None
    if not isinstance(hooks, dict):
        return _ClaudeHookStatus(settings_path, False)
    serialized = json.dumps(hooks, ensure_ascii=False)
    return _ClaudeHookStatus(
        settings_path,
        "ctxforge hook memory" in serialized,
    )


def _likely_causes(
    *,
    cli_name: str,
    palace_exists: bool,
    runtime_ok: bool,
    preload_status: str,
    hooks_managed: bool,
) -> list[str]:
    reasons: list[str] = []
    if not runtime_ok:
        reasons.append("MemPalace runtime is unavailable, so neither preload nor MCP can work.")
    if cli_name != "claude":
        reasons.append(
            "Current profile is not using Claude, so automatic checkpoint hooks "
            "will not run."
        )
    if cli_name == "codex":
        reasons.append(
            "Current Codex runner does not pass MemPalace MCP config into the "
            "session."
        )
    if cli_name == "claude" and not hooks_managed:
        reasons.append(
            "Claude managed hooks are missing; autosave will not trigger until "
            "a Claude run refreshes them."
        )
    if preload_status == "error" and not palace_exists:
        reasons.append(
            "The MemPalace directory does not exist yet, so preload/search has "
            "nothing to load."
        )
    elif preload_status == "empty":
        reasons.append("The palace exists, but this namespace currently has no recalled memories.")
    return reasons
