"""Tests for project_writer."""

import tomllib
from pathlib import Path

from ctxforge.spec.schema import CliConfig, DefaultsConfig, ProjectConfig, ProjectSection
from ctxforge.storage.project_writer import write_project


class TestWriteProject:
    def test_write_and_read_back(self, tmp_path: Path):
        path = tmp_path / "project.toml"
        config = ProjectConfig(
            project=ProjectSection(name="my-app"),
            cli=CliConfig(detected=["claude"], active="claude"),
            defaults=DefaultsConfig(profile="default"),
        )
        write_project(path, config)
        assert path.exists()

        with open(path, "rb") as f:
            data = tomllib.load(f)
        assert data["project"]["name"] == "my-app"
        assert data["cli"]["active"] == "claude"

    def test_creates_parent_dirs(self, tmp_path: Path):
        path = tmp_path / "deep" / "nested" / "project.toml"
        config = ProjectConfig(project=ProjectSection(name="test"))
        write_project(path, config)
        assert path.exists()

    def test_empty_fields_omitted(self, tmp_path: Path):
        path = tmp_path / "project.toml"
        config = ProjectConfig()
        write_project(path, config)

        with open(path, "rb") as f:
            data = tomllib.load(f)
        # Empty project name should be omitted, and cli with empty lists too
        assert "cli" not in data or "detected" not in data.get("cli", {})
