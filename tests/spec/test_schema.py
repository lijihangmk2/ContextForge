"""Tests for ctxforge schema models."""

import pytest
from pydantic import ValidationError

from ctxforge.spec.schema import (
    BudgetSection,
    CliConfig,
    DefaultsConfig,
    EnhancersSection,
    InjectionSection,
    KeyFilesSection,
    ProfileConfig,
    ProfileSection,
    ProjectConfig,
    ProjectSection,
    RoleSection,
)


class TestProjectConfig:
    def test_defaults(self):
        config = ProjectConfig()
        assert config.project.name == ""
        assert config.project.description == ""
        assert config.cli.detected == []
        assert config.cli.active is None
        assert config.defaults.profile is None

    def test_full(self):
        config = ProjectConfig(
            project=ProjectSection(name="my-app", description="A test app"),
            cli=CliConfig(detected=["claude", "codex"], active="claude"),
            defaults=DefaultsConfig(profile="architect"),
        )
        assert config.project.name == "my-app"
        assert config.cli.active == "claude"
        assert config.defaults.profile == "architect"

    def test_from_dict(self):
        data = {
            "project": {"name": "test", "description": "desc"},
            "cli": {"detected": ["claude"], "active": "claude"},
            "defaults": {"profile": "default"},
        }
        config = ProjectConfig.model_validate(data)
        assert config.project.name == "test"
        assert config.cli.active == "claude"

    def test_json_schema_export(self):
        schema = ProjectConfig.model_json_schema()
        assert "properties" in schema


class TestProfileConfig:
    def test_minimal(self):
        config = ProfileConfig(profile=ProfileSection(name="dev"))
        assert config.profile.name == "dev"
        assert config.role.prompt == ""
        assert config.key_files.paths == []
        assert config.injection.strategy == "simple"
        assert config.injection.order == "role_first"
        assert config.budget.max_tokens == 24000
        assert config.enhancers.enabled == []

    def test_full(self):
        config = ProfileConfig(
            profile=ProfileSection(name="architect", description="System design"),
            role=RoleSection(prompt="You are a software architect."),
            key_files=KeyFilesSection(paths=["src/main.py", "README.md"]),
            injection=InjectionSection(strategy="simple", order="files_first"),
            budget=BudgetSection(max_tokens=16000),
            enhancers=EnhancersSection(enabled=["tree"]),
        )
        assert config.profile.name == "architect"
        assert config.role.prompt == "You are a software architect."
        assert len(config.key_files.paths) == 2
        assert config.injection.order == "files_first"

    def test_name_required(self):
        with pytest.raises(ValidationError):
            ProfileConfig(profile=ProfileSection())  # type: ignore[call-arg]

    def test_from_dict(self):
        data = {
            "profile": {"name": "reviewer", "description": "Code review"},
            "role": {"prompt": "Review code carefully."},
            "key_files": {"paths": ["src/api.py"]},
        }
        config = ProfileConfig.model_validate(data)
        assert config.profile.name == "reviewer"
        assert config.key_files.paths == ["src/api.py"]

    def test_json_schema_export(self):
        schema = ProfileConfig.model_json_schema()
        assert "properties" in schema

    def test_default_injection(self):
        config = ProfileConfig(profile=ProfileSection(name="x"))
        assert config.injection.strategy == "simple"
        assert config.injection.order == "role_first"

    def test_default_budget(self):
        config = ProfileConfig(profile=ProfileSection(name="x"))
        assert config.budget.max_tokens == 24000

    def test_default_enhancers(self):
        config = ProfileConfig(profile=ProfileSection(name="x"))
        assert config.enhancers.enabled == []
