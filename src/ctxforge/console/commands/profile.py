"""ctxforge profile sub-commands (create / list / show)."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from ctxforge.core.profile import ProfileManager
from ctxforge.core.project import Project
from ctxforge.exceptions import CForgeError, ProjectNotFoundError

console = Console()
profile_app = typer.Typer(
    name="profile",
    help="Manage AI role profiles.",
    no_args_is_help=True,
)


def _get_manager() -> tuple[Project, ProfileManager]:
    try:
        project = Project.load()
    except ProjectNotFoundError:
        raise CForgeError("No ctxforge project found. Run [bold]ctxforge init[/bold] first.")
    return project, ProfileManager(project.profiles_dir)


@profile_app.command("list")
def list_command() -> None:
    """List all profiles."""
    try:
        project, pm = _get_manager()
    except CForgeError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    names = pm.list_names()
    if not names:
        console.print("[yellow]No profiles found.[/yellow]")
        return

    default = project.config.defaults.profile
    table = Table(title="Profiles")
    table.add_column("Name")
    table.add_column("Default")
    for name in names:
        marker = "*" if name == default else ""
        table.add_row(name, marker)
    console.print(table)


@profile_app.command("create")
def create_command(
    name: str = typer.Argument(..., help="Profile name."),
    description: str = typer.Option("", "--desc", "-d", help="Role description."),
    role_prompt: str = typer.Option("", "--prompt", "-p", help="Role prompt."),
    key_files: str = typer.Option("", "--files", "-f", help="Comma-separated key file paths."),
) -> None:
    """Create a new profile."""
    try:
        _project, pm = _get_manager()
    except CForgeError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    if pm.exists(name):
        console.print(f"[yellow]Profile '{name}' already exists.[/yellow]")
        raise typer.Exit(1)

    files = [f.strip() for f in key_files.split(",") if f.strip()] if key_files else []
    pm.create(name=name, description=description, role_prompt=role_prompt, key_files=files)
    console.print(f"[green]Created profile '{name}'.[/green]")


@profile_app.command("show")
def show_command(
    name: str = typer.Argument(..., help="Profile name."),
) -> None:
    """Show profile details."""
    try:
        _project, pm = _get_manager()
    except CForgeError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    try:
        profile = pm.load(name)
    except CForgeError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    console.print(f"[bold]{profile.profile.name}[/bold]")
    if profile.profile.description:
        console.print(f"  Description: {profile.profile.description}")
    if profile.role.prompt:
        console.print(f"  Role prompt: {profile.role.prompt}")
    if profile.key_files.paths:
        console.print(f"  Key files: {', '.join(profile.key_files.paths)}")
    console.print(f"  Injection: {profile.injection.strategy} ({profile.injection.order})")
