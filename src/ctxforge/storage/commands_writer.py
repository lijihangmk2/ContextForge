"""Generate .claude/commands/*.md for Claude Code slash commands."""

from __future__ import annotations

from pathlib import Path


def write_commands(project_root: Path, profile_name: str, cli_name: str) -> None:
    """Write ctxforge slash command files into .claude/commands/.

    Only generates commands when *cli_name* is ``"claude"``.
    Other CLIs do not support custom slash commands.

    Args:
        project_root: Project root directory (where .claude/ lives).
        profile_name: Active profile name (embedded into prompts).
        cli_name: Active CLI tool name (e.g. "claude", "codex").
    """
    if cli_name != "claude":
        return

    commands_dir = project_root / ".claude" / "commands"
    commands_dir.mkdir(parents=True, exist_ok=True)

    profile_path = f".ctxforge/profiles/{profile_name}/profile.toml"

    _write(commands_dir / "ctx-profile.md", _CTX_PROFILE.format(profile_path=profile_path))
    _write(commands_dir / "ctx-files.md", _CTX_FILES.format(profile_path=profile_path))
    _write(commands_dir / "ctx-update.md", _CTX_UPDATE.format(profile_path=profile_path))
    _write(commands_dir / "ctx-compress.md", _CTX_COMPRESS.format(profile_path=profile_path))


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


# ── Prompt templates ─────────────────────────────────────────────────────────

_CTX_PROFILE = """\
Read the ctxforge profile at `{profile_path}` and display:
- Profile name and description
- Role prompt (if set)
- Key files list
- Injection settings (strategy, order, greeting)
"""

_CTX_FILES = """\
List all key files configured in `{profile_path}` under `[key_files]`.
For each file, show whether it exists and its approximate size (lines and characters).
"""

_CTX_UPDATE = """\
Review the current project structure and the key files list in `{profile_path}`.
Analyze what context files would be most valuable for understanding this project.
Then update the `paths` array in the `[key_files]` section of `{profile_path}`.
Rules:
- Only add individual files, never directories
- Prefer documentation files (.md) and key source entry points
- Remove files that no longer exist
- Keep the total context concise — avoid large generated files
- $ARGUMENTS
"""

_CTX_COMPRESS = """\
Read all key files listed in `{profile_path}` under `[key_files]`.
For each file:
1. Show its current size (lines and characters)
2. Analyze whether the content can be compressed without losing essential information
3. If compressible, rewrite it more concisely while preserving all key facts and structure

Compression guidelines:
- Remove redundant explanations, verbose examples, and filler text
- Preserve all technical details, API signatures, and architectural decisions
- Keep headings and structure intact for readability
- Do NOT remove user_notes sections (marked with `cforge:user_notes`)
- Show before/after size comparison for each compressed file
- Ask for confirmation before writing any changes
- $ARGUMENTS
"""
