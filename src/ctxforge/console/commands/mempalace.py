"""ctxforge mempalace — manage project-level MemPalace integration."""

from __future__ import annotations

import typer
from rich.console import Console

from ctxforge.core.memory import MemoryBinding, validate_mempalace_installation
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


def resolve_memory_binding_for_status(project: Project) -> MemoryBinding | None:
    from ctxforge.core.memory import resolve_memory_binding

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
    binding = resolve_memory_binding_for_status(project)
    sync_claude_memory_hooks(project.root, binding)
    console.print(f"[green]Updated MemPalace checkpoint interval to {value}.[/green]")


app.add_typer(set_app, name="set")
