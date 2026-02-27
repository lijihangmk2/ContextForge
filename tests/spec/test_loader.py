"""Tests for TOML loader."""

import pytest
from pathlib import Path

from ctxforge.spec.loader import load_project, load_profile
from ctxforge.exceptions import (
    ProjectNotFoundError,
    InvalidProjectError,
    ProfileNotFoundError,
    InvalidProfileError,
)


class TestLoadProject:
    def test_file_not_found(self, tmp_path: Path):
        with pytest.raises(ProjectNotFoundError):
            load_project(tmp_path / "nonexistent.toml")

    def test_load_from_directory(self, tmp_path: Path):
        content = b'[project]\nname = "test"\n'
        (tmp_path / "project.toml").write_bytes(content)
        config = load_project(tmp_path)
        assert config.project.name == "test"

    def test_load_from_file(self, tmp_path: Path):
        path = tmp_path / "project.toml"
        path.write_bytes(b'[project]\nname = "direct"\n')
        config = load_project(path)
        assert config.project.name == "direct"

    def test_empty_dict_uses_defaults(self, tmp_path: Path):
        path = tmp_path / "project.toml"
        path.write_bytes(b"")
        config = load_project(path)
        assert config.project.name == ""

    def test_with_cli_section(self, tmp_path: Path):
        content = b'[project]\nname = "app"\n\n[cli]\ndetected = ["claude"]\nactive = "claude"\n'
        (tmp_path / "project.toml").write_bytes(content)
        config = load_project(tmp_path)
        assert config.cli.active == "claude"

    def test_invalid_toml(self, tmp_path: Path):
        path = tmp_path / "project.toml"
        path.write_bytes(b"[invalid toml <<<")
        with pytest.raises(InvalidProjectError):
            load_project(path)


class TestLoadProfile:
    def test_file_not_found(self, tmp_path: Path):
        with pytest.raises(ProfileNotFoundError):
            load_profile(tmp_path / "nonexistent.toml")

    def test_load_profile(self, tmp_path: Path):
        content = b'[profile]\nname = "architect"\ndescription = "Design"\n\n[role]\nprompt = "You are an architect."\n'
        (tmp_path / "profile.toml").write_bytes(content)
        config = load_profile(tmp_path)
        assert config.profile.name == "architect"
        assert config.role.prompt == "You are an architect."

    def test_missing_profile_name(self, tmp_path: Path):
        content = b"[profile]\ndescription = 'no name'\n"
        (tmp_path / "profile.toml").write_bytes(content)
        with pytest.raises(InvalidProfileError):
            load_profile(tmp_path)

    def test_with_key_files(self, tmp_path: Path):
        content = b'[profile]\nname = "dev"\n\n[key_files]\npaths = ["src/main.py", "README.md"]\n'
        (tmp_path / "profile.toml").write_bytes(content)
        config = load_profile(tmp_path)
        assert config.key_files.paths == ["src/main.py", "README.md"]
