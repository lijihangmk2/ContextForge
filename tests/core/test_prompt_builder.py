"""Tests for PromptBuilder."""

from pathlib import Path

from ctxforge.core.prompt_builder import PromptBuilder
from ctxforge.spec.schema import (
    ProfileConfig,
    ProfileSection,
    RoleSection,
)


class TestPromptBuilder:
    def test_build_basic(self, tmp_path: Path):
        builder = PromptBuilder(tmp_path)
        profile = ProfileConfig(
            profile=ProfileSection(name="dev"),
            role=RoleSection(prompt="Write clean code."),
        )
        result = builder.build(profile, "fix the bug")
        assert "Write clean code." in result
        assert "fix the bug" in result

    def test_build_no_role(self, tmp_path: Path):
        builder = PromptBuilder(tmp_path)
        profile = ProfileConfig(profile=ProfileSection(name="dev"))
        result = builder.build(profile, "hello")
        assert result == "hello"

    def test_build_with_files(self, tmp_path: Path):
        (tmp_path / "main.py").write_text("print('hi')")
        builder = PromptBuilder(tmp_path)
        profile = ProfileConfig(
            profile=ProfileSection(name="dev"),
        )
        profile.key_files.paths = ["main.py"]
        result = builder.build(profile, "explain")
        assert "main.py" in result
        assert "print('hi')" in result

    def test_build_system(self, tmp_path: Path):
        builder = PromptBuilder(tmp_path)
        profile = ProfileConfig(
            profile=ProfileSection(name="dev"),
            role=RoleSection(prompt="Write clean code."),
        )
        result = builder.build_system(profile, language="English")
        assert "Write clean code." in result
        assert "[Language]" in result
        assert "Please respond in English." in result
