"""Generate .claude/commands/*.md for Claude Code slash commands."""

from __future__ import annotations

from pathlib import Path

from ctxforge.spec.schema import ProfileConfig


def write_commands(
    project_root: Path, profile_name: str, cli_name: str,
    profile_config: ProfileConfig | None = None,
) -> None:
    """Write ctxforge slash command files into .claude/commands/.

    Only generates commands when *cli_name* is ``"claude"``.
    Other CLIs do not support custom slash commands.

    Args:
        project_root: Project root directory (where .claude/ lives).
        profile_name: Active profile name (embedded into prompts).
        cli_name: Active CLI tool name (e.g. "claude", "codex").
        profile_config: Profile configuration (for work record paths).
    """
    if cli_name != "claude":
        return

    commands_dir = project_root / ".claude" / "commands"
    commands_dir.mkdir(parents=True, exist_ok=True)

    profile_dir = f".ctxforge/profiles/{profile_name}"
    profile_path = f"{profile_dir}/profile.toml"

    # Build work record paths from profile config
    work_record_files: dict[str, str] = {}
    if profile_config is not None:
        work_record_files = profile_config.work_record.files
    else:
        # Fallback for backwards compatibility
        work_record_files = {
            "journal.md": "work journal — completed tasks, in-progress, TODOs",
            "pitfalls.md": "pitfalls — gotchas, lessons learned, warnings",
        }

    record_paths = {
        name: f"{profile_dir}/{name}" for name in work_record_files
    }

    _write(commands_dir / "ctx-profile.md", _build_ctx_profile(profile_path))
    _write(commands_dir / "ctx-files.md", _build_ctx_files(profile_path))
    _write(
        commands_dir / "ctx-update.md",
        _build_ctx_update(profile_path, record_paths, work_record_files),
    )
    _write(
        commands_dir / "ctx-compress.md",
        _build_ctx_compress(profile_path, record_paths, work_record_files),
    )


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def _build_work_record_list(
    record_paths: dict[str, str],
    work_record_files: dict[str, str],
) -> str:
    """Build a markdown list of work record files with paths."""
    lines: list[str] = []
    for name, desc in work_record_files.items():
        path = record_paths[name]
        lines.append(f"- `{path}` ({desc})")
    return "\n".join(lines)


# ── Prompt builders ──────────────────────────────────────────────────────────


def _build_ctx_profile(profile_path: str) -> str:
    return CTX_PROFILE.format(profile_path=profile_path)


def _build_ctx_files(profile_path: str) -> str:
    return CTX_FILES.format(profile_path=profile_path)


def _build_ctx_update(
    profile_path: str,
    record_paths: dict[str, str],
    work_record_files: dict[str, str],
) -> str:
    record_list = _build_work_record_list(record_paths, work_record_files)
    return CTX_UPDATE.format(
        profile_path=profile_path,
        work_record_section=record_list,
    )


def _build_ctx_compress(
    profile_path: str,
    record_paths: dict[str, str],
    work_record_files: dict[str, str],
) -> str:
    record_list = _build_work_record_list(record_paths, work_record_files)
    return CTX_COMPRESS.format(
        profile_path=profile_path,
        work_record_section=record_list,
    )


# ── Prompt templates ─────────────────────────────────────────────────────────

CTX_PROFILE = """\
Read the ctxforge profile at `{profile_path}` and display:
- Profile name and description
- Role prompt (if set)
- Work record files
- Key files list
- Injection settings (strategy, order, greeting)
"""

CTX_FILES = """\
List all key files configured in `{profile_path}` under `[key_files]`.
For each file, show whether it exists and its approximate size (lines and characters).
"""

CTX_UPDATE = """\
Read `{profile_path}` to understand the current profile configuration.

## 1. Work record files — PRIORITY
Update the following work record files to reflect the current session. \
Create any that don't exist.

{work_record_section}

For **journal** files:
- Completed tasks: one-liner each, just the outcome — no details or rationale
- In-progress tasks: brief status note
- TODOs: be specific — include what needs to be done and why, so future sessions can act on them without extra context
- Remove tasks that are no longer relevant
- Structure: use headings like `## Completed`, `## In Progress`, `## TODO`

For **pitfalls** files:
- Append new non-obvious pitfalls, gotchas, or lessons learned
- Keep entries concise and actionable (one-liner + brief explanation)
- Do NOT duplicate entries already present in the file
- Remove entries that have been permanently resolved

## 2. Key files (listed in `{profile_path}` under `[key_files]`)
Based on changes made in the current session, update stale key files.
- Only update files whose content is actually outdated
- Preserve the existing structure and style of each file
- Do NOT rewrite files that are already accurate

Show a brief summary of all changes made.
- $ARGUMENTS
"""

CTX_COMPRESS = """\
Read `{profile_path}` to understand the current profile configuration.

## 1. Work record files — PRIORITY
Compress the following work record files to keep them focused and useful:

{work_record_section}

For **journal** files:
- Completed tasks: collapse to one-liner each; remove if no longer relevant for context
- In-progress: keep brief status
- TODOs: preserve specifics — these guide future sessions and must remain actionable
- Goal: the journal should fit the AI's working memory, not be a full history

For **pitfalls** files:
- Merge similar or related entries
- Remove entries for issues that have been permanently resolved
- Tighten wording — each entry should be a concise, actionable reminder
- Deduplicate entries that say the same thing differently

## 2. Key files (listed in `{profile_path}` under `[key_files]`)
For each key file, show its current size (lines/chars) and analyze compressibility.
Compression guidelines:
- Remove redundant explanations, verbose examples, and filler text
- Preserve all technical details, API signatures, and architectural decisions
- Keep headings and structure intact for readability
- Do NOT remove user_notes sections (marked with `cforge:user_notes`)

Show before/after size comparison for each compressed file.
Ask for confirmation before writing any changes.
- $ARGUMENTS
"""
