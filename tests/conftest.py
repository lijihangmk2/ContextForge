"""Shared test fixtures."""

import pytest
from pathlib import Path

from ctxforge.spec.schema import (
    CURRENT_PROFILE_VERSION,
    CliConfig,
    DefaultsConfig,
    ProfileCliSection,
    ProfileConfig,
    ProfileSection,
    ProjectConfig,
    ProjectSection,
    RoleSection,
    KeyFilesSection,
)
from ctxforge.storage.project_writer import write_project
from ctxforge.storage.profile_writer import write_profile


@pytest.fixture
def ctxforge_project(tmp_path: Path) -> Path:
    """Create a minimal .ctxforge/ project structure and return project root."""
    ctxforge_dir = tmp_path / ".ctxforge"
    ctxforge_dir.mkdir()

    # project.toml
    project_config = ProjectConfig(
        project=ProjectSection(name="test-project"),
        cli=CliConfig(detected=["claude"]),
        defaults=DefaultsConfig(),
    )
    write_project(ctxforge_dir / "project.toml", project_config)

    # default profile
    profile_config = ProfileConfig(
        schema_version=CURRENT_PROFILE_VERSION,
        profile=ProfileSection(name="default", description="Default profile"),
        role=RoleSection(prompt="You are a helpful assistant."),
        key_files=KeyFilesSection(paths=[]),
        cli=ProfileCliSection(name="claude"),
    )
    profile_dir = ctxforge_dir / "profiles" / "default"
    profile_dir.mkdir(parents=True)
    write_profile(profile_dir / "profile.toml", profile_config)

    return tmp_path
