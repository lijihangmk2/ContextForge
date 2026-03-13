"""Tests for ProfileManager."""

import pytest
from pathlib import Path

from ctxforge.core.profile import ProfileManager
from ctxforge.exceptions import CForgeError, ProfileNotFoundError


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
        assert pm.resolve("architect") == "architect"

    def test_resolve_single_profile(self, tmp_path: Path):
        profiles_dir = tmp_path / "profiles"
        pm = ProfileManager(profiles_dir)
        pm.create(name="only-one")
        assert pm.resolve(None) == "only-one"

    def test_resolve_multiple_profiles_error(self, tmp_path: Path):
        profiles_dir = tmp_path / "profiles"
        pm = ProfileManager(profiles_dir)
        pm.create(name="a")
        pm.create(name="b")
        with pytest.raises(ProfileNotFoundError):
            pm.resolve(None)

    def test_resolve_no_profile_error(self, tmp_path: Path):
        pm = ProfileManager(tmp_path / "profiles")
        with pytest.raises(ProfileNotFoundError):
            pm.resolve(None)

    def test_edit_description(self, tmp_path: Path):
        pm = ProfileManager(tmp_path / "profiles")
        pm.create(name="dev", description="old desc")
        config = pm.edit("dev", description="new desc")
        assert config.profile.description == "new desc"
        reloaded = pm.load("dev")
        assert reloaded.profile.description == "new desc"

    def test_edit_role_prompt(self, tmp_path: Path):
        pm = ProfileManager(tmp_path / "profiles")
        pm.create(name="dev", role_prompt="old prompt")
        config = pm.edit("dev", role_prompt="new prompt")
        assert config.role.prompt == "new prompt"

    def test_edit_rename(self, tmp_path: Path):
        pm = ProfileManager(tmp_path / "profiles")
        pm.create(name="old-name", description="test")
        config = pm.edit("old-name", new_name="new-name")
        assert config.profile.name == "new-name"
        assert pm.exists("new-name")
        assert not pm.exists("old-name")

    def test_edit_rename_conflict(self, tmp_path: Path):
        pm = ProfileManager(tmp_path / "profiles")
        pm.create(name="a")
        pm.create(name="b")
        with pytest.raises(CForgeError):
            pm.edit("a", new_name="b")

    def test_edit_cli_settings(self, tmp_path: Path):
        pm = ProfileManager(tmp_path / "profiles")
        pm.create(name="dev", cli_name="claude", auto_approve=False)
        config = pm.edit("dev", cli_name="codex", auto_approve=True)
        assert config.cli.name == "codex"
        assert config.cli.auto_approve is True

    def test_edit_not_found(self, tmp_path: Path):
        pm = ProfileManager(tmp_path / "profiles")
        with pytest.raises(ProfileNotFoundError):
            pm.edit("nonexistent", description="test")
