"""Prompt builder — high-level API for constructing injected prompts."""

from __future__ import annotations

from pathlib import Path

from ctxforge.core.injection import SimpleInjection
from ctxforge.spec.schema import ProfileConfig


class PromptBuilder:
    """Build a context-injected prompt from a profile and user input."""

    def __init__(self, project_root: Path) -> None:
        self._injector = SimpleInjection(project_root)

    def build(self, profile: ProfileConfig, user_prompt: str) -> str:
        return self._injector.build(profile, user_prompt)

    def build_system(
        self, profile: ProfileConfig, language: str | None = None
    ) -> str:
        return self._injector.build_system(profile, language)

    def build_greeting(
        self, profile: ProfileConfig, language: str | None = None
    ) -> str:
        return self._injector.build_greeting(profile, language)
