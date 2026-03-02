"""ctxforge run command."""

from __future__ import annotations

import sys

import typer
from rich.console import Console

from ctxforge.core.profile import ProfileManager
from ctxforge.core.project import Project
from ctxforge.core.prompt_builder import PromptBuilder
from ctxforge.exceptions import CForgeError, ProfileNotFoundError, ProjectNotFoundError
from ctxforge.runner.registry import get_runner
from ctxforge.spec.schema import ProfileConfig
from ctxforge.storage.commands_writer import write_commands

console = Console()


def _choose_profile(names: list[str]) -> str:
    """Let the user pick a profile interactively."""
    if sys.stdin.isatty():
        import questionary  # lazy import

        result = questionary.select("Select profile:", choices=names).ask()
        if result is None:
            raise typer.Exit(0)
        return result
    # Fallback for piped input (tests, CI)
    console.print("Select profile:")
    for i, name in enumerate(names, 1):
        console.print(f"  [{i}] {name}")
    value = sys.stdin.readline().strip()
    try:
        return names[int(value) - 1]
    except (ValueError, IndexError):
        return names[0]


def _print_injection_summary(
    profile_name: str,
    cli_name: str,
    profile_config: ProfileConfig,
    system_prompt: str,
    language: str | None,
) -> None:
    """Print a summary of what is being injected."""
    console.print(f"[bold]ctxforge[/bold] profile=[cyan]{profile_name}[/cyan]"
                  f" cli=[cyan]{cli_name}[/cyan]")

    if profile_config.role.prompt:
        prompt_preview = profile_config.role.prompt.strip()
        if len(prompt_preview) > 60:
            prompt_preview = prompt_preview[:60] + "..."
        console.print(f"  [dim]Role:[/dim] {prompt_preview}")

    paths = profile_config.key_files.paths
    if paths:
        console.print(f"  [dim]Key files ({len(paths)}):[/dim]")
        for p in paths:
            console.print(f"    [dim]{p}[/dim]")

    if language:
        console.print(f"  [dim]Language:[/dim] {language}")

    prompt_chars = len(system_prompt)
    console.print(f"  [dim]System prompt:[/dim] ~{prompt_chars:,} chars")
    console.print()


def run_command(
    profile: str | None = typer.Argument(
        None, help="Profile name (uses default if omitted)."
    ),
) -> None:
    """Start an interactive AI CLI session with profile context injection.

    Usage:
        ctxforge run                # default profile
        ctxforge run architect      # named profile
    """
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

    pm = ProfileManager(project.profiles_dir)
    try:
        resolved = pm.resolve(profile)
    except ProfileNotFoundError:
        # Multiple profiles, none specified — let user choose
        names = pm.list_names()
        if len(names) > 1:
            resolved = _choose_profile(names)
        else:
            console.print(
                "[red]Error:[/red] No profile specified and no default configured."
            )
            raise typer.Exit(1)
    except CForgeError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    try:
        profile_config = pm.load(resolved)
    except CForgeError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    cli_name = project.config.cli.active
    if not cli_name:
        console.print("[red]Error:[/red] No active CLI configured.")
        raise typer.Exit(1)

    builder = PromptBuilder(project.root)
    language = project.config.defaults.language
    system_prompt = builder.build_system(profile_config, language)
    greeting = builder.build_greeting(profile_config, language)

    # ── Sync slash commands for this profile (claude only) ──────────────
    write_commands(project.root, resolved, cli_name)

    _print_injection_summary(resolved, cli_name, profile_config, system_prompt, language)

    try:
        runner = get_runner(cli_name)
    except CForgeError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    try:
        result = runner.run(system_prompt, greeting)
    except CForgeError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    if not result.ok:
        raise typer.Exit(result.exit_code)
