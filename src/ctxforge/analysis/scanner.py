"""Project directory scanner — static analysis entry point."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ctxforge.analysis.lang_detector import detect_languages

# Default patterns to exclude from scanning
DEFAULT_EXCLUDES = frozenset(
    {
        "node_modules",
        ".venv",
        "venv",
        "__pycache__",
        ".git",
        ".hg",
        ".svn",
        "dist",
        "build",
        ".eggs",
        ".tox",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".ctxforge",
    }
)


@dataclass
class ScanReport:
    """Result of static project analysis."""

    project_name: str = ""
    dir_tree: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    config_files: list[str] = field(default_factory=list)


def scan_project(root: Path, excludes: frozenset[str] | None = None) -> ScanReport:
    """Scan a project directory and produce a structured report.

    Only collects raw data: directory tree, languages, config files, entry points.
    Deeper analysis (frameworks, architecture, conventions) is left to LLM in P2.
    """
    if excludes is None:
        excludes = DEFAULT_EXCLUDES

    report = ScanReport()
    report.project_name = root.name

    # Collect all files (respecting excludes)
    all_files = _collect_files(root, excludes)

    # Build directory tree (relative paths)
    report.dir_tree = _build_dir_tree(root, excludes)

    # Detect languages
    report.languages = detect_languages(all_files)

    # Find config files
    report.config_files = _find_config_files(root)

    return report


def _collect_files(root: Path, excludes: frozenset[str]) -> list[Path]:
    """Collect all files under root, skipping excluded directories."""
    files: list[Path] = []
    for item in root.rglob("*"):
        if any(part in excludes for part in item.parts):
            continue
        if item.is_file():
            files.append(item)
    return files


def _build_dir_tree(root: Path, excludes: frozenset[str], max_depth: int = 3) -> list[str]:
    """Build a list of directory paths relative to root, up to max_depth."""
    dirs: list[str] = []
    for item in sorted(root.rglob("*")):
        if not item.is_dir():
            continue
        rel = item.relative_to(root)
        if any(part in excludes for part in rel.parts):
            continue
        if len(rel.parts) > max_depth:
            continue
        dirs.append(str(rel))
    return dirs


def _find_config_files(root: Path) -> list[str]:
    """Find known configuration files in the project root."""
    known_configs = [
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "package.json",
        "tsconfig.json",
        "go.mod",
        "Cargo.toml",
        "Makefile",
        "Dockerfile",
        "docker-compose.yml",
        "docker-compose.yaml",
        ".env.example",
        "alembic.ini",
        "tox.ini",
    ]
    return [name for name in known_configs if (root / name).exists()]


