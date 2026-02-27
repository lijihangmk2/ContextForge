"""Tests for ProfileManager."""

import pytest
from pathlib import Path

from ctxforge.core.profile import ProfileManager
from ctxforge.exceptions import ProfileNotFoundError


class TestProfileManager:
    def test_list_empty(self, tmp_path: Path):
        pm = ProfileManager(tmp_path / "profiles")
        assert pm.list_names() == []

    def test_create_and_list(self, tmp_path: Path):
        profiles_dir = tmp_path / "profiles"
        pm = ProfileManager(profiles_dir)
        pm.create(name="architect", description="Design role")
        assert pm.list_names() == ["architect"]

    def test_create_with_all_fields(self, tmp_path: Path):
        profiles_dir = tmp_path / "profiles"
        pm = ProfileManager(profiles_dir)
        config = pm.create(
            name="dev",
            description="Developer",
            role_prompt="Write clean code.",
            key_files=["src/main.py"],
        )
        assert config.profile.name == "dev"
        assert config.role.prompt == "Write clean code."
        assert config.key_files.paths == ["src/main.py"]

    def test_exists(self, tmp_path: Path):
        profiles_dir = tmp_path / "profiles"
        pm = ProfileManager(profiles_dir)
        pm.create(name="dev")
        assert pm.exists("dev")
        assert not pm.exists("nonexistent")

    def test_load(self, tmp_path: Path):
        profiles_dir = tmp_path / "profiles"
        pm = ProfileManager(profiles_dir)
        pm.create(name="reviewer", description="Code review")
        loaded = pm.load("reviewer")
        assert loaded.profile.name == "reviewer"
        assert loaded.profile.description == "Code review"

    def test_load_not_found(self, tmp_path: Path):
        pm = ProfileManager(tmp_path / "profiles")
        with pytest.raises(ProfileNotFoundError):
            pm.load("nonexistent")

    def test_resolve_explicit(self, tmp_path: Path):
        profiles_dir = tmp_path / "profiles"
        pm = ProfileManager(profiles_dir)
        pm.create(name="architect")
        assert pm.resolve("architect", None) == "architect"

    def test_resolve_default(self, tmp_path: Path):
        profiles_dir = tmp_path / "profiles"
        pm = ProfileManager(profiles_dir)
        pm.create(name="default")
        assert pm.resolve(None, "default") == "default"

    def test_resolve_single_profile(self, tmp_path: Path):
        profiles_dir = tmp_path / "profiles"
        pm = ProfileManager(profiles_dir)
        pm.create(name="only-one")
        assert pm.resolve(None, None) == "only-one"

    def test_resolve_no_profile_error(self, tmp_path: Path):
        pm = ProfileManager(tmp_path / "profiles")
        with pytest.raises(ProfileNotFoundError):
            pm.resolve(None, None)
