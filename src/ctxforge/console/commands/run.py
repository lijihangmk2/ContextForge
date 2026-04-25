"""ctxforge run command."""

from __future__ import annotations

import json
import sys
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import typer
from rich.console import Console
from setproctitle import setproctitle

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - Python 3.10 fallback
    import tomli as tomllib  # type: ignore[import-not-found]

from ctxforge.core.injection import SimpleInjection
from ctxforge.core.memory import (
    build_memory_system_prompt,
    build_mempalace_mcp_server,
    load_memory_preload,
    resolve_memory_binding,
    validate_memory_runtime,
)
from ctxforge.core.migration import migrate_profile, needs_migration
from ctxforge.core.profile import ProfileManager
from ctxforge.core.project import Project
from ctxforge.core.prompt_builder import PromptBuilder
from ctxforge.core.toolchain import ToolStatus, build_mcp_config, resolve_tools
from ctxforge.exceptions import CForgeError, ProfileNotFoundError, ProjectNotFoundError
from ctxforge.runner.claude import ClaudeRunner
from ctxforge.runner.codex import CodexRunner
from ctxforge.runner.registry import get_runner
from ctxforge.spec.schema import ProfileConfig
from ctxforge.storage.claude_settings import sync_claude_memory_hooks
from ctxforge.storage.commands_writer import write_commands
from ctxforge.storage.profile_writer import write_profile

console = Console()


def _choose_profile(names: list[str]) -> str:
    """Let the user pick a profile interactively."""
    if sys.stdin.isatty():
        import questionary  # lazy import

        result = questionary.select("Select profile:", choices=names).ask()
        if result is None:
            raise typer.Exit(0)
        return str(result)
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
    tool_summary: list[tuple[str, str]] | None = None,
    memory_summary: str | None = None,
) -> None:
    """Print a summary of what is being injected."""
    console.print(f"[bold]ctxforge[/bold] profile=[cyan]{profile_name}[/cyan]"
                  f" cli=[cyan]{cli_name}[/cyan]")

    if profile_config.role.prompt:
        prompt_preview = profile_config.role.prompt.strip()
        if len(prompt_preview) > 60:
            prompt_preview = prompt_preview[:60] + "..."
        console.print(f"  [dim]Role:[/dim] {prompt_preview}")

    record_paths = SimpleInjection.work_record_paths(profile_config)
    console.print("  [dim]Work record:[/dim]")
    for p in record_paths:
        console.print(f"    [dim]{p}[/dim]")

    paths = profile_config.key_files.paths
    if paths:
        console.print(f"  [dim]Key files ({len(paths)}):[/dim]")
        for p in paths:
            console.print(f"    [dim]{p}[/dim]")

    if tool_summary:
        parts = []
        for tname, tstatus in tool_summary:
            if tstatus == "ok":
                parts.append(f"[green]{tname} ✓[/green]")
            else:
                parts.append(f"[yellow]{tname} ✗[/yellow] ({tstatus})")
        console.print(f"  [dim]Tools:[/dim] {', '.join(parts)}")

    if memory_summary:
        console.print(f"  [dim]Memory:[/dim] {memory_summary}")

    if language:
        console.print(f"  [dim]Language:[/dim] {language}")

    prompt_chars = len(system_prompt)
    console.print(f"  [dim]System prompt:[/dim] ~{prompt_chars:,} chars")
    console.print()


def _print_memory_debug(
    *,
    cli_name: str,
    resume_id: str | None,
    memory_binding: object | None,
    runtime_ok: bool,
    runtime_message: str,
    memory_prompt: str,
    preload_status: str | None,
    preload_ok: bool,
    mcp_config_path: Path | None,
    profile_root: Path,
) -> None:
    """Print detailed MemPalace diagnostics for troubleshooting."""
    console.print("[bold]Memory Debug[/bold]")
    console.print(f"  [dim]CLI:[/dim] {cli_name}")
    console.print(f"  [dim]Resume:[/dim] {'yes' if resume_id else 'no'}")
    console.print(f"  [dim]Runtime:[/dim] {'ok' if runtime_ok else 'error'}")
    if runtime_message:
        console.print(f"  [dim]Runtime message:[/dim] {runtime_message}")

    if memory_binding is None:
        console.print("  [dim]Binding:[/dim] disabled")
    else:
        console.print(f"  [dim]Namespace:[/dim] {memory_binding.namespace}")
        console.print(f"  [dim]Wing:[/dim] {memory_binding.wing}")
        console.print(f"  [dim]Palace path:[/dim] {memory_binding.palace_path}")
        console.print(
            f"  [dim]Palace exists:[/dim] "
            f"{'yes' if memory_binding.palace_path.exists() else 'no'}"
        )
        console.print(
            f"  [dim]Memory prompt injected:[/dim] "
            f"{'yes' if bool(memory_prompt) else 'no'}"
        )
        console.print(f"  [dim]Preload status:[/dim] {preload_status or 'skipped'}")
        console.print(f"  [dim]Preload content injected:[/dim] {'yes' if preload_ok else 'no'}")

    console.print(
        f"  [dim]MCP config:[/dim] {mcp_config_path if mcp_config_path else 'none'}"
    )
    if cli_name == "claude":
        settings_path = profile_root / ".claude" / "settings.local.json"
        hook_text = ""
        if settings_path.exists():
            try:
                hook_text = settings_path.read_text(encoding="utf-8")
            except OSError:
                hook_text = ""
        console.print(
            f"  [dim]Claude memory hooks:[/dim] "
            f"{'present' if 'ctxforge hook memory' in hook_text else 'missing'}"
        )
    elif cli_name == "codex":
        console.print("  [dim]Codex MCP handoff:[/dim] unsupported by current runner")
        console.print("  [dim]Autosave hooks:[/dim] unsupported outside Claude")

    console.print()


def _ensure_migrated(
    pm: ProfileManager,
    profile_name: str,
    project: Project,
) -> ProfileConfig:
    """Load a profile and run migration if needed."""
    profile_config = pm.load(profile_name)
    if needs_migration(profile_config):
        profile_config = migrate_profile(
            profile_config,
            project.config,
            pm.profile_path(profile_name),
        )
    elif _needs_profile_normalization(pm.profile_path(profile_name)):
        write_profile(pm.profile_path(profile_name), profile_config)
    return profile_config


def _needs_profile_normalization(profile_path: Path) -> bool:
    """Check whether a profile.toml is missing required normalized sections."""
    try:
        with open(profile_path, "rb") as f:
            data = tomllib.load(f)
    except Exception:
        return False

    key_files = data.get("key_files")
    if not isinstance(key_files, dict):
        return True
    paths = key_files.get("paths")
    return not isinstance(paths, list)


def _ensure_context_files(profile_dir: Path, profile_config: ProfileConfig) -> None:
    """Ensure work record files exist in the profile directory."""
    for name in profile_config.work_record.files:
        path = profile_dir / name
        if not path.exists():
            path.write_text("", encoding="utf-8")


SESSION_FILE = ".session"
SESSION_INDEX_FILE = "sessions.json"
CODEX_LIST_LIMIT = 20


@dataclass(frozen=True)
class ProfileSessionEntry:
    """A session entry owned by one profile."""

    session_id: str
    cwd: str
    modified_at: datetime
    preview: str = ""


def _load_session_id(profile_dir: Path) -> str | None:
    """Read the saved session ID for a profile, or None."""
    profile_sessions = _load_profile_sessions(profile_dir)
    session_file = profile_dir / SESSION_FILE
    if not session_file.exists():
        return None

    sid = session_file.read_text(encoding="utf-8").strip()
    if not sid:
        return None

    if not profile_sessions:
        return sid

    if sid in {session.session_id for session in profile_sessions}:
        return sid
    return profile_sessions[0].session_id


def _save_session_id(profile_dir: Path, session_id: str) -> None:
    """Persist a session ID to the profile directory."""
    session_file = profile_dir / SESSION_FILE
    session_file.write_text(session_id, encoding="utf-8")


def _clear_session_id(profile_dir: Path) -> None:
    """Remove any persisted session ID for a profile."""
    session_file = profile_dir / SESSION_FILE
    if session_file.exists():
        session_file.unlink()


def _load_profile_sessions(profile_dir: Path) -> list[ProfileSessionEntry]:
    """Load the per-profile session index."""
    index_file = profile_dir / SESSION_INDEX_FILE
    if not index_file.exists():
        return []

    try:
        raw = json.loads(index_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(raw, list):
        return []

    sessions: list[ProfileSessionEntry] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        session_id = item.get("session_id")
        cwd = item.get("cwd")
        modified_at = item.get("modified_at")
        preview = item.get("preview", "")
        if not (
            isinstance(session_id, str)
            and isinstance(cwd, str)
            and isinstance(modified_at, str)
            and isinstance(preview, str)
        ):
            continue
        try:
            parsed_time = datetime.fromisoformat(modified_at)
        except ValueError:
            continue
        sessions.append(
            ProfileSessionEntry(
                session_id=session_id,
                cwd=cwd,
                modified_at=parsed_time,
                preview=preview,
            )
        )

    sessions.sort(key=lambda session: session.modified_at, reverse=True)
    return sessions


def _save_profile_sessions(
    profile_dir: Path,
    sessions: Sequence[ProfileSessionEntry],
) -> None:
    """Persist the per-profile session index."""
    payload = [
        {
            "session_id": session.session_id,
            "cwd": session.cwd,
            "modified_at": session.modified_at.isoformat(),
            "preview": session.preview,
        }
        for session in sessions
    ]
    (profile_dir / SESSION_INDEX_FILE).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _to_profile_session_entry(session: object) -> ProfileSessionEntry | None:
    """Convert a runner-specific session object into a profile session entry."""
    session_id = getattr(session, "session_id", None)
    cwd = getattr(session, "cwd", None)
    modified_at = getattr(session, "modified_at", None)
    preview = getattr(session, "preview", "")
    if not (
        isinstance(session_id, str)
        and isinstance(cwd, str)
        and isinstance(modified_at, datetime)
    ):
        return None
    if not isinstance(preview, str):
        preview = ""
    return ProfileSessionEntry(
        session_id=session_id,
        cwd=cwd,
        modified_at=modified_at,
        preview=preview,
    )


def _upsert_profile_session(
    profile_dir: Path,
    session_id: str,
    *,
    cwd: Path,
    fetch_sessions: Callable[[Path], Sequence[object]] | None = None,
) -> None:
    """Record a session under this profile only."""
    sessions = [s for s in _load_profile_sessions(profile_dir) if s.session_id != session_id]
    entry: ProfileSessionEntry | None = None
    if fetch_sessions is not None:
        entry = next(
            (
                converted
                for session in fetch_sessions(cwd)
                if (converted := _to_profile_session_entry(session)) is not None
                and converted.session_id == session_id
            ),
            None,
        )
    if entry is None:
        entry = ProfileSessionEntry(
            session_id=session_id,
            cwd=str(cwd.resolve()),
            modified_at=datetime.now(timezone.utc),
        )
    _save_profile_sessions(profile_dir, [entry, *sessions])


def _discover_recent_codex_session_id(profile_dir: Path, cwd: Path) -> str | None:
    """Find a recent Codex session owned by the current profile."""
    profile_sessions = _load_profile_sessions(profile_dir)
    if profile_sessions:
        return profile_sessions[0].session_id
    # `C` must never auto-pick sessions from another profile. Global runner scans
    # are only allowed from `L`, where the user explicitly inspects candidates.
    return None


def _discover_claude_session_id(profile_dir: Path, cwd: Path) -> str | None:
    """Find the latest Claude session owned by the current profile."""
    profile_sessions = _load_profile_sessions(profile_dir)
    if profile_sessions:
        return profile_sessions[0].session_id
    return None


def _ask_session_action(
    *,
    allow_resume: bool = True,
    allow_list: bool,
    allow_list_all: bool = False,
) -> str:
    """Ask how to start the session based on available choices."""
    if not sys.stdin.isatty():
        return "resume" if allow_resume else "new"
    if allow_resume and allow_list_all:
        options = "Continue, start new, list project sessions, or list all? \\[C/n/l/la]: "
    elif allow_resume and allow_list:
        options = "Continue, start new, or list sessions? \\[C/n/l]: "
    elif allow_resume:
        options = "Continue or start new? \\[C/n]: "
    elif allow_list_all:
        options = "Start new, or list all? \\[N/la]: "
    elif allow_list:
        options = "Start new, or list sessions? \\[N/l]: "
    else:
        return "new"

    prefix = "[bold]Previous session found.[/bold] " if allow_resume else ""
    console.print(prefix + options, end="")
    value = sys.stdin.readline().strip().lower()
    if allow_resume and (not value or value in ("c", "continue", "y", "yes")):
        return "resume"
    if allow_list_all and value in ("la", "list-all", "list all"):
        return "list_all"
    if allow_list and value in ("l", "list"):
        return "list"
    return "new"


def _select_saved_session(
    *,
    profile_dir: Path,
    cwd: Path,
    fetch_sessions: Callable[[Path], Sequence[object]],
    title: str,
    empty_message: str,
    prefer_profile_index: bool = True,
) -> str | None:
    """List profile-owned sessions for the current cwd and let the user choose one."""
    sessions: list[ProfileSessionEntry] = []
    if prefer_profile_index:
        sessions = _load_profile_sessions(profile_dir)
    if not sessions:
        sessions = [
            entry
            for session in fetch_sessions(cwd)
            if (entry := _to_profile_session_entry(session)) is not None
        ]
    sessions = sessions[:CODEX_LIST_LIMIT]
    if not sessions:
        console.print(f"[yellow]{empty_message}[/yellow]")
        return None

    console.print(f"[bold]{title}[/bold] (most recent first):")
    for i, session in enumerate(sessions, 1):
        modified = session.modified_at.astimezone().strftime("%Y-%m-%d %H:%M")
        preview = f"  {session.preview}" if getattr(session, "preview", "") else ""
        console.print(
            f"  [{i}] {modified}  {session.session_id[:8]}  "
            f"{Path(session.cwd).name or session.cwd}{preview}"
        )

    console.print("Select a session number, or press Enter to cancel: ", end="")
    value = sys.stdin.readline().strip()
    if not value:
        return None
    try:
        index = int(value) - 1
    except ValueError:
        return None
    if index < 0 or index >= len(sessions):
        return None
    return sessions[index].session_id


def _select_codex_session(profile_dir: Path, cwd: Path) -> str | None:
    """List saved Codex sessions for the current cwd and let the user choose one."""
    return _select_saved_session(
        profile_dir=profile_dir,
        cwd=cwd,
        fetch_sessions=lambda current_cwd: CodexRunner().list_sessions(cwd=current_cwd),
        title="Saved Codex sessions",
        empty_message="No saved Codex sessions found for this project.",
        prefer_profile_index=True,
    )


def _select_codex_global_session(profile_dir: Path, cwd: Path) -> str | None:
    """List all discovered Codex sessions and let the user choose one."""
    return _select_saved_session(
        profile_dir=profile_dir,
        cwd=cwd,
        fetch_sessions=lambda current_cwd: CodexRunner().list_sessions(cwd=None),
        title="All Codex sessions",
        empty_message="No Codex sessions found.",
        prefer_profile_index=False,
    )


def _select_claude_session(profile_dir: Path, cwd: Path) -> str | None:
    """List saved Claude sessions for the current cwd and let the user choose one."""
    return _select_saved_session(
        profile_dir=profile_dir,
        cwd=cwd,
        fetch_sessions=lambda current_cwd: ClaudeRunner().list_sessions(cwd=current_cwd),
        title="Saved Claude sessions",
        empty_message="No saved Claude sessions found for this project.",
    )


def _resume_with_saved_session(
    *,
    profile_dir: Path,
    saved_sid: str,
    select_session: Callable[[Path, Path], str | None] | None,
    select_all_sessions: Callable[[Path, Path], str | None] | None = None,
    fetch_sessions: Callable[[Path], Sequence[object]] | None,
    cwd: Path,
) -> tuple[str | None, str | None]:
    """Resolve whether to resume an existing session or start a new one."""
    action = _ask_session_action(
        allow_resume=True,
        allow_list=select_session is not None,
        allow_list_all=select_all_sessions is not None,
    )
    if action == "resume":
        console.print(f"  [dim]Resuming session {saved_sid[:8]}...[/dim]")
        return saved_sid, None
    if action == "list" and select_session is not None:
        selected_sid = select_session(profile_dir, cwd)
        if selected_sid:
            _save_session_id(profile_dir, selected_sid)
            _upsert_profile_session(
                profile_dir,
                selected_sid,
                cwd=cwd,
                fetch_sessions=fetch_sessions,
            )
            console.print(f"  [dim]Resuming session {selected_sid[:8]}...[/dim]")
            return selected_sid, None
    if action == "list_all" and select_all_sessions is not None:
        selected_sid = select_all_sessions(profile_dir, cwd)
        if selected_sid:
            _save_session_id(profile_dir, selected_sid)
            _upsert_profile_session(
                profile_dir,
                selected_sid,
                cwd=cwd,
                fetch_sessions=fetch_sessions,
            )
            console.print(f"  [dim]Resuming session {selected_sid[:8]}...[/dim]")
            return selected_sid, None
    return None, str(uuid.uuid4())

def launch_session(
    project_root: Path,
    profile_name: str,
    compress: bool = False,
    debug_memory: bool = False,
) -> int:
    """Launch an AI CLI session. Returns exit code."""
    project = Project.load(project_root)
    pm = ProfileManager(project.profiles_dir)
    profile_config = _ensure_migrated(pm, profile_name, project)
    _ensure_context_files(pm.profile_path(profile_name).parent, profile_config)

    cli_name = profile_config.cli.name
    if not cli_name:
        # Fallback to project-level for un-migrated edge cases
        cli_name = project.config.cli.active
    if not cli_name:
        console.print("[red]Error:[/red] No CLI configured for this profile.")
        return 1

    profile_dir = pm.profile_path(profile_name).parent

    # ── Session management ─────────────────────────────────────────────
    resume_id: str | None = None
    session_id: str | None = None
    cwd = Path.cwd()
    saved_sid = _load_session_id(profile_dir)
    if cli_name == "codex":
        if not saved_sid and not compress:
            saved_sid = _discover_recent_codex_session_id(profile_dir, cwd)
        if saved_sid and not compress:
            resume_id, session_id = _resume_with_saved_session(
                profile_dir=profile_dir,
                saved_sid=saved_sid,
                select_session=_select_codex_session,
                select_all_sessions=_select_codex_global_session,
                fetch_sessions=lambda current_cwd: CodexRunner().list_sessions(cwd=current_cwd),
                cwd=cwd,
            )
            if session_id:
                _clear_session_id(profile_dir)
        elif not compress:
            action = _ask_session_action(
                allow_resume=False,
                allow_list=False,
                allow_list_all=True,
            )
            if action == "list_all":
                selected_sid = _select_codex_global_session(profile_dir, cwd)
                if selected_sid:
                    resume_id = selected_sid
                    _save_session_id(profile_dir, selected_sid)
                    _upsert_profile_session(
                        profile_dir,
                        selected_sid,
                        cwd=cwd,
                        fetch_sessions=lambda current_cwd: CodexRunner().list_sessions(
                            cwd=current_cwd
                        ),
                    )
                    console.print(f"  [dim]Resuming session {selected_sid[:8]}...[/dim]")
                else:
                    session_id = str(uuid.uuid4())
                    _clear_session_id(profile_dir)
            else:
                session_id = str(uuid.uuid4())
                _clear_session_id(profile_dir)
        else:
            _clear_session_id(profile_dir)
    elif cli_name == "claude":
        if not saved_sid and not compress:
            saved_sid = _discover_claude_session_id(profile_dir, cwd)
        if saved_sid and not compress:
            resume_id, session_id = _resume_with_saved_session(
                profile_dir=profile_dir,
                saved_sid=saved_sid,
                select_session=_select_claude_session,
                fetch_sessions=lambda current_cwd: ClaudeRunner().list_sessions(cwd=current_cwd),
                cwd=cwd,
            )
            if session_id:
                _save_session_id(profile_dir, session_id)
        else:
            session_id = str(uuid.uuid4())
            _save_session_id(profile_dir, session_id)
    else:
        if saved_sid and not compress:
            action = _ask_session_action(allow_list=False)
            if action == "resume":
                resume_id = saved_sid
                console.print(f"  [dim]Resuming session {saved_sid[:8]}...[/dim]")
            else:
                session_id = str(uuid.uuid4())
                _save_session_id(profile_dir, session_id)
        else:
            session_id = str(uuid.uuid4())
            _save_session_id(profile_dir, session_id)

    builder = PromptBuilder(project.root)
    language = project.config.defaults.language
    system_prompt = builder.build_system(profile_config, language)
    memory_summary: str | None = None
    memory_binding = resolve_memory_binding(project.root, profile_name, project.config)
    runtime_status = validate_memory_runtime(memory_binding)
    if not runtime_status.ok:
        console.print(f"[red]Error:[/red] {runtime_status.message}")
        return 1
    memory_prompt = build_memory_system_prompt(memory_binding)
    if memory_prompt:
        system_prompt += "\n\n" + memory_prompt
    preload_status: str | None = None
    preload_ok = False

    if compress:
        greeting = builder.build_compress_greeting(profile_config, language)
    else:
        greeting = builder.build_greeting(profile_config, language)

    # ── Resolve tools ──────────────────────────────────────────────────
    tool_summary: list[tuple[str, str]] | None = None
    mcp_config_path = None
    if project.config.tools:
        results = resolve_tools(profile_config, project.config)
        tool_summary = []
        available_tools: list[tuple[str, str]] = []  # (name, description)
        for r in results:
            tool_def = project.config.tools[r.name]
            if r.ok:
                tool_summary.append((r.name, "ok"))
                available_tools.append((r.name, tool_def.description))
            elif r.status == ToolStatus.MISSING_COMMAND:
                tool_summary.append((r.name, "missing command"))
            else:
                tool_summary.append((r.name, f"missing {', '.join(r.missing_env)}"))

        # Inject tool descriptions into system prompt
        if available_tools:
            lines = ["[Available MCP Tools]",
                     "The following MCP tools are connected and ready to use:"]
            for tname, tdesc in available_tools:
                desc_part = f" — {tdesc}" if tdesc else ""
                lines.append(f"- {tname}{desc_part}")
            system_prompt += "\n\n" + "\n".join(lines)

        mcp_config_path = build_mcp_config(
            profile_config,
            project.config,
            extra_servers=build_mempalace_mcp_server(memory_binding),
        )
    elif memory_binding is not None:
        mcp_config_path = build_mcp_config(
            profile_config,
            project.config,
            extra_servers=build_mempalace_mcp_server(memory_binding),
        )

    if not resume_id:
        preload = load_memory_preload(memory_binding)
        preload_status = preload.status
        preload_ok = preload.ok
        memory_status_map = {
            "disabled": None,
            "loaded": f"{memory_binding.namespace} loaded" if memory_binding else None,
            "unavailable": "configured, mempalace CLI not found",
            "unsupported": "configured, unsupported provider",
            "error": "configured, preload failed",
            "empty": f"{memory_binding.namespace} empty" if memory_binding else "empty",
        }
        memory_summary = memory_status_map.get(preload.status)
        if preload.ok:
            system_prompt += "\n\n" + preload.content

    # ── Sync slash commands for this profile (claude only) ──────────────
    write_commands(project.root, profile_name, cli_name, profile_config)
    if cli_name == "claude":
        sync_claude_memory_hooks(project.root, memory_binding)

    if debug_memory:
        _print_memory_debug(
            cli_name=cli_name,
            resume_id=resume_id,
            memory_binding=memory_binding,
            runtime_ok=runtime_status.ok,
            runtime_message=runtime_status.message,
            memory_prompt=memory_prompt,
            preload_status=preload_status,
            preload_ok=preload_ok,
            mcp_config_path=mcp_config_path,
            profile_root=project.root,
        )

    if not resume_id:
        _print_injection_summary(
            profile_name, cli_name, profile_config, system_prompt, language,
            tool_summary=tool_summary,
            memory_summary=memory_summary,
        )

    # Set terminal title to show the active profile
    setproctitle(profile_name)
    if sys.stdout.isatty():
        sys.stdout.write(f"\033]0;{profile_name}\007")
        sys.stdout.flush()

    try:
        runner = get_runner(cli_name)
    except CForgeError as e:
        console.print(f"[red]Error:[/red] {e}")
        return 1

    auto_approve = profile_config.cli.auto_approve
    on_session_started = None
    if cli_name == "codex" and not resume_id:
        def _record_codex_session_start(started_session_id: str) -> None:
            _save_session_id(profile_dir, started_session_id)
            _upsert_profile_session(
                profile_dir,
                started_session_id,
                cwd=cwd,
                fetch_sessions=lambda current_cwd: CodexRunner().list_sessions(cwd=current_cwd),
            )

        on_session_started = _record_codex_session_start

    try:
        result = runner.run(
            system_prompt, greeting,
            auto_approve=auto_approve,
            mcp_config=mcp_config_path,
            session_id=session_id,
            resume_id=resume_id,
            on_session_started=on_session_started,
        )
    except CForgeError as e:
        console.print(f"[red]Error:[/red] {e}")
        return 1

    if cli_name == "codex" and not resume_id and result.session_id:
        _save_session_id(profile_dir, result.session_id)
        _upsert_profile_session(
            profile_dir,
            result.session_id,
            cwd=cwd,
            fetch_sessions=lambda current_cwd: CodexRunner().list_sessions(cwd=current_cwd),
        )
    elif cli_name == "codex" and resume_id:
        _save_session_id(profile_dir, resume_id)
        _upsert_profile_session(
            profile_dir,
            resume_id,
            cwd=cwd,
            fetch_sessions=lambda current_cwd: CodexRunner().list_sessions(cwd=current_cwd),
        )
    elif cli_name == "claude" and resume_id:
        _save_session_id(profile_dir, resume_id)
        _upsert_profile_session(
            profile_dir,
            resume_id,
            cwd=cwd,
            fetch_sessions=lambda current_cwd: ClaudeRunner().list_sessions(cwd=current_cwd),
        )
    elif cli_name == "claude" and session_id:
        _upsert_profile_session(
            profile_dir,
            session_id,
            cwd=cwd,
            fetch_sessions=lambda current_cwd: ClaudeRunner().list_sessions(cwd=current_cwd),
        )

    return 0 if result.ok else result.exit_code


def run_command(
    profile: str | None = typer.Argument(
        None, help="Profile name (uses default if omitted)."
    ),
    debug_memory: bool = typer.Option(
        False,
        "--debug-memory",
        help="Print MemPalace wiring and preload diagnostics before launch.",
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

    exit_code = launch_session(project.root, resolved, debug_memory=debug_memory)
    if exit_code != 0:
        raise typer.Exit(exit_code)
