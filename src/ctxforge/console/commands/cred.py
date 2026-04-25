"""ctxforge cred — manage system-level CLI credentials."""

from __future__ import annotations

import sys

import typer
from rich.console import Console
from rich.table import Table

from ctxforge.core.credentials import CredentialsManager
from ctxforge.exceptions import CredentialError

console = Console()

cred_app = typer.Typer(
    name="cred",
    help="Manage system-level Claude/Codex credentials.",
    no_args_is_help=True,
)


def _manager() -> CredentialsManager:
    manager = CredentialsManager()
    manager.ensure_store()
    return manager


def _prompt(text: str, default: str = "") -> str:
    """Prompt for text input."""
    if sys.stdin.isatty():
        import questionary

        result = questionary.text(text, default=default).ask()
        if result is None:
            raise typer.Exit(0)
        return result.strip() or default

    if default:
        console.print(f"{text} \\[{default}]: ", end="")
    else:
        console.print(f"{text}: ", end="")
    value = sys.stdin.readline().strip()
    return value if value else default


def _confirm(text: str, default: bool = False) -> bool:
    """Prompt for yes/no."""
    hint = "Y/n" if default else "y/N"
    console.print(f"{text} \\[{hint}]: ", end="")
    value = sys.stdin.readline().strip().lower()
    if not value:
        return default
    return value in {"y", "yes"}


def _select_cli(
    manager: CredentialsManager,
    cli_name: str | None,
    *,
    require_live: bool = False,
) -> str:
    """Resolve the target CLI, interactively when omitted."""
    if cli_name:
        return cli_name

    candidates = manager.supported_clis()
    if require_live:
        candidates = [name for name in candidates if manager.has_live_credentials(name)]

    if not candidates:
        label = "live credentials" if require_live else "supported CLIs"
        raise CredentialError(f"No {label} available.")

    if len(candidates) == 1:
        return candidates[0]

    if sys.stdin.isatty():
        import questionary

        result: str | None = questionary.select("Select CLI:", choices=candidates).ask()
        if result is None:
            raise typer.Exit(0)
        return result

    raise CredentialError("Multiple CLIs available. Specify --cli.")


def _select_name(
    manager: CredentialsManager,
    cli_name: str,
    name: str | None,
    *,
    action: str,
) -> str:
    """Resolve a managed credential name, interactively when omitted."""
    if name:
        return name

    names = [item.name for item in manager.list_credentials(cli_name)]
    if not names:
        raise CredentialError(f"No managed credentials found for {cli_name}.")
    if len(names) == 1:
        return names[0]

    if sys.stdin.isatty():
        import questionary

        result: str | None = questionary.select(
            f"Select {cli_name} credential to {action}:",
            choices=names,
        ).ask()
        if result is None:
            raise typer.Exit(0)
        return result

    raise CredentialError(f"Multiple {cli_name} credentials found. Specify a name.")


def _handle_error(exc: CredentialError) -> None:
    console.print(f"[red]Error:[/red] {exc}")
    raise typer.Exit(1)


def _resolve_capture_name(
    manager: CredentialsManager,
    cli_name: str,
    requested_name: str | None,
    *,
    overwrite: bool,
) -> str:
    """Resolve the capture name, with onboarding on first managed credential."""
    if not manager.has_live_credentials(cli_name):
        raise CredentialError(f"No live {cli_name} credentials found to capture.")

    suggested = requested_name or manager.suggested_name(cli_name)
    if requested_name is not None:
        return suggested

    if not manager.has_managed_credentials(cli_name):
        console.print(f"Credential store: [cyan]{manager.root}[/cyan]")
        console.print(f"  {cli_name}: first managed credential setup")

    existing_names = {item.name for item in manager.list_credentials(cli_name)}
    while True:
        candidate = _prompt(f"{cli_name} credential name", default=suggested)
        if overwrite or candidate not in existing_names:
            return candidate
        console.print(
            f"[yellow]Credential '{candidate}' already exists for {cli_name}.[/yellow]"
        )
        suggested = ""


@cred_app.command("list")
def list_command(
    cli_name: str | None = typer.Option(None, "--cli", help="Filter by CLI name."),
) -> None:
    """List managed credentials and show which one is currently in use."""
    manager = _manager()
    items = manager.list_credentials(cli_name)

    if not items:
        console.print("No managed credentials found. Use [bold]ctxforge cred capture[/bold].")
        return

    table = Table(title="Managed Credentials")
    table.add_column("CLI", style="cyan")
    table.add_column("Name")
    table.add_column("Current")
    table.add_column("Selected")
    table.add_column("Hint")

    for item in items:
        current = "[green]yes[/green]" if item.current else ""
        selected = "[dim]selected[/dim]" if item.selected else ""
        table.add_row(item.cli_name, item.name, current, selected, item.account_hint)

    console.print(table)


@cred_app.command("status")
def status_command() -> None:
    """Show live credential status for each supported CLI."""
    manager = _manager()
    for cli_name in manager.supported_clis():
        live_exists, current = manager.current_status(cli_name)
        if current:
            console.print(f"{cli_name}: [green]{current}[/green] is currently in use.")
        elif live_exists:
            console.print(f"{cli_name}: live credentials exist, but they are not managed.")
        else:
            console.print(f"{cli_name}: no live credentials detected.")


@cred_app.command("capture")
def capture_command(
    name: str | None = typer.Argument(None, help="Managed credential name."),
    cli_name: str | None = typer.Option(None, "--cli", help="CLI name: claude or codex."),
    overwrite: bool = typer.Option(False, "--overwrite", help="Overwrite existing name."),
) -> None:
    """Capture the current native CLI credentials into the managed store."""
    manager = _manager()
    try:
        resolved_cli = _select_cli(manager, cli_name, require_live=True)
        resolved_name = _resolve_capture_name(
            manager,
            resolved_cli,
            name,
            overwrite=overwrite,
        )
        captured = manager.capture(resolved_cli, resolved_name, overwrite=overwrite)
    except CredentialError as exc:
        _handle_error(exc)

    console.print(f"[green]Captured[/green] {captured.cli_name}:{captured.name}")


@cred_app.command("switch")
def switch_command(
    name: str | None = typer.Argument(None, help="Managed credential name."),
    cli_name: str | None = typer.Option(None, "--cli", help="CLI name: claude or codex."),
) -> None:
    """Switch the live CLI credentials to one managed snapshot."""
    manager = _manager()
    try:
        resolved_cli = _select_cli(manager, cli_name)
        resolved_name = _select_name(manager, resolved_cli, name, action="switch")
        switched = manager.switch(resolved_cli, resolved_name)
    except CredentialError as exc:
        _handle_error(exc)

    console.print(f"[green]Switched[/green] {switched.cli_name} to [bold]{switched.name}[/bold].")
    console.print(
        "[yellow]Any currently running sessions must be restarted after a "
        "credential switch.[/yellow]"
    )


@cred_app.command("remove")
def remove_command(
    name: str | None = typer.Argument(None, help="Managed credential name."),
    cli_name: str | None = typer.Option(None, "--cli", help="CLI name: claude or codex."),
    yes: bool = typer.Option(False, "--yes", help="Skip confirmation."),
) -> None:
    """Remove one managed credential snapshot."""
    manager = _manager()
    try:
        resolved_cli = _select_cli(manager, cli_name)
        resolved_name = _select_name(manager, resolved_cli, name, action="remove")
        if not yes and not _confirm(
            f"Remove managed credential {resolved_cli}:{resolved_name}?",
            default=False,
        ):
            raise typer.Exit(0)
        manager.remove(resolved_cli, resolved_name)
    except CredentialError as exc:
        _handle_error(exc)

    console.print(f"[green]Removed[/green] {resolved_cli}:{resolved_name}")


@cred_app.command("clean")
def clean_command(
    cli_name: str | None = typer.Option(None, "--cli", help="Only clean one CLI."),
    yes: bool = typer.Option(False, "--yes", help="Skip confirmation."),
) -> None:
    """Remove ctxforge-managed credentials from the store."""
    manager = _manager()
    if cli_name is not None and cli_name not in manager.supported_clis():
        _handle_error(CredentialError(f"Unsupported CLI: {cli_name}"))

    if not yes:
        target = f"{cli_name} managed credentials" if cli_name else "all managed credentials"
        if not _confirm(f"Clean {target} from {manager.root}?", default=False):
            raise typer.Exit(0)

    try:
        manager.clean(cli_name)
    except CredentialError as exc:
        _handle_error(exc)

    if cli_name:
        console.print(f"[green]Cleaned[/green] managed {cli_name} credentials.")
    else:
        console.print("[green]Cleaned[/green] all managed credentials.")
