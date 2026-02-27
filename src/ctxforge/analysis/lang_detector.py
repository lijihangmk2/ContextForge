"""Language detection via file extension statistics."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

# Map file extensions to language names
EXTENSION_MAP: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".jsx": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".kt": "kotlin",
    ".rb": "ruby",
    ".php": "php",
    ".cs": "csharp",
    ".cpp": "cpp",
    ".c": "c",
    ".h": "c",
    ".hpp": "cpp",
    ".swift": "swift",
    ".scala": "scala",
    ".ex": "elixir",
    ".exs": "elixir",
    ".lua": "lua",
    ".r": "r",
    ".R": "r",
    ".dart": "dart",
    ".zig": "zig",
    ".vue": "vue",
    ".svelte": "svelte",
}

# Minimum file count to consider a language significant
MIN_FILES = 2


def detect_languages(files: list[Path], min_files: int = MIN_FILES) -> list[str]:
    """Detect project languages by counting file extensions.

    Args:
        files: List of file paths.
        min_files: Minimum number of files to consider a language.

    Returns:
        List of detected language names, sorted by frequency (most common first).
    """
    counter: Counter[str] = Counter()
    for f in files:
        suffix = f.suffix.lower()
        lang = EXTENSION_MAP.get(suffix)
        if lang:
            counter[lang] += 1

    return [lang for lang, count in counter.most_common() if count >= min_files]
