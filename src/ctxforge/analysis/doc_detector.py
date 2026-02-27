"""Static detection of documentation and configuration files."""

from __future__ import annotations

from pathlib import Path

# Case-insensitive prefixes for documentation files at project root.
_DOC_FILE_PREFIXES: list[str] = [
    "README",
    "CHANGELOG",
    "CONTRIBUTING",
    "LICENSE",
    "ARCHITECTURE",
    "SECURITY",
    "CODE_OF_CONDUCT",
]

# Directory names whose *.md contents are scanned individually.
_DOC_DIRS: list[str] = [
    "docs",
    "doc",
    "design",
    "wiki",
    "adr",
]

# Maximum number of candidates returned.
_MAX_RESULTS: int = 30


def detect_doc_candidates(root: Path) -> list[str]:
    """Return documentation file paths found under *root*, sorted by priority.

    Only individual files are returned (no directory entries).
    Files are returned as relative paths (e.g. ``README.md``, ``docs/guide.md``).

    Subdirectory markdown scanning is limited to known doc/design directories.
    Results are capped at 30 entries, sorted by path length within each group.

    Order: root doc files (known prefixes) → root other \\*.md →
    doc-dir \\*.md.
    """
    doc_files: list[str] = []
    sub_md_files: list[str] = []

    # --- documentation files (case-insensitive prefix match) ---
    for prefix in _DOC_FILE_PREFIXES:
        for entry in sorted(root.iterdir()):
            if entry.is_file() and entry.name.upper().startswith(prefix.upper()):
                doc_files.append(entry.name)

    # --- other markdown files at root (*.md not already matched) ---
    seen = {name.lower() for name in doc_files}
    for entry in sorted(root.iterdir()):
        if (
            entry.is_file()
            and entry.suffix.lower() == ".md"
            and entry.name.lower() not in seen
        ):
            doc_files.append(entry.name)

    # --- markdown files inside known doc directories only ---
    seen_all = {name.lower() for name in doc_files}
    for dir_name in _DOC_DIRS:
        for entry in sorted(root.iterdir()):
            if not entry.is_dir() or entry.name.lower() != dir_name.lower():
                continue
            for md_file in sorted(entry.rglob("*.md")):
                if not md_file.is_file():
                    continue
                rel_str = str(md_file.relative_to(root))
                if rel_str.lower() not in seen_all:
                    seen_all.add(rel_str.lower())
                    sub_md_files.append(rel_str)

    # sort each group by path length, then combine and cap
    doc_files.sort(key=len)
    sub_md_files.sort(key=len)

    combined = doc_files + sub_md_files
    return combined[:_MAX_RESULTS]
