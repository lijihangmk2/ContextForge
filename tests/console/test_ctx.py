"""Tests for ctx sub-commands."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from ctxforge.console.application import app

runner = CliRunner()


class TestCtxProfile:
    def test_single_profile_auto(self, ctxforge_project: Path, monkeypatch):
        monkeypatch.chdir(ctxforge_project)
        result = runner.invoke(app, ["ctx", "profile"])
        assert result.exit_code == 0, result.output
        assert "default" in result.output

    def test_explicit_profile(self, ctxforge_project: Path, monkeypatch):
        monkeypatch.chdir(ctxforge_project)
        result = runner.invoke(app, ["ctx", "profile", "default"])
        assert result.exit_code == 0, result.output
        assert "default" in result.output
        assert "Injection" in result.output

    def test_profile_not_found(self, ctxforge_project: Path, monkeypatch):
        monkeypatch.chdir(ctxforge_project)
        result = runner.invoke(app, ["ctx", "profile", "nonexistent"])
        assert result.exit_code == 1

    def test_shows_description(self, ctxforge_project: Path, monkeypatch):
        monkeypatch.chdir(ctxforge_project)
        result = runner.invoke(app, ["ctx", "profile", "default"])
        assert result.exit_code == 0, result.output
        assert "Default profile" in result.output

    def test_shows_role_prompt(self, ctxforge_project: Path, monkeypatch):
        monkeypatch.chdir(ctxforge_project)
        result = runner.invoke(app, ["ctx", "profile", "default"])
        assert result.exit_code == 0, result.output
        assert "helpful assistant" in result.output


class TestCtxFiles:
    def test_no_key_files(self, ctxforge_project: Path, monkeypatch):
        monkeypatch.chdir(ctxforge_project)
        result = runner.invoke(app, ["ctx", "files"])
        assert result.exit_code == 0, result.output
        assert "No key files" in result.output

    def test_with_key_files(self, ctxforge_project: Path, monkeypatch):
        monkeypatch.chdir(ctxforge_project)
        # Create a key file
        readme = ctxforge_project / "README.md"
        readme.write_text("# Test\nHello world\n", encoding="utf-8")

        # Update profile to include key file
        from ctxforge.core.profile import ProfileManager
        from ctxforge.spec.schema import KeyFilesSection, ProfileConfig, ProfileSection, RoleSection
        from ctxforge.storage.profile_writer import write_profile

        profile_path = ctxforge_project / ".ctxforge" / "profiles" / "default" / "profile.toml"
        config = ProfileConfig(
            profile=ProfileSection(name="default", description="Default profile"),
            role=RoleSection(prompt="You are a helpful assistant."),
            key_files=KeyFilesSection(paths=["README.md"]),
        )
        write_profile(profile_path, config)

        result = runner.invoke(app, ["ctx", "files"])
        assert result.exit_code == 0, result.output
        assert "README.md" in result.output
        assert "yes" in result.output

    def test_missing_file(self, ctxforge_project: Path, monkeypatch):
        monkeypatch.chdir(ctxforge_project)
        from ctxforge.spec.schema import KeyFilesSection, ProfileConfig, ProfileSection, RoleSection
        from ctxforge.storage.profile_writer import write_profile

        profile_path = ctxforge_project / ".ctxforge" / "profiles" / "default" / "profile.toml"
        config = ProfileConfig(
            profile=ProfileSection(name="default"),
            key_files=KeyFilesSection(paths=["nonexistent.md"]),
        )
        write_profile(profile_path, config)

        result = runner.invoke(app, ["ctx", "files"])
        assert result.exit_code == 0, result.output
        assert "no" in result.output


class TestCtxUpdate:
    def test_update_single_profile(self, ctxforge_project: Path, monkeypatch):
        monkeypatch.chdir(ctxforge_project)
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("ctxforge.runner.claude.subprocess.run", return_value=mock_result) as mock_run:
            result = runner.invoke(app, ["ctx", "update"])
        assert result.exit_code == 0, result.output
        assert "Updating" in result.output
        # Verify claude -p was called with session isolation
        call_args = mock_run.call_args[0][0]
        assert call_args[0] == "claude"
        assert "--no-session-persistence" in call_args
        assert "-p" in call_args

    def test_update_explicit_profile(self, ctxforge_project: Path, monkeypatch):
        monkeypatch.chdir(ctxforge_project)
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("ctxforge.runner.claude.subprocess.run", return_value=mock_result):
            result = runner.invoke(app, ["ctx", "update", "default"])
        assert result.exit_code == 0, result.output

    def test_update_profile_not_found(self, ctxforge_project: Path, monkeypatch):
        monkeypatch.chdir(ctxforge_project)
        result = runner.invoke(app, ["ctx", "update", "nonexistent"])
        assert result.exit_code == 1


class TestCtxCompress:
    def test_compress_single_profile(self, ctxforge_project: Path, monkeypatch):
        monkeypatch.chdir(ctxforge_project)
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("ctxforge.runner.claude.subprocess.run", return_value=mock_result) as mock_run:
            result = runner.invoke(app, ["ctx", "compress"])
        assert result.exit_code == 0, result.output
        assert "Compressing" in result.output
        call_args = mock_run.call_args[0][0]
        assert call_args[0] == "claude"
        assert "--no-session-persistence" in call_args
        assert "-p" in call_args

    def test_compress_explicit_profile(self, ctxforge_project: Path, monkeypatch):
        monkeypatch.chdir(ctxforge_project)
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("ctxforge.runner.claude.subprocess.run", return_value=mock_result):
            result = runner.invoke(app, ["ctx", "compress", "default"])
        assert result.exit_code == 0, result.output


class TestCtxUpdateAll:
    def _make_multi_profile(self, ctxforge_project: Path) -> None:
        """Create a second profile for multi-profile testing."""
        from ctxforge.spec.schema import (
            CURRENT_PROFILE_VERSION,
            ProfileCliSection,
            ProfileConfig,
            ProfileSection,
        )
        from ctxforge.storage.profile_writer import write_profile

        profile_dir = ctxforge_project / ".ctxforge" / "profiles" / "reviewer"
        profile_dir.mkdir(parents=True)
        config = ProfileConfig(
            schema_version=CURRENT_PROFILE_VERSION,
            profile=ProfileSection(name="reviewer", description="Code reviewer"),
            cli=ProfileCliSection(name="claude"),
        )
        write_profile(profile_dir / "profile.toml", config)

    def test_update_all_flag(self, ctxforge_project: Path, monkeypatch):
        monkeypatch.chdir(ctxforge_project)
        self._make_multi_profile(ctxforge_project)

        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("ctxforge.runner.claude.subprocess.run", return_value=mock_result) as mock_run:
            result = runner.invoke(app, ["ctx", "update", "--all"])
        assert result.exit_code == 0, result.output
        # Should be called once per profile
        assert mock_run.call_count == 2

    def test_compress_all_flag(self, ctxforge_project: Path, monkeypatch):
        monkeypatch.chdir(ctxforge_project)
        self._make_multi_profile(ctxforge_project)

        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("ctxforge.runner.claude.subprocess.run", return_value=mock_result) as mock_run:
            result = runner.invoke(app, ["ctx", "compress", "--all"])
        assert result.exit_code == 0, result.output
        assert mock_run.call_count == 2

    def test_multi_profile_no_arg_non_tty(self, ctxforge_project: Path, monkeypatch):
        """Non-TTY without --all or profile should error."""
        monkeypatch.chdir(ctxforge_project)
        self._make_multi_profile(ctxforge_project)

        result = runner.invoke(app, ["ctx", "update"])
        assert result.exit_code == 1


class TestNoProject:
    def test_ctx_profile_no_project(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["ctx", "profile"])
        assert result.exit_code == 1
        assert "No ctxforge project" in result.output

    def test_ctx_files_no_project(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["ctx", "files"])
        assert result.exit_code == 1
