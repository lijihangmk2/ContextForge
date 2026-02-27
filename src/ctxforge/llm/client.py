"""LLM client for project analysis — dispatches to native SDKs via provider."""

from __future__ import annotations

import json
import re

from ctxforge.llm.provider import SDKNotInstalledError, call_llm

# Re-export for backward compatibility with init command imports.
LLMNotAvailableError = SDKNotInstalledError


def suggest_key_files(
    model: str,
    project_name: str,
    languages: list[str],
    dir_tree: list[str],
    config_files: list[str],
    language: str = "English",
) -> list[str]:
    """Ask an LLM to suggest key files worth tracking for a project.

    Args:
        model: Model name (e.g. "claude-sonnet-4-20250514", "gpt-4o").
        project_name: Name of the project.
        languages: Detected programming languages.
        dir_tree: Directory tree of the project.
        config_files: Config files found in root.
        language: Output language preference.

    Returns:
        List of suggested file paths.

    Raises:
        SDKNotInstalledError: If the required SDK is not installed.
    """
    system_prompt, user_prompt = _build_prompt(
        project_name, languages, dir_tree, config_files, language
    )
    content = call_llm(model, system_prompt, user_prompt)
    return _parse_file_list(content)


def _build_prompt(
    project_name: str,
    languages: list[str],
    dir_tree: list[str],
    config_files: list[str],
    language: str,
) -> tuple[str, str]:
    """Build system and user prompts for key-file suggestion.

    Returns:
        A (system_prompt, user_prompt) tuple.
    """
    tree_text = "\n".join(f"  {d}" for d in dir_tree) if dir_tree else "  (empty)"
    configs_text = ", ".join(config_files) if config_files else "none"
    langs_text = ", ".join(languages) if languages else "unknown"

    system_prompt = (
        "You are analyzing a software project to suggest key documentation"
        " and configuration files that an AI assistant should read to"
        " understand the project."
    )

    user_prompt = f"""Project: {project_name}
Languages: {langs_text}
Config files: {configs_text}

Directory structure:
{tree_text}

Based on this project structure, suggest 3-10 important documentation\
 and configuration files that an AI assistant should track. Focus on:
- README, CHANGELOG, and documentation files
- Design documents and architecture decision records (ADR)
- Project configuration files (pyproject.toml, package.json, etc.)
- API specifications (OpenAPI, GraphQL schema, etc.)
- Contributing guides and style guides

Do NOT include source code files (.py, .ts, .js, .go, etc.).

Respond in {language}. Return ONLY a JSON array of file paths, no explanation.
Example: ["README.md", "docs/architecture.md", "pyproject.toml"]"""

    return system_prompt, user_prompt


def _parse_file_list(content: str) -> list[str]:
    """Extract a JSON array of file paths from LLM response."""
    # Try direct JSON parse first
    content = content.strip()
    try:
        result = json.loads(content)
        if isinstance(result, list):
            return [str(item) for item in result if isinstance(item, str)]
    except json.JSONDecodeError:
        pass

    # Fallback: find JSON array in the text
    match = re.search(r"\[.*?\]", content, re.DOTALL)
    if match:
        try:
            result = json.loads(match.group())
            if isinstance(result, list):
                return [str(item) for item in result if isinstance(item, str)]
        except json.JSONDecodeError:
            pass

    return []
