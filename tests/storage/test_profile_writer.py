"""Tests for profile_writer."""

import tomllib
from pathlib import Path

from ctxforge.spec.schema import (
    KeyFilesSection,
    ProfileConfig,
    ProfileSection,
    RoleSection,
)
from ctxforge.storage.profile_writer import write_profile


class TestWriteProfile:
    def test_write_and_read_back(self, tmp_path: Path):
        path = tmp_path / "profile.toml"
        config = ProfileConfig(
            profile=ProfileSection(name="architect", description="Design"),
            role=RoleSection(prompt="You are an architect."),
        )
        write_profile(path, config)
        assert path.exists()

        with open(path, "rb") as f:
            data = tomllib.load(f)
        assert data["profile"]["name"] == "architect"
        assert data["role"]["prompt"] == "You are an architect."

    def test_creates_parent_dirs(self, tmp_path: Path):
        path = tmp_path / "profiles" / "dev" / "profile.toml"
        config = ProfileConfig(profile=ProfileSection(name="dev"))
        write_profile(path, config)
        assert path.exists()

    def test_with_key_files(self, tmp_path: Path):
        path = tmp_path / "profile.toml"
        config = ProfileConfig(
            profile=ProfileSection(name="dev"),
            key_files=KeyFilesSection(paths=["src/main.py", "README.md"]),
        )
        write_profile(path, config)

        with open(path, "rb") as f:
            data = tomllib.load(f)
        assert data["key_files"]["paths"] == ["src/main.py", "README.md"]

    def test_empty_optional_fields_omitted(self, tmp_path: Path):
        path = tmp_path / "profile.toml"
        config = ProfileConfig(profile=ProfileSection(name="minimal"))
        write_profile(path, config)

        with open(path, "rb") as f:
            data = tomllib.load(f)
        assert data["profile"]["name"] == "minimal"
        assert "enhancers" not in data  # empty list omitted
