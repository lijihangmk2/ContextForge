"""Context injection strategies."""

from __future__ import annotations

from pathlib import Path

from ctxforge.spec.schema import ProfileConfig


class SimpleInjection:
    """Concatenate role prompt + key file contents + user prompt."""

    def __init__(self, project_root: Path) -> None:
        self._root = project_root

    def build(self, profile: ProfileConfig, user_prompt: str) -> str:
        """Assemble the full prompt.

        Order is determined by profile.injection.order:
          - "role_first": role prompt → key files → user prompt
          - "files_first": key files → role prompt → user prompt
        """
        role_part = self._role_section(profile)
        files_part = self._files_section(profile)
        user_part = user_prompt.strip()

        if profile.injection.order == "files_first":
            parts = [files_part, role_part, user_part]
        else:
            parts = [role_part, files_part, user_part]

        return "\n\n".join(p for p in parts if p)

    def build_system(
        self, profile: ProfileConfig, language: str | None = None
    ) -> str:
        """Build a system prompt (no user prompt) for interactive mode.

        Sections are ordered according to ``profile.injection.order``:
          - "role_first": role → key files → language
          - "files_first": key files → role → language
        """
        role_part = self._role_section(profile)
        files_part = self._files_section(profile)
        lang_part = self._language_section(language)

        if profile.injection.order == "files_first":
            parts = [files_part, role_part, lang_part]
        else:
            parts = [role_part, files_part, lang_part]

        return "\n\n".join(p for p in parts if p)

    def _role_section(self, profile: ProfileConfig) -> str:
        prompt = profile.role.prompt.strip()
        if not prompt:
            return ""
        return f"[Role: {profile.profile.name}]\n{prompt}"

    def _files_section(self, profile: ProfileConfig) -> str:
        if not profile.key_files.paths:
            return ""
        sections: list[str] = []
        for rel_path in profile.key_files.paths:
            full = self._root / rel_path
            if full.is_file():
                self._append_file(sections, rel_path, full)
        if not sections:
            return ""
        return "[Key Files]\n" + "\n\n".join(sections)

    @staticmethod
    def _language_section(language: str | None) -> str:
        if not language:
            return ""
        return f"[Language]\nPlease respond in {language}."

    @staticmethod
    def build_greeting(profile: ProfileConfig, language: str | None = None) -> str:
        """Build an initial user prompt that asks the AI to confirm loaded context.

        Returns empty string when greeting is disabled.
        """
        if not profile.injection.greeting:
            return ""
        file_list = ", ".join(profile.key_files.paths) if profile.key_files.paths else ""
        role_name = profile.profile.name
        lang_hint = f" Respond in {language}." if language else ""
        parts = [
            f"You are now operating as profile \"{role_name}\".",
        ]
        if file_list:
            parts.append(f"Key files loaded: {file_list}.")
        parts.append(
            "Briefly confirm (2-3 lines) that you have received this context "
            f"and are ready.{lang_hint}"
        )
        return " ".join(parts)

    def _append_file(
        self, sections: list[str], rel_path: str, full: Path
    ) -> None:
        try:
            content = full.read_text(encoding="utf-8")
        except Exception:
            content = f"(failed to read {rel_path})"
        sections.append(f"--- {rel_path} ---\n{content}")
