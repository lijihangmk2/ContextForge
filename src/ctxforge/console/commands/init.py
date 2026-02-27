"""ctxforge init command."""

from __future__ import annotations

import sys
from pathlib import Path

import typer
from rich.console import Console

from ctxforge.analysis.cli_detector import detect_ai_clis
from ctxforge.analysis.doc_detector import detect_doc_candidates
from ctxforge.analysis.scanner import ScanReport, scan_project
from ctxforge.core.profile import ProfileManager
from ctxforge.spec.schema import (
    CliConfig,
    DefaultsConfig,
    ProjectConfig,
    ProjectSection,
)
from ctxforge.storage.commands_writer import write_commands
from ctxforge.storage.project_writer import write_project

console = Console()

CTXFORGE_DIR = ".ctxforge"


def _prompt(text: str, default: str = "") -> str:
    """Prompt for input bypassing readline (fixes CJK backspace display)."""
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


def _estimate_tokens(char_count: int) -> int:
    """Rough token estimate: ~4 chars per token for mixed content."""
    return max(1, char_count // 4)


def _file_char_count(root: Path, rel_path: str) -> int:
    """Count characters for a single file."""
    full = root / rel_path
    if full.is_file():
        try:
            return len(full.read_text(encoding="utf-8"))
        except Exception:
            return 0
    return 0


def _format_tokens(tokens: int) -> str:
    """Format token count for display: 1.2k, 15.3k, etc."""
    if tokens < 1000:
        return f"{tokens}"
    return f"{tokens / 1000:.1f}k"


def _resolve_custom_path(raw: str, root: Path) -> str:
    """Resolve a user-provided path to a relative file path from *root*.

    Returns relative_path.  Raises ValueError if the path does not exist,
    is a directory, or is outside *root*.
    """
    p = Path(raw)
    if p.is_absolute():
        full = p.resolve()
    else:
        full = (root / p).resolve()

    if not full.exists():
        raise ValueError(f"Path does not exist: {raw}")
    if full.is_dir():
        raise ValueError(f"Directories are not allowed, specify individual files: {raw}")

    root_resolved = root.resolve()
    try:
        rel = full.relative_to(root_resolved)
    except ValueError:
        raise ValueError(f"Path is outside the project root: {raw}")

    return str(rel)


def _select_key_files(
    candidates: list[str], root: Path, budget: int = 24000
) -> list[str]:
    """Interactive checkbox with per-file token estimates and budget summary."""
    import questionary  # lazy import — avoid crash for commands that don't use init

    # Pre-compute sizes
    char_counts: dict[str, int] = {}
    for c in candidates:
        char_counts[c] = _file_char_count(root, c)

    style = questionary.Style([
        ("highlighted", "bold"),
        ("selected", "fg:ansigreen bold"),
        ("pointer", "fg:ansigreen bold"),
    ])

    while True:
        # ── Checkbox (default unchecked) ──────────────────────────────
        choices = [
            questionary.Choice(
                title=f"{c}  (~{_format_tokens(_estimate_tokens(char_counts[c]))} tok)",
                value=c,
                checked=False,
            )
            for c in candidates
        ]
        selected: list[str] | None = questionary.checkbox(
            "Select key files:",
            choices=choices,
            style=style,
        ).ask()
        if selected is None:
            return []

        # ── Custom path loop ──────────────────────────────────────────
        while True:
            raw = _prompt("Add file path (Enter to skip)")
            if not raw:
                break
            try:
                rel_str = _resolve_custom_path(raw, root)
            except ValueError as e:
                console.print(f"  [red]{e}[/red]")
                continue
            if rel_str in selected:
                console.print(f"  [yellow]Already selected: {rel_str}[/yellow]")
                continue
            char_counts[rel_str] = _file_char_count(root, rel_str)
            tok = _estimate_tokens(char_counts[rel_str])
            console.print(f"  [green]+ {rel_str}[/green] (~{_format_tokens(tok)} tok)")
            selected.append(rel_str)

        # ── Summary ───────────────────────────────────────────────────
        total_chars = sum(char_counts.get(s, 0) for s in selected)
        total_tokens = _estimate_tokens(total_chars)
        console.print(
            f"\n  Selected {len(selected)} files, "
            f"~[bold]{_format_tokens(total_tokens)}[/bold] tokens"
        )

        if total_tokens > budget:
            console.print(
                f"  [yellow]Exceeds budget ({_format_tokens(budget)} tokens). "
                f"Consider deselecting large files.[/yellow]"
            )
            if _confirm("Re-select files?", default=True):
                continue
        break

    return selected


def init_command(
    path: Path = typer.Argument(
        Path("."),
        help="Project root directory.",
        exists=True,
        file_okay=False,
        resolve_path=True,
    ),
) -> None:
    """Initialize ctxforge for a project."""
    ctxforge_dir = path / CTXFORGE_DIR
    reinit = ctxforge_dir.exists()

    console.print(f"[bold]Initializing ctxforge in[/bold] {path}\n")

    # ── Static analysis ──────────────────────────────────────────────────
    console.print("[dim]Scanning project...[/dim]")
    report = scan_project(path)
    console.print(f"  Languages: {', '.join(report.languages) or 'unknown'}")
    console.print(f"  Config files: {', '.join(report.config_files) or 'none'}")

    # ── CLI detection ────────────────────────────────────────────────────
    console.print("\n[dim]Detecting AI CLI tools...[/dim]")
    detected_clis = detect_ai_clis()

    if not detected_clis:
        console.print("[yellow]No AI CLI tools detected.[/yellow]")
        cli_config = CliConfig()
    else:
        console.print(f"  Found: {', '.join(detected_clis)}")
        if len(detected_clis) == 1:
            active = detected_clis[0]
            console.print(f"  Using: [bold]{active}[/bold]")
        else:
            console.print("\nSelect default CLI:")
            for i, cli_name in enumerate(detected_clis, 1):
                console.print(f"  [{i}] {cli_name}")
            choice = typer.prompt("Choice", default="1")
            try:
                idx = int(choice) - 1
                active = detected_clis[idx]
            except (ValueError, IndexError):
                active = detected_clis[0]
        cli_config = CliConfig(detected=detected_clis, active=active)

    # ── Output language ───────────────────────────────────────────────────
    language = _prompt("Output language", default="English")

    # ── Reinit check ─────────────────────────────────────────────────────
    pm = ProfileManager(ctxforge_dir / "profiles")

    if reinit:
        existing = pm.list_names()
        if existing:
            console.print(
                f"\n[yellow]Existing profiles:[/yellow] {', '.join(existing)}"
            )
            if not _confirm("Create a new profile?"):
                # Skip profile creation, just update project.toml
                profile_name = existing[0]
                _write_project_toml(
                    ctxforge_dir, report, cli_config, profile_name, language
                )
                console.print(
                    f"\n[bold green]Done.[/bold green] Updated {CTXFORGE_DIR}/project.toml"
                )
                return

    # ── Detect key files ────────────────────────────────────────────────
    candidates = detect_doc_candidates(path)
    if candidates:
        key_files = _select_key_files(candidates, root=path)
    else:
        key_files_raw = _prompt("Key files (comma-separated, optional)")
        key_files = (
            [f.strip() for f in key_files_raw.split(",") if f.strip()]
            if key_files_raw
            else []
        )

    console.print("\n[dim]Create a profile:[/dim]")
    profile_name = _prompt("Profile name", default="default")
    profile_desc = _prompt("Description")

    # ── Write project.toml ───────────────────────────────────────────────
    _write_project_toml(ctxforge_dir, report, cli_config, profile_name, language)

    # ── Write profile ────────────────────────────────────────────────────
    pm.create(
        name=profile_name,
        description=profile_desc,
        key_files=key_files,
    )

    # ── Generate Claude Code slash commands (claude only) ────────────────
    active_cli = cli_config.active or ""
    write_commands(path, profile_name, active_cli)

    # ── Summary ──────────────────────────────────────────────────────────
    console.print(f"\n[bold green]Done.[/bold green] Created {CTXFORGE_DIR}/")
    console.print("  project.toml")
    console.print(f"  profiles/{profile_name}/profile.toml")
    if active_cli == "claude":
        console.print("  .claude/commands/ (slash commands)")


def _write_project_toml(
    ctxforge_dir: Path,
    report: ScanReport,
    cli_config: CliConfig,
    profile_name: str,
    language: str,
    model: str = "",
) -> None:
    project_config = ProjectConfig(
        project=ProjectSection(
            name=report.project_name,
            description="",
        ),
        cli=cli_config,
        defaults=DefaultsConfig(
            profile=profile_name,
            language=language,
            model=model or None,
        ),
    )
    ctxforge_dir.mkdir(exist_ok=True)
    write_project(ctxforge_dir / "project.toml", project_config)
