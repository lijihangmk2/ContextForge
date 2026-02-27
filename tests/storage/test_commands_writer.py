"""Tests for commands_writer."""

from pathlib import Path

from ctxforge.storage.commands_writer import write_commands


class TestWriteCommands:
    def test_creates_commands_dir(self, tmp_path: Path) -> None:
        write_commands(tmp_path, "architect", "claude")
        assert (tmp_path / ".claude" / "commands").is_dir()

    def test_generates_four_files(self, tmp_path: Path) -> None:
        write_commands(tmp_path, "architect", "claude")
        commands_dir = tmp_path / ".claude" / "commands"
        assert (commands_dir / "ctx-profile.md").is_file()
        assert (commands_dir / "ctx-files.md").is_file()
        assert (commands_dir / "ctx-update.md").is_file()
        assert (commands_dir / "ctx-compress.md").is_file()

    def test_profile_path_embedded(self, tmp_path: Path) -> None:
        write_commands(tmp_path, "reviewer", "claude")
        content = (tmp_path / ".claude" / "commands" / "ctx-profile.md").read_text()
        assert ".ctxforge/profiles/reviewer/profile.toml" in content

    def test_ctx_files_references_profile(self, tmp_path: Path) -> None:
        write_commands(tmp_path, "default", "claude")
        content = (tmp_path / ".claude" / "commands" / "ctx-files.md").read_text()
        assert ".ctxforge/profiles/default/profile.toml" in content

    def test_ctx_update_has_rules(self, tmp_path: Path) -> None:
        write_commands(tmp_path, "default", "claude")
        content = (tmp_path / ".claude" / "commands" / "ctx-update.md").read_text()
        assert "never directories" in content
        assert "$ARGUMENTS" in content

    def test_overwrites_existing(self, tmp_path: Path) -> None:
        write_commands(tmp_path, "old-profile", "claude")
        write_commands(tmp_path, "new-profile", "claude")
        content = (tmp_path / ".claude" / "commands" / "ctx-profile.md").read_text()
        assert "new-profile" in content
        assert "old-profile" not in content

    def test_ctx_compress_has_guidelines(self, tmp_path: Path) -> None:
        write_commands(tmp_path, "default", "claude")
        content = (tmp_path / ".claude" / "commands" / "ctx-compress.md").read_text()
        assert "compress" in content.lower()
        assert "user_notes" in content
        assert "$ARGUMENTS" in content

    def test_idempotent(self, tmp_path: Path) -> None:
        write_commands(tmp_path, "architect", "claude")
        content1 = (tmp_path / ".claude" / "commands" / "ctx-profile.md").read_text()
        write_commands(tmp_path, "architect", "claude")
        content2 = (tmp_path / ".claude" / "commands" / "ctx-profile.md").read_text()
        assert content1 == content2

    def test_skipped_for_codex(self, tmp_path: Path) -> None:
        write_commands(tmp_path, "default", "codex")
        assert not (tmp_path / ".claude" / "commands").exists()

    def test_skipped_for_unknown_cli(self, tmp_path: Path) -> None:
        write_commands(tmp_path, "default", "aider")
        assert not (tmp_path / ".claude" / "commands").exists()
