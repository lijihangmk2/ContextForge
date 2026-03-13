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

    table = Table(title="Profiles")
    table.add_column("Name")
    for name in names:
        table.add_row(name)
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


@profile_app.command("edit")
def edit_command(
    name: str = typer.Argument(..., help="Profile name to edit."),
    new_name: str | None = typer.Option(None, "--name", "-n", help="New profile name."),
    description: str | None = typer.Option(None, "--desc", "-d", help="New description."),
    role_prompt: str | None = typer.Option(None, "--prompt", "-p", help="New role prompt."),
) -> None:
    """Edit a profile's name, description, or role prompt."""
    try:
        _project, pm = _get_manager()
    except CForgeError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    if new_name is None and description is None and role_prompt is None:
        console.print("[yellow]Nothing to change. Use --name, --desc, or --prompt.[/yellow]")
        raise typer.Exit(1)

    try:
        config = pm.edit(name, new_name=new_name, description=description, role_prompt=role_prompt)
    except CForgeError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    display_name = config.profile.name
    if new_name and new_name != name:
        console.print(f"[green]Renamed profile '{name}' → '{display_name}'.[/green]")
    else:
        console.print(f"[green]Updated profile '{display_name}'.[/green]")


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
