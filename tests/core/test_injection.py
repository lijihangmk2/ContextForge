"""Tests for injection strategies."""

from pathlib import Path

from ctxforge.core.injection import SimpleInjection
from ctxforge.spec.schema import (
    InjectionSection,
    KeyFilesSection,
    ProfileConfig,
    ProfileSection,
    RoleSection,
)


def _make_profile(
    *,
    role_prompt: str = "",
    key_files: list[str] | None = None,
    order: str = "role_first",
    greeting: bool = True,
) -> ProfileConfig:
    return ProfileConfig(
        profile=ProfileSection(name="test"),
        role=RoleSection(prompt=role_prompt),
        key_files=KeyFilesSection(paths=key_files or []),
        injection=InjectionSection(order=order, greeting=greeting),
    )


class TestSimpleInjection:
    def test_role_only(self, tmp_path: Path):
        inj = SimpleInjection(tmp_path)
        profile = _make_profile(role_prompt="You are an architect.")
        result = inj.build(profile, "explain the project")
        assert "[Role: test]" in result
        assert "You are an architect." in result
        assert "explain the project" in result

    def test_with_key_files(self, tmp_path: Path):
        (tmp_path / "readme.md").write_text("# Hello")
        inj = SimpleInjection(tmp_path)
        profile = _make_profile(key_files=["readme.md"])
        result = inj.build(profile, "summarize")
        assert "--- readme.md ---" in result
        assert "# Hello" in result

    def test_missing_key_file_skipped(self, tmp_path: Path):
        inj = SimpleInjection(tmp_path)
        profile = _make_profile(key_files=["nonexistent.md"])
        result = inj.build(profile, "go")
        assert "nonexistent.md" not in result

    def test_files_first_order(self, tmp_path: Path):
        (tmp_path / "f.txt").write_text("file content")
        inj = SimpleInjection(tmp_path)
        profile = _make_profile(
            role_prompt="Be helpful.", key_files=["f.txt"], order="files_first"
        )
        result = inj.build(profile, "do stuff")
        files_pos = result.index("[Key Files]")
        role_pos = result.index("[Role: test]")
        assert files_pos < role_pos

    def test_empty_role_and_files(self, tmp_path: Path):
        inj = SimpleInjection(tmp_path)
        profile = _make_profile()
        result = inj.build(profile, "hello")
        assert result == "hello"

    def test_dir_path_skipped(self, tmp_path: Path):
        """Directory paths in key_files are silently skipped."""
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "api.md").write_text("API docs")
        inj = SimpleInjection(tmp_path)
        profile = _make_profile(key_files=["docs/"])
        result = inj.build(profile, "go")
        assert "[Key Files]" not in result


class TestBuildSystem:
    def test_build_system_role_and_files(self, tmp_path: Path):
        (tmp_path / "readme.md").write_text("# Project")
        inj = SimpleInjection(tmp_path)
        profile = _make_profile(role_prompt="You are a reviewer.", key_files=["readme.md"])
        result = inj.build_system(profile)
        assert "[Role: test]" in result
        assert "You are a reviewer." in result
        assert "--- readme.md ---" in result
        assert "# Project" in result

    def test_build_system_with_language(self, tmp_path: Path):
        inj = SimpleInjection(tmp_path)
        profile = _make_profile(role_prompt="Be helpful.")
        result = inj.build_system(profile, language="中文")
        assert "[Language]" in result
        assert "Please respond in 中文." in result
        # Language section should come after role
        role_pos = result.index("[Role: test]")
        lang_pos = result.index("[Language]")
        assert lang_pos > role_pos

    def test_build_system_no_language(self, tmp_path: Path):
        inj = SimpleInjection(tmp_path)
        profile = _make_profile(role_prompt="Be helpful.")
        result = inj.build_system(profile)
        assert "[Language]" not in result

    def test_build_system_empty(self, tmp_path: Path):
        inj = SimpleInjection(tmp_path)
        profile = _make_profile(greeting=False)
        result = inj.build_system(profile)
        assert result == ""

    def test_build_system_no_greeting_section(self, tmp_path: Path):
        """System prompt should never contain greeting content."""
        inj = SimpleInjection(tmp_path)
        profile = _make_profile(role_prompt="Be helpful.")
        result = inj.build_system(profile)
        assert "[Greeting]" not in result
        assert "confirm" not in result.lower()


class TestBuildGreeting:
    def test_greeting_default(self, tmp_path: Path):
        inj = SimpleInjection(tmp_path)
        profile = _make_profile()
        result = inj.build_greeting(profile)
        assert '"test"' in result
        assert "confirm" in result.lower()

    def test_greeting_with_files(self, tmp_path: Path):
        inj = SimpleInjection(tmp_path)
        profile = _make_profile(key_files=["readme.md"])
        result = inj.build_greeting(profile)
        assert "readme.md" in result

    def test_greeting_with_language(self, tmp_path: Path):
        inj = SimpleInjection(tmp_path)
        profile = _make_profile()
        result = inj.build_greeting(profile, language="中文")
        assert "中文" in result

    def test_greeting_disabled(self, tmp_path: Path):
        inj = SimpleInjection(tmp_path)
        profile = _make_profile(greeting=False)
        result = inj.build_greeting(profile)
        assert result == ""
