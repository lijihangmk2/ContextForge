"""Tests for injection strategies."""

from pathlib import Path

from ctxforge.core.injection import SimpleInjection
from ctxforge.spec.schema import (
    InjectionSection,
    KeyFilesSection,
    ProfileConfig,
    ProfileSection,
    RoleSection,
    WorkRecordSection,
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
        assert "- readme.md" in result

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
        assert "- f.txt" in result
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


class TestWorkRecordSection:
    def test_no_files(self, tmp_path: Path):
        inj = SimpleInjection(tmp_path)
        profile = _make_profile(role_prompt="Be helpful.")
        result = inj._work_record_section(profile)
        assert result == ""

    def test_with_files(self, tmp_path: Path):
        profile_dir = tmp_path / ".ctxforge" / "profiles" / "test"
        profile_dir.mkdir(parents=True)
        (profile_dir / "journal.md").write_text("## TODO\n- fix bug")
        (profile_dir / "pitfalls.md").write_text("- Watch out for X\n")
        inj = SimpleInjection(tmp_path)
        profile = _make_profile()
        result = inj._work_record_section(profile)
        assert "[Work Record]" in result
        assert "journal.md" in result
        assert "pitfalls.md" in result

    def test_empty_files_still_listed(self, tmp_path: Path):
        """Empty files exist on disk — still referenced so AI can write to them."""
        profile_dir = tmp_path / ".ctxforge" / "profiles" / "test"
        profile_dir.mkdir(parents=True)
        (profile_dir / "journal.md").write_text("")
        (profile_dir / "pitfalls.md").write_text("")
        inj = SimpleInjection(tmp_path)
        profile = _make_profile()
        result = inj._work_record_section(profile)
        assert "[Work Record]" in result
        assert "journal.md" in result
        assert "pitfalls.md" in result

    def test_build_includes_work_record(self, tmp_path: Path):
        profile_dir = tmp_path / ".ctxforge" / "profiles" / "test"
        profile_dir.mkdir(parents=True)
        (profile_dir / "journal.md").write_text("## TODO\n- task")
        (profile_dir / "pitfalls.md").write_text("- gotcha")
        inj = SimpleInjection(tmp_path)
        profile = _make_profile(role_prompt="Be helpful.")
        result = inj.build(profile, "do stuff")
        assert "[Work Record]" in result

    def test_build_system_includes_work_record(self, tmp_path: Path):
        profile_dir = tmp_path / ".ctxforge" / "profiles" / "test"
        profile_dir.mkdir(parents=True)
        (profile_dir / "pitfalls.md").write_text("- Pitfall B\n")
        inj = SimpleInjection(tmp_path)
        profile = _make_profile(role_prompt="Be helpful.")
        result = inj.build_system(profile)
        assert "[Work Record]" in result
        assert "pitfalls.md" in result


class TestBuildSystem:
    def test_build_system_role_and_files(self, tmp_path: Path):
        (tmp_path / "readme.md").write_text("# Project")
        inj = SimpleInjection(tmp_path)
        profile = _make_profile(role_prompt="You are a reviewer.", key_files=["readme.md"])
        result = inj.build_system(profile)
        assert "[Role: test]" in result
        assert "You are a reviewer." in result
        assert "- readme.md" in result

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


class TestBuildCompressGreeting:
    def test_compress_greeting_basic(self, tmp_path: Path):
        profile = _make_profile(key_files=["readme.md", "design.md"])
        result = SimpleInjection.build_compress_greeting(profile)
        assert '"test"' in result
        assert "readme.md" in result
        assert "design.md" in result
        assert "compress" in result.lower()

    def test_compress_greeting_with_language(self, tmp_path: Path):
        profile = _make_profile(key_files=["readme.md"])
        result = SimpleInjection.build_compress_greeting(profile, language="中文")
        assert "中文" in result

    def test_compress_greeting_no_language(self, tmp_path: Path):
        profile = _make_profile(key_files=["readme.md"])
        result = SimpleInjection.build_compress_greeting(profile)
        assert "Respond in" not in result
