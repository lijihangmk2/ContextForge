"""Tests for schema migration."""

import sys

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib
from pathlib import Path

from ctxforge.core.migration import migrate_profile, needs_migration
from ctxforge.spec.schema import (
    CURRENT_PROFILE_VERSION,
    CliConfig,
    DefaultsConfig,
    ProfileConfig,
    ProfileSection,
    ProjectConfig,
    ProjectSection,
    RoleSection,
)
from ctxforge.storage.profile_writer import write_profile


def _make_v1_profile(path: Path) -> ProfileConfig:
    """Create a v1 profile (no cli section, schema_version=1)."""
    config = ProfileConfig(
        schema_version=1,
        profile=ProfileSection(name="legacy", description="Old profile"),
        role=RoleSection(prompt="You are helpful."),
    )
    write_profile(path, config)
    return config


def _make_project_config() -> ProjectConfig:
    return ProjectConfig(
        project=ProjectSection(name="test"),
        cli=CliConfig(detected=["claude", "codex"], active="claude"),
        defaults=DefaultsConfig(language="English"),
    )


class TestNeedsMigration:
    def test_v1_needs_migration(self):
        config = ProfileConfig(
            schema_version=1,
            profile=ProfileSection(name="test"),
        )
        assert needs_migration(config)

    def test_current_no_migration(self):
        config = ProfileConfig(
            schema_version=CURRENT_PROFILE_VERSION,
            profile=ProfileSection(name="test"),
        )
        assert not needs_migration(config)


class TestMigrateProfile:
    def test_v1_to_v2_non_interactive(self, tmp_path: Path):
        """Non-interactive migration uses project's cli.active as default."""
        profile_path = tmp_path / "profile.toml"
        config = _make_v1_profile(profile_path)
        project_config = _make_project_config()

        result = migrate_profile(config, project_config, profile_path)

        assert result.schema_version == CURRENT_PROFILE_VERSION
        assert result.cli.name == "claude"
        assert result.cli.auto_approve is False
        # Verify written to disk
        with open(profile_path, "rb") as f:
            data = tomllib.load(f)
        assert data["schema_version"] == CURRENT_PROFILE_VERSION
        assert data["cli"]["name"] == "claude"

    def test_v1_to_v2_preserves_existing_fields(self, tmp_path: Path):
        """Migration preserves role, key_files, etc."""
        profile_path = tmp_path / "profile.toml"
        config = _make_v1_profile(profile_path)
        project_config = _make_project_config()

        result = migrate_profile(config, project_config, profile_path)

        assert result.profile.name == "legacy"
        assert result.role.prompt == "You are helpful."

    def test_already_current_is_noop(self, tmp_path: Path):
        """Migrating an already-current profile is a no-op."""
        from ctxforge.spec.schema import ProfileCliSection

        profile_path = tmp_path / "profile.toml"
        config = ProfileConfig(
            schema_version=CURRENT_PROFILE_VERSION,
            profile=ProfileSection(name="current"),
            cli=ProfileCliSection(name="codex", auto_approve=True),
        )
        write_profile(profile_path, config)
        project_config = _make_project_config()

        result = migrate_profile(config, project_config, profile_path)

        assert result.cli.name == "codex"
        assert result.cli.auto_approve is True

    def test_v1_no_active_cli(self, tmp_path: Path):
        """Migration with no project cli.active sets cli.name to None."""
        profile_path = tmp_path / "profile.toml"
        config = _make_v1_profile(profile_path)
        project_config = ProjectConfig(
            project=ProjectSection(name="test"),
            cli=CliConfig(detected=[]),
            defaults=DefaultsConfig(),
        )

        result = migrate_profile(config, project_config, profile_path)

        assert result.schema_version == CURRENT_PROFILE_VERSION
        assert result.cli.name is None
        assert result.cli.auto_approve is False
