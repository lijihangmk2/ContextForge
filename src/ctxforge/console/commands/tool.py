"""ctxforge tool — manage MCP tools for AI sessions."""

from __future__ import annotations

import sys

import typer
from rich.console import Console
from rich.table import Table

from ctxforge.core.profile import ProfileManager
from ctxforge.core.project import Project
from ctxforge.core.registry import RegistryError, RegistryPackage, fetch_from_github, is_github_url
from ctxforge.core.registry import search as registry_search
from ctxforge.core.toolchain import ToolStatus, check_tool
from ctxforge.exceptions import CForgeError, ProfileNotFoundError, RunnerError
from ctxforge.runner.registry import get_runner
from ctxforge.spec.schema import ToolDefinition
from ctxforge.storage.profile_writer import write_profile
from ctxforge.storage.project_writer import write_project

console = Console()

tool_app = typer.Typer(help="Manage MCP tools.", no_args_is_help=True)


def _load_project() -> Project:
    try:
        return Project.load()
    except CForgeError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


def _resolve_tool_name(project: Project, name: str) -> str:
    """Resolve a tool name with fuzzy matching.

    Returns the exact registered name, or raises typer.Exit if not found.
    """
    if name in project.config.tools:
        return name
    # Fuzzy: find registered tools containing the keyword
    matches = [t for t in project.config.tools if name in t]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        if not sys.stdin.isatty():
            return matches[0]
        import questionary

        result: str | None = questionary.select(
            f"Multiple tools match '{name}':", choices=matches,
        ).ask()
        if result is None:
            raise typer.Exit(0)
        return result
    console.print(f"[red]Error:[/red] Tool '{name}' not registered.")
    raise typer.Exit(1)


def _resolve_profile_name(
    pm: ProfileManager, profile: str | None,
) -> str:
    """Resolve profile name, interactively if needed."""
    try:
        return pm.resolve(profile)
    except ProfileNotFoundError:
        names = pm.list_names()
        if not names:
            console.print("[red]Error:[/red] No profiles found.")
            raise typer.Exit(1)
        if len(names) == 1:
            return names[0]
        if sys.stdin.isatty():
            import questionary

            result: str | None = questionary.select("Select profile:", choices=names).ask()
            if result is None:
                raise typer.Exit(0)
            return result
        console.print("[red]Error:[/red] Multiple profiles — specify one.")
        raise typer.Exit(1)


@tool_app.command("search")
def search_command(
    keyword: str = typer.Argument(..., help="Search keyword."),
    limit: int = typer.Option(10, "--limit", "-l", help="Max results."),
) -> None:
    """Search the MCP registry for available tools."""
    try:
        results = registry_search(keyword, limit=limit)
    except RegistryError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)

    if not results:
        console.print(f"No tools found for [cyan]{keyword}[/cyan].")
        return

    table = Table(title=f"MCP Registry — '{keyword}'")
    table.add_column("Name", style="cyan")
    table.add_column("Package")
    table.add_column("Type")
    table.add_column("Description")

    for pkg in results:
        table.add_row(pkg.short_name, pkg.identifier, pkg.registry_type, pkg.description)

    console.print(table)
    console.print(
        f"\n  Use [bold]ctxforge tool add {keyword}[/bold] to register one."
    )


@tool_app.command("list")
def list_command() -> None:
    """List all registered tools and their availability status."""
    project = _load_project()

    if not project.config.tools:
        console.print("No tools registered. Use [bold]ctxforge tool add[/bold] to add one.")
        return

    table = Table(title="Registered Tools")
    table.add_column("Name", style="cyan")
    table.add_column("Description")
    table.add_column("Command")
    table.add_column("Status")

    for name, tool in project.config.tools.items():
        result = check_tool(name, tool)
        if result.ok:
            status = "[green]available[/green]"
        elif result.status == ToolStatus.MISSING_COMMAND:
            status = f"[red]missing command: {tool.command}[/red]"
        else:
            status = f"[yellow]missing env: {', '.join(result.missing_env)}[/yellow]"
        table.add_row(name, tool.description, tool.command, status)

    console.print(table)


def _search_registry(keyword: str) -> RegistryPackage | None:
    """Search the MCP registry and let the user pick a result."""
    console.print(f"  Searching MCP registry for [cyan]{keyword}[/cyan]...")
    try:
        results = registry_search(keyword)
    except RegistryError as exc:
        console.print(f"  [yellow]Registry lookup failed:[/yellow] {exc}")
        return None

    if not results:
        console.print("  [dim]No results found in the MCP registry.[/dim]")
        return None

    if not sys.stdin.isatty():
        return results[0]

    import questionary

    # Always let user confirm — even for single result
    choices = [
        questionary.Choice(
            title=f"{pkg.identifier} — {pkg.description}",
            value=pkg,
        )
        for pkg in results
    ]
    choices.append(questionary.Choice(title="(none — enter manually)", value=None))
    selected: RegistryPackage | None = questionary.select(
        "Select a tool (or skip to enter manually):",
        choices=choices,
    ).ask()
    return selected


def _register_from_package(project: Project, pkg: RegistryPackage) -> None:
    """Register a tool from a resolved RegistryPackage."""
    tool_name = pkg.short_name
    if tool_name in project.config.tools:
        console.print(f"[yellow]Tool '{tool_name}' already registered.[/yellow]")
        raise typer.Exit(1)

    console.print(f"  [bold]Name:[/bold]    {tool_name}")
    console.print(f"  [bold]Command:[/bold] {pkg.command} {' '.join(pkg.args)}")
    if pkg.env_vars:
        for var in pkg.env_vars:
            desc = pkg.env_descriptions.get(var, "")
            suffix = f" — {desc}" if desc else ""
            console.print(f"  [bold]Env:[/bold]     {var}{suffix}")

    tool_def = ToolDefinition(
        description=pkg.description,
        command=pkg.command,
        args=pkg.args,
        env=pkg.env_vars,
    )
    _register_tool(project, tool_name, tool_def)


def _run_setup(project: Project, tool_name: str, tool_def: ToolDefinition) -> None:
    """Launch AI CLI to set up a tool interactively, then verify."""
    cli_name = _get_active_cli(project)
    console.print(
        f"  Launching [cyan]{cli_name}[/cyan] to set up [bold]{tool_name}[/bold]..."
    )
    console.print()

    prompt = _build_setup_prompt(tool_name, tool_def)
    try:
        runner = get_runner(cli_name)
        runner.run(
            system_prompt="You are a system setup assistant. "
            "Help the user install and configure the requested tool. "
            "Be concise and action-oriented.",
            initial_prompt=prompt,
        )
    except (CForgeError, RunnerError) as e:
        console.print(f"\n[red]Error:[/red] {e}")
        raise typer.Exit(1)

    # Post-check
    console.print()
    post_check = check_tool(tool_name, tool_def)
    if post_check.ok:
        console.print(f"  [green]✓ Tool '{tool_name}' is now available.[/green]")
    elif post_check.status == ToolStatus.MISSING_COMMAND:
        console.print(
            f"  [red]✗ Tool '{tool_name}' setup incomplete:[/red] "
            f"command '{tool_def.command}' still not found."
        )
    else:
        missing = ", ".join(post_check.missing_env)
        console.print(
            f"  [yellow]✗ Tool '{tool_name}' partially set up:[/yellow] "
            f"missing env vars: {missing}"
        )


def _register_tool(
    project: Project,
    tool_name: str,
    tool_def: ToolDefinition,
) -> None:
    """Write to project.toml, check availability, launch setup if needed."""
    project.config.tools[tool_name] = tool_def
    project_path = project.ctxforge_dir / "project.toml"
    write_project(project_path, project.config)
    console.print(f"  [green]Registered tool '{tool_name}' in project.toml[/green]")

    result = check_tool(tool_name, tool_def)
    if result.ok:
        console.print(f"  [green]Tool '{tool_name}' is available[/green]")
        return

    # Not available — launch CLI setup
    if result.status == ToolStatus.MISSING_COMMAND:
        console.print(
            f"  [yellow]Command '{tool_def.command}' not found on PATH[/yellow]"
        )
    else:
        missing = ", ".join(result.missing_env)
        console.print(f"  [yellow]Missing env vars: {missing}[/yellow]")

    _run_setup(project, tool_name, tool_def)


@tool_app.command("add")
def add_command(
    name: str = typer.Argument(..., help="Tool name or search keyword."),
    description: str = typer.Option("", "--desc", "-d", help="Tool description."),
    command: str = typer.Option("", "--command", "-c", help="MCP server command."),
    args: str = typer.Option("", "--args", "-a", help="Comma-separated arguments."),
    env: str = typer.Option("", "--env", "-e", help="Comma-separated env var names."),
    setup: str = typer.Option("", "--setup", "-s", help="Setup instructions."),
    manual: bool = typer.Option(False, "--manual", "-m", help="Skip registry lookup."),
) -> None:
    """Register a new MCP tool in the project.

    Accepts a tool name (searches MCP registry), a GitHub URL (fetches
    server.json), or --command for manual configuration.
    """
    project = _load_project()

    # --- GitHub URL mode ---
    if not manual and not command and is_github_url(name):
        console.print(f"  Fetching server.json from [cyan]{name}[/cyan]...")
        try:
            pkg = fetch_from_github(name)
        except RegistryError as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(1)
        return _register_from_package(project, pkg)

    # --- Registry search mode (default) ---
    if not manual and not command:
        found = _search_registry(name)
        if found is not None:
            return _register_from_package(project, found)

        # Registry returned nothing — fall through to manual
        console.print("  Falling back to manual mode.")

    # --- Manual / custom command mode ---
    if name in project.config.tools:
        console.print(f"[yellow]Tool '{name}' already registered.[/yellow]")
        raise typer.Exit(1)

    if not command:
        if not sys.stdin.isatty():
            console.print("[red]Error:[/red] --command is required in non-interactive mode.")
            raise typer.Exit(1)

        if not description:
            console.print("Description: ", end="")
            description = sys.stdin.readline().strip()
        console.print("MCP server command (e.g. npx, tavily-mcp): ", end="")
        command = sys.stdin.readline().strip()
        if not command:
            console.print("[red]Error:[/red] Command is required.")
            raise typer.Exit(1)
        if not args:
            console.print("Arguments (comma-separated, or empty): ", end="")
            args = sys.stdin.readline().strip()
        if not env:
            console.print("Required env vars (comma-separated, or empty): ", end="")
            env = sys.stdin.readline().strip()
        if not setup:
            console.print("Setup instructions (or empty): ", end="")
            setup = sys.stdin.readline().strip()

    args_list = [a.strip() for a in args.split(",") if a.strip()] if args else []
    env_list = [e.strip() for e in env.split(",") if e.strip()] if env else []

    tool_def = ToolDefinition(
        description=description,
        command=command,
        args=args_list,
        env=env_list,
        setup=setup,
    )
    _register_tool(project, name, tool_def)


@tool_app.command("remove")
def remove_command(
    name: str = typer.Argument(..., help="Tool name to remove."),
) -> None:
    """Remove a tool from the project registry."""
    project = _load_project()
    name = _resolve_tool_name(project, name)
    del project.config.tools[name]
    project_path = project.ctxforge_dir / "project.toml"
    write_project(project_path, project.config)
    console.print(f"  [green]Removed tool '{name}' from project.toml[/green]")

    # Also clean up from any profiles' disabled lists
    pm = ProfileManager(project.profiles_dir)
    for profile_name in pm.list_names():
        config = pm.load(profile_name)
        if name in config.tools.disabled:
            config.tools.disabled.remove(name)
            write_profile(pm.profile_path(profile_name), config)
            console.print(f"  [dim]Cleaned '{name}' from profile '{profile_name}'[/dim]")


@tool_app.command("check")
def check_command(
    name: str = typer.Argument(None, help="Tool name (all if omitted)."),
) -> None:
    """Check tool availability (command + env vars)."""
    project = _load_project()

    tools_to_check = {}
    if name:
        name = _resolve_tool_name(project, name)
        tools_to_check[name] = project.config.tools[name]
    else:
        tools_to_check = project.config.tools

    if not tools_to_check:
        console.print("No tools registered.")
        return

    for tool_name, tool_def in tools_to_check.items():
        result = check_tool(tool_name, tool_def)
        if result.ok:
            console.print(f"  [green]✓[/green] {tool_name}: available")
        elif result.status == ToolStatus.MISSING_COMMAND:
            console.print(f"  [red]✗[/red] {tool_name}: command '{tool_def.command}' not found")
            if tool_def.setup:
                console.print(f"    Setup: {tool_def.setup}")
        else:
            console.print(
                f"  [yellow]✗[/yellow] {tool_name}: "
                f"missing env: {', '.join(result.missing_env)}"
            )


def _build_setup_prompt(name: str, tool: ToolDefinition) -> str:
    """Build a prompt for the AI CLI to set up a tool."""
    lines = [
        f"I need you to set up the MCP tool '{name}' on this system.",
        f"Tool: {tool.description}" if tool.description else "",
        f"Command: {tool.command} {' '.join(tool.args)}",
    ]
    if tool.env:
        lines.append(f"Required environment variables: {', '.join(tool.env)}")
    if tool.setup:
        lines.append(f"Setup instructions: {tool.setup}")

    lines.extend([
        "",
        "Please:",
        "1. Check if the command is available, install it if not.",
        "2. For each required env var, check if it is set. "
        "If not, guide me through obtaining and configuring it.",
        "3. Verify everything works by running a quick test.",
        "4. Report the final status clearly.",
    ])
    return "\n".join(line for line in lines if line is not None)


def _get_active_cli(project: Project) -> str:
    """Get the active CLI from project config."""
    cli_name = project.config.cli.active
    if not cli_name:
        detected = project.config.cli.detected
        if detected:
            cli_name = detected[0]
    if not cli_name:
        console.print("[red]Error:[/red] No CLI configured. Run [bold]ctxforge init[/bold].")
        raise typer.Exit(1)
    return cli_name


@tool_app.command("setup")
def setup_command(
    name: str = typer.Argument(..., help="Tool name to set up."),
) -> None:
    """Launch AI CLI to install and configure a registered tool."""
    project = _load_project()
    name = _resolve_tool_name(project, name)
    tool_def = project.config.tools[name]

    pre_check = check_tool(name, tool_def)
    if pre_check.ok:
        console.print(f"  [green]Tool '{name}' is already available. No setup needed.[/green]")
        return

    _run_setup(project, name, tool_def)


@tool_app.command("enable")
def enable_command(
    name: str = typer.Argument(..., help="Tool name to re-enable."),
    profile: str | None = typer.Option(None, "--profile", "-p", help="Target profile."),
) -> None:
    """Re-enable a previously disabled tool for a profile."""
    project = _load_project()
    name = _resolve_tool_name(project, name)
    pm = ProfileManager(project.profiles_dir)
    profile_name = _resolve_profile_name(pm, profile)
    config = pm.load(profile_name)

    if name not in config.tools.disabled:
        console.print(f"  Tool '{name}' is already active for profile '{profile_name}'.")
        return

    config.tools.disabled.remove(name)
    write_profile(pm.profile_path(profile_name), config)
    console.print(f"  [green]Enabled tool '{name}' for profile '{profile_name}'[/green]")


@tool_app.command("disable")
def disable_command(
    name: str = typer.Argument(..., help="Tool name to disable."),
    profile: str | None = typer.Option(None, "--profile", "-p", help="Target profile."),
) -> None:
    """Disable a tool for a specific profile."""
    project = _load_project()
    name = _resolve_tool_name(project, name)
    pm = ProfileManager(project.profiles_dir)
    profile_name = _resolve_profile_name(pm, profile)
    config = pm.load(profile_name)

    if name in config.tools.disabled:
        console.print(f"  Tool '{name}' is already disabled for profile '{profile_name}'.")
        return

    config.tools.disabled.append(name)
    write_profile(pm.profile_path(profile_name), config)
    console.print(f"  [green]Disabled tool '{name}' for profile '{profile_name}'[/green]")
