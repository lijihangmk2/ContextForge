"""ctxforge profile sub-commands (create / list / show / edit)."""

from __future__ import annotations

import sys

import typer
from rich.console import Console
from rich.table import Table

from ctxforge.analysis.cli_detector import detect_ai_clis
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


def _prompt(text: str, default: str = "") -> str:
    """Prompt for input with proper CJK wide-character handling."""
    if sys.stdin.isatty():
        import questionary

        result = questionary.text(text, default=default).ask()
        if result is None:
            return default
        return result.strip() or default
    # Fallback for piped input (tests, CI)
    if default:
        console.print(f"{text} \\[{default}]: ", end="")
    else:
        console.print(f"{text}: ", end="")
    value = sys.stdin.readline().strip()
    return value if value else default


def _confirm(text: str, default: bool = False) -> bool:
    """Yes/no prompt bypassing readline."""
    hint = "Y/n" if default else "y/N"
    console.print(f"{text} \\[{hint}]: ", end="")
    value = sys.stdin.readline().strip().lower()
    if not value:
        return default
    return value in ("y", "yes")


def _select_cli(detected_clis: list[str], current: str | None) -> str | None:
    """Let the user pick a CLI, with the current one as default."""
    if not detected_clis:
        return current
    if len(detected_clis) == 1:
        console.print(f"  CLI: [bold]{detected_clis[0]}[/bold]")
        return detected_clis[0]
    # Build numbered list, mark current
    console.print("  Select CLI:")
    default_idx = 1
    for i, name in enumerate(detected_clis, 1):
        marker = " (current)" if name == current else ""
        console.print(f"    [{i}] {name}{marker}")
        if name == current:
            default_idx = i
    choice = _prompt("  Choice", default=str(default_idx))
    try:
        return detected_clis[int(choice) - 1]
    except (ValueError, IndexError):
        return current


@profile_app.command("edit")
def edit_command(
    name: str = typer.Argument(..., help="Profile name to edit."),
) -> None:
    """Interactively edit a profile's settings."""
    try:
        _project, pm = _get_manager()
    except CForgeError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    try:
        config = pm.load(name)
    except CForgeError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    console.print(f"[bold]Editing profile '{name}'[/bold]\n")

    new_name = _prompt("Profile name", default=config.profile.name)
    description = _prompt("Description", default=config.profile.description)
    role_prompt = _prompt("Role prompt", default=config.role.prompt)

    # CLI selection
    detected_clis = detect_ai_clis()
    cli_name = _select_cli(detected_clis, current=config.cli.name)

    # Auto-approve
    auto_approve = _confirm(
        "Auto-approve CLI operations?",
        default=config.cli.auto_approve,
    )

    try:
        updated = pm.edit(
            name,
            new_name=new_name if new_name != name else None,
            description=description,
            role_prompt=role_prompt,
            cli_name=cli_name,
            auto_approve=auto_approve,
        )
    except CForgeError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    display_name = updated.profile.name
    if new_name != name:
        console.print(f"\n[green]Renamed and updated profile '{name}' → '{display_name}'.[/green]")
    else:
        console.print(f"\n[green]Updated profile '{display_name}'.[/green]")


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
