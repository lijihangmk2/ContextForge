"""Integration tests for CLI commands."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from ctxforge.console.application import app

runner = CliRunner()


class TestInitCommand:
    def test_init_creates_structure(self, tmp_path: Path):
        # language → detect (empty) → key files prompt → profile name → description
        with (
            patch("ctxforge.console.commands.init.detect_ai_clis", return_value=["claude"]),
            patch("ctxforge.console.commands.init.detect_doc_candidates", return_value=[]),
        ):
            result = runner.invoke(
                app,
                ["init", str(tmp_path)],
                input="English\n\ndefault\nGeneral assistant\n",
            )
        assert result.exit_code == 0, result.output
        assert (tmp_path / ".ctxforge" / "project.toml").exists()
        assert (tmp_path / ".ctxforge" / "profiles" / "default" / "profile.toml").exists()

    def test_init_no_cli(self, tmp_path: Path):
        # language → detect (empty) → key files prompt → profile name → description
        with (
            patch("ctxforge.console.commands.init.detect_ai_clis", return_value=[]),
            patch("ctxforge.console.commands.init.detect_doc_candidates", return_value=[]),
        ):
            result = runner.invoke(
                app,
                ["init", str(tmp_path)],
                input="English\n\ndefault\n\n",
            )
        assert result.exit_code == 0, result.output
        assert "No AI CLI tools detected" in result.output

    def test_init_with_doc_detection(self, tmp_path: Path):
        """Init with doc detection — all candidates accepted via checkbox."""
        candidates = ["README.md", "CHANGELOG.md", "docs/guide.md"]
        with (
            patch("ctxforge.console.commands.init.detect_ai_clis", return_value=["claude"]),
            patch(
                "ctxforge.console.commands.init.detect_doc_candidates",
                return_value=candidates,
            ) as mock_detect,
            patch(
                "ctxforge.console.commands.init._select_key_files",
                return_value=candidates,
            ),
        ):
            # language → (checkbox mocked) → profile name → description
            result = runner.invoke(
                app,
                ["init", str(tmp_path)],
                input="English\ndefault\nGeneral assistant\n",
            )
        assert result.exit_code == 0, result.output
        mock_detect.assert_called_once()

    def test_init_select_none(self, tmp_path: Path):
        """Init with doc detection — user deselects all in checkbox."""
        candidates = ["README.md"]
        with (
            patch("ctxforge.console.commands.init.detect_ai_clis", return_value=["claude"]),
            patch(
                "ctxforge.console.commands.init.detect_doc_candidates",
                return_value=candidates,
            ),
            patch(
                "ctxforge.console.commands.init._select_key_files",
                return_value=[],
            ),
        ):
            # language → (checkbox mocked) → profile name → description
            result = runner.invoke(
                app,
                ["init", str(tmp_path)],
                input="English\ndefault\n\n",
            )
        assert result.exit_code == 0, result.output

    def test_init_select_one(self, tmp_path: Path):
        """Init with doc detection — user selects a single file in checkbox."""
        candidates = ["README.md", "pyproject.toml"]
        with (
            patch("ctxforge.console.commands.init.detect_ai_clis", return_value=["claude"]),
            patch(
                "ctxforge.console.commands.init.detect_doc_candidates",
                return_value=candidates,
            ),
            patch(
                "ctxforge.console.commands.init._select_key_files",
                return_value=["README.md"],
            ),
        ):
            # language → (checkbox mocked) → profile name → description
            result = runner.invoke(
                app,
                ["init", str(tmp_path)],
                input="English\ndefault\n\n",
            )
        assert result.exit_code == 0, result.output

    def test_init_partial_select(self, tmp_path: Path):
        """Init with doc detection — user selects specific files in checkbox."""
        candidates = ["README.md", "docs/architecture.md", "CHANGELOG.md", "CONTRIBUTING.md"]
        with (
            patch("ctxforge.console.commands.init.detect_ai_clis", return_value=["claude"]),
            patch(
                "ctxforge.console.commands.init.detect_doc_candidates",
                return_value=candidates,
            ),
            patch(
                "ctxforge.console.commands.init._select_key_files",
                return_value=["README.md", "pyproject.toml"],
            ),
        ):
            # language → (checkbox mocked) → profile name → description
            result = runner.invoke(
                app,
                ["init", str(tmp_path)],
                input="English\ndefault\n\n",
            )
        assert result.exit_code == 0, result.output

    def test_reinit_skip_profile(self, ctxforge_project: Path):
        """Re-init with existing profiles, user declines creating new one."""
        with patch("ctxforge.console.commands.init.detect_ai_clis", return_value=["claude"]):
            # language → decline new profile
            result = runner.invoke(
                app,
                ["init", str(ctxforge_project)],
                input="English\nn\n",
            )
        assert result.exit_code == 0, result.output
        assert "Existing profiles" in result.output
        assert "Updated" in result.output

    def test_reinit_create_new_profile(self, ctxforge_project: Path):
        """Re-init with existing profiles, user creates a new one."""
        with (
            patch("ctxforge.console.commands.init.detect_ai_clis", return_value=["claude"]),
            patch("ctxforge.console.commands.init.detect_doc_candidates", return_value=[]),
        ):
            # language → accept new profile → key files prompt → name → desc
            result = runner.invoke(
                app,
                ["init", str(ctxforge_project)],
                input="English\ny\n\nreviewer\nCode review\n",
            )
        assert result.exit_code == 0, result.output
        assert (
            ctxforge_project / ".ctxforge" / "profiles" / "reviewer" / "profile.toml"
        ).exists()


class TestRunCommand:
    def test_run_default_profile(self, ctxforge_project: Path, monkeypatch):
        monkeypatch.chdir(ctxforge_project)
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("ctxforge.runner.claude.subprocess.run", return_value=mock_result) as mock_run:
            result = runner.invoke(app, ["run"])
        assert result.exit_code == 0, result.output
        # Should call claude with --append-system-prompt
        call_args = mock_run.call_args[0][0]
        assert call_args[0] == "claude"

    def test_run_named_profile(self, ctxforge_project: Path, monkeypatch):
        monkeypatch.chdir(ctxforge_project)
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("ctxforge.runner.claude.subprocess.run", return_value=mock_result):
            result = runner.invoke(app, ["run", "default"])
        assert result.exit_code == 0, result.output


class TestProfileCommands:
    def test_profile_list(self, ctxforge_project: Path, monkeypatch):
        monkeypatch.chdir(ctxforge_project)
        result = runner.invoke(app, ["profile", "list"])
        assert result.exit_code == 0, result.output
        assert "default" in result.output

    def test_profile_show(self, ctxforge_project: Path, monkeypatch):
        monkeypatch.chdir(ctxforge_project)
        result = runner.invoke(app, ["profile", "show", "default"])
        assert result.exit_code == 0, result.output
        assert "default" in result.output

    def test_profile_create(self, ctxforge_project: Path, monkeypatch):
        monkeypatch.chdir(ctxforge_project)
        result = runner.invoke(
            app, ["profile", "create", "reviewer", "--desc", "Review code"]
        )
        assert result.exit_code == 0, result.output
        assert "Created profile 'reviewer'" in result.output
        assert (
            ctxforge_project / ".ctxforge" / "profiles" / "reviewer" / "profile.toml"
        ).exists()

    def test_profile_create_duplicate(self, ctxforge_project: Path, monkeypatch):
        monkeypatch.chdir(ctxforge_project)
        result = runner.invoke(app, ["profile", "create", "default"])
        assert result.exit_code == 1


class TestCleanCommand:
    def test_clean_removes_ctxforge_dir(self, ctxforge_project: Path):
        result = runner.invoke(
            app, ["clean", str(ctxforge_project)], input="y\n"
        )
        assert result.exit_code == 0, result.output
        assert "Removed" in result.output
        assert not (ctxforge_project / ".ctxforge").exists()

    def test_clean_cancelled(self, ctxforge_project: Path):
        result = runner.invoke(
            app, ["clean", str(ctxforge_project)], input="n\n"
        )
        assert result.exit_code == 0, result.output
        assert "Cancelled" in result.output
        assert (ctxforge_project / ".ctxforge").exists()

    def test_clean_removes_slash_commands(self, ctxforge_project: Path):
        """Clean also removes .claude/commands/ctx-*.md files."""
        commands_dir = ctxforge_project / ".claude" / "commands"
        commands_dir.mkdir(parents=True)
        for name in ["ctx-profile.md", "ctx-files.md", "ctx-update.md", "ctx-compress.md"]:
            (commands_dir / name).write_text("test")
        # Also place a non-ctxforge command to ensure it survives
        (commands_dir / "other.md").write_text("keep")

        result = runner.invoke(
            app, ["clean", str(ctxforge_project)], input="y\n"
        )
        assert result.exit_code == 0, result.output
        assert "slash command" in result.output
        assert not (commands_dir / "ctx-profile.md").exists()
        assert (commands_dir / "other.md").exists()

    def test_clean_nothing_to_clean(self, tmp_path: Path):
        result = runner.invoke(app, ["clean", str(tmp_path)])
        assert result.exit_code == 0, result.output
        assert "Nothing to clean" in result.output


class TestVersionFlag:
    def test_version(self):
        result = runner.invoke(app, ["--version"])
        assert "1.0.0" in result.output
