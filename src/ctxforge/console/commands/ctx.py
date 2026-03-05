"""ctxforge ctx sub-commands (profile / files / update / compress)."""

from __future__ import annotations

import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from ctxforge.core.injection import SimpleInjection
from ctxforge.core.migration import migrate_profile, needs_migration
from ctxforge.core.profile import ProfileManager
from ctxforge.core.project import Project
from ctxforge.exceptions import CForgeError, ProjectNotFoundError
from ctxforge.runner.registry import get_runner
from ctxforge.spec.schema import ProfileConfig
from ctxforge.storage.commands_writer import _build_ctx_compress, _build_ctx_update

console = Console()
ctx_app = typer.Typer(
    name="ctx",
    help="Context inspection and AI-driven maintenance.",
    no_args_is_help=True,
)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _load_project() -> tuple[Project, ProfileManager]:
    try:
        project = Project.load()
    except ProjectNotFoundError:
        console.print(
            "[red]Error:[/red] No ctxforge project found. "
            "Run [bold]ctxforge init[/bold] first."
        )
        raise typer.Exit(1)
    except CForgeError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    return project, ProfileManager(project.profiles_dir)


def _resolve_profile(
    profile: str | None,
    pm: ProfileManager,
) -> str:
    """Resolve a single profile name (explicit > single > interactive)."""
    if profile:
        if not pm.exists(profile):
            console.print(f"[red]Error:[/red] Profile '{profile}' not found.")
            raise typer.Exit(1)
        return profile
    names = pm.list_names()
    if not names:
        console.print("[red]Error:[/red] No profiles found.")
        raise typer.Exit(1)
    if len(names) == 1:
        return names[0]
    # Multiple profiles — interactive selection
    if sys.stdin.isatty():
        import questionary

        chosen: str | None = questionary.select(
            "Select profile:", choices=names,
        ).ask()
        if chosen is None:
            raise typer.Exit(0)
        return chosen
    console.print(
        "[red]Error:[/red] Multiple profiles — specify one explicitly."
    )
    raise typer.Exit(1)


def _resolve_profiles(
    profile: str | None,
    all_flag: bool,
    pm: ProfileManager,
) -> list[str]:
    """Resolve profile list for update/compress."""
    names = pm.list_names()
    if not names:
        console.print("[red]Error:[/red] No profiles found.")
        raise typer.Exit(1)

    if all_flag:
        return names
    if profile:
        if not pm.exists(profile):
            console.print(
                f"[red]Error:[/red] Profile '{profile}' not found."
            )
            raise typer.Exit(1)
        return [profile]
    if len(names) == 1:
        return names

    # Multiple profiles — interactive selection with "* all" option
    if sys.stdin.isatty():
        import questionary

        choices = names + ["* all"]
        result = questionary.select(
            "Select profile:", choices=choices,
        ).ask()
        if result is None:
            raise typer.Exit(0)
        return names if result == "* all" else [result]
    console.print(
        "[red]Error:[/red] Multiple profiles — specify one or use --all."
    )
    raise typer.Exit(1)


def _ensure_context_files(profile_dir: Path, profile_config: ProfileConfig) -> None:
    """Ensure work record files exist in the profile directory."""
    for name in profile_config.work_record.files:
        path = profile_dir / name
        if not path.exists():
            path.write_text("", encoding="utf-8")


def _run_ai_prompt(
    project: Project, pm: ProfileManager,
    profile_name: str, prompt: str,
) -> int:
    """Build prompt and call AI CLI in non-interactive mode."""
    try:
        profile_config = pm.load(profile_name)
    except CForgeError as e:
        console.print(f"[red]Error:[/red] {e}")
        return 1

    if needs_migration(profile_config):
        profile_config = migrate_profile(
            profile_config,
            project.config,
            pm.profile_path(profile_name),
        )

    _ensure_context_files(pm.profile_path(profile_name).parent, profile_config)

    cli_name = profile_config.cli.name or project.config.cli.active
    if not cli_name:
        console.print("[red]Error:[/red] No CLI configured.")
        return 1

    auto_approve = profile_config.cli.auto_approve

    try:
        runner = get_runner(cli_name)
    except CForgeError as e:
        console.print(f"[red]Error:[/red] {e}")
        return 1

    try:
        result = runner.run_oneshot(prompt, auto_approve=auto_approve)
    except CForgeError as e:
        console.print(f"[red]Error:[/red] {e}")
        return 1

    return 0 if result.ok else result.exit_code


# ── Commands ─────────────────────────────────────────────────────────────────


@ctx_app.command("profile")
def profile_command(
    profile: str | None = typer.Argument(None, help="Profile name."),
) -> None:
    """Show profile configuration details."""
    project, pm = _load_project()
    resolved = _resolve_profile(profile, pm)

    try:
        config = pm.load(resolved)
    except CForgeError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    console.print(f"[bold]{config.profile.name}[/bold]")
    if config.profile.description:
        console.print(f"  Description: {config.profile.description}")
    if config.role.prompt:
        console.print(f"  Role prompt: {config.role.prompt}")

    record_paths = SimpleInjection.work_record_paths(config)
    console.print(f"  Work record: {', '.join(record_paths)}")

    if config.key_files.paths:
        console.print(
            f"  Key files: {', '.join(config.key_files.paths)}"
        )
    console.print(
        f"  Injection: {config.injection.strategy}"
        f" ({config.injection.order})"
    )


@ctx_app.command("files")
def files_command(
    profile: str | None = typer.Argument(None, help="Profile name."),
) -> None:
    """List key files and their sizes."""
    project, pm = _load_project()
    resolved = _resolve_profile(profile, pm)

    try:
        config = pm.load(resolved)
    except CForgeError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    def _file_row(fp: Path) -> tuple[str, str, str]:
        if fp.exists() and fp.is_file():
            content = fp.read_text(encoding="utf-8", errors="replace")
            lines = content.count("\n")
            chars = len(content)
            status = "[green]yes[/green]" if chars > 0 else "[yellow]empty[/yellow]"
            return status, str(lines), f"{chars:,}"
        return "[red]no[/red]", "-", "-"

    # Work record table
    record_table = Table(title=f"Work record — {resolved}")
    record_table.add_column("File", style="cyan")
    record_table.add_column("Status", justify="center")
    record_table.add_column("Lines", justify="right")
    record_table.add_column("Chars", justify="right")

    for p in SimpleInjection.work_record_paths(config):
        status, lines, chars = _file_row(project.root / p)
        record_table.add_row(p, status, lines, chars)
    console.print(record_table)

    # Key files table
    paths = config.key_files.paths
    if not paths:
        console.print(
            f"\n[yellow]No key files configured for "
            f"profile '{resolved}'.[/yellow]"
        )
        return

    key_table = Table(title=f"Key files — {resolved}")
    key_table.add_column("File", style="cyan")
    key_table.add_column("Status", justify="center")
    key_table.add_column("Lines", justify="right")
    key_table.add_column("Chars", justify="right")

    for p in paths:
        status, lines, chars = _file_row(project.root / p)
        key_table.add_row(p, status, lines, chars)

    console.print(key_table)


@ctx_app.command("update")
def update_command(
    profile: str | None = typer.Argument(None, help="Profile name."),
    all_: bool = typer.Option(
        False, "--all", help="Process all profiles.",
    ),
) -> None:
    """AI-update outdated key files."""
    project, pm = _load_project()
    targets = _resolve_profiles(profile, all_, pm)

    for name in targets:
        try:
            config = pm.load(name)
        except CForgeError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)
        profile_dir = f".ctxforge/profiles/{name}"
        record_paths = {f: f"{profile_dir}/{f}" for f in config.work_record.files}
        prompt = _build_ctx_update(
            f"{profile_dir}/profile.toml", record_paths, config.work_record.files,
        ).replace("- $ARGUMENTS\n", "")
        console.print(
            f"[bold]Updating[/bold] profile=[cyan]{name}[/cyan]"
        )
        exit_code = _run_ai_prompt(project, pm, name, prompt)
        if exit_code != 0:
            raise typer.Exit(exit_code)


@ctx_app.command("compress")
def compress_command(
    profile: str | None = typer.Argument(None, help="Profile name."),
    all_: bool = typer.Option(
        False, "--all", help="Process all profiles.",
    ),
) -> None:
    """AI-compress redundant key files."""
    project, pm = _load_project()
    targets = _resolve_profiles(profile, all_, pm)

    for name in targets:
        try:
            config = pm.load(name)
        except CForgeError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)
        profile_dir = f".ctxforge/profiles/{name}"
        record_paths = {f: f"{profile_dir}/{f}" for f in config.work_record.files}
        prompt = _build_ctx_compress(
            f"{profile_dir}/profile.toml", record_paths, config.work_record.files,
        ).replace("- $ARGUMENTS\n", "")
        console.print(
            f"[bold]Compressing[/bold] profile=[cyan]{name}[/cyan]"
        )
        exit_code = _run_ai_prompt(project, pm, name, prompt)
        if exit_code != 0:
            raise typer.Exit(exit_code)
