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
          - "role_first": role prompt → key files → pitfalls → user prompt
          - "files_first": key files → role prompt → pitfalls → user prompt
        """
        role_part = self._role_section(profile)
        files_part = self._files_section(profile)
        pitfalls_part = self._pitfalls_section(profile)
        user_part = user_prompt.strip()

        if profile.injection.order == "files_first":
            parts = [files_part, role_part, pitfalls_part, user_part]
        else:
            parts = [role_part, files_part, pitfalls_part, user_part]

        return "\n\n".join(p for p in parts if p)

    def build_system(
        self, profile: ProfileConfig, language: str | None = None
    ) -> str:
        """Build a system prompt (no user prompt) for interactive mode.

        Sections are ordered according to ``profile.injection.order``:
          - "role_first": role → key files → pitfalls → language
          - "files_first": key files → role → pitfalls → language
        """
        role_part = self._role_section(profile)
        files_part = self._files_section(profile)
        pitfalls_part = self._pitfalls_section(profile)
        lang_part = self._language_section(language)

        if profile.injection.order == "files_first":
            parts = [files_part, role_part, pitfalls_part, lang_part]
        else:
            parts = [role_part, files_part, pitfalls_part, lang_part]

        return "\n\n".join(p for p in parts if p)

    def _role_section(self, profile: ProfileConfig) -> str:
        prompt = profile.role.prompt.strip()
        if not prompt:
            return ""
        return f"[Role: {profile.profile.name}]\n{prompt}"

    def _pitfalls_section(self, profile: ProfileConfig) -> str:
        path = (
            self._root / ".ctxforge" / "profiles"
            / profile.profile.name / "pitfalls.md"
        )
        if not path.is_file():
            return ""
        content = path.read_text(encoding="utf-8").strip()
        if not content:
            return ""
        return f"[Pitfalls]\n{content}"

    def _files_section(self, profile: ProfileConfig) -> str:
        if not profile.key_files.paths:
            return ""
        lines: list[str] = []
        for rel_path in profile.key_files.paths:
            full = self._root / rel_path
            if full.is_file():
                lines.append(f"- {rel_path}")
        if not lines:
            return ""
        header = (
            "[Key Files]\n"
            "Read the following files to understand the project context:"
        )
        return header + "\n" + "\n".join(lines)

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
        role_name = profile.profile.name
        lang_hint = f" Respond in {language}." if language else ""
        parts = [
            f"You are now operating as profile \"{role_name}\".",
        ]
        if profile.key_files.paths:
            file_list = ", ".join(profile.key_files.paths)
            parts.append(f"Key files loaded: {file_list}.")
        parts.append(
            "Briefly confirm (2-3 lines) that you have received this context "
            f"and are ready.{lang_hint}"
        )
        return " ".join(parts)

    @staticmethod
    def build_compress_greeting(
        profile: ProfileConfig, language: str | None = None
    ) -> str:
        """Build a greeting that asks the AI to compress large key files."""
        role_name = profile.profile.name
        lang_hint = f" Respond in {language}." if language else ""
        file_list = ", ".join(profile.key_files.paths)
        return (
            f'You are now operating as profile "{role_name}". '
            f"Key files loaded: {file_list}.\n\n"
            "Before we begin, please analyze the key files and compress any that are too large. "
            "For each file, decide whether to compress, merge with related files, or keep as-is. "
            "Compression guidelines:\n"
            "- Remove redundant explanations, verbose examples, and filler text\n"
            "- Preserve all technical details, API signatures, and architectural decisions\n"
            "- Keep headings and structure for readability\n"
            "- Show before/after size comparison\n"
            "- Ask for confirmation before writing changes\n\n"
            f"After compression, briefly confirm you are ready.{lang_hint}"
        )

