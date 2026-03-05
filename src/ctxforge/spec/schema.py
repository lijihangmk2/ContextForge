"""Pydantic models for ctxforge configuration files."""

from __future__ import annotations

from pydantic import BaseModel, Field

# ─── Schema versioning ─────────────────────────────────────────────────────

CURRENT_PROFILE_VERSION = 2
CURRENT_PROJECT_VERSION = 1  # project.toml has not changed yet

# ─── project.toml models ────────────────────────────────────────────────────


class ProjectSection(BaseModel):
    name: str = ""
    description: str = ""


class CliConfig(BaseModel):
    detected: list[str] = Field(default_factory=list)
    active: str | None = None  # legacy — now per-profile; kept for migration


class DefaultsConfig(BaseModel):
    language: str | None = None  # output language preference, e.g. "中文", "English"
    model: str | None = None  # LLM model for project analysis, e.g. "gpt-4o-mini"


class ProjectConfig(BaseModel):
    schema_version: int = 1
    project: ProjectSection = Field(default_factory=ProjectSection)
    cli: CliConfig = Field(default_factory=CliConfig)
    defaults: DefaultsConfig = Field(default_factory=DefaultsConfig)


# ─── profile.toml models ────────────────────────────────────────────────────


class ProfileSection(BaseModel):
    name: str
    description: str = ""


class RoleSection(BaseModel):
    prompt: str = ""


class KeyFilesSection(BaseModel):
    paths: list[str] = Field(default_factory=list)


class InjectionSection(BaseModel):
    strategy: str = "simple"
    order: str = "role_first"  # "role_first" | "files_first"
    greeting: bool = True  # ask AI to confirm context on session start


class BudgetSection(BaseModel):
    max_tokens: int = 24000


class ProfileCliSection(BaseModel):
    name: str | None = None  # CLI to use: "claude" | "codex"
    auto_approve: bool = False  # skip permission prompts


class EnhancersSection(BaseModel):
    enabled: list[str] = Field(default_factory=list)


class ProfileConfig(BaseModel):
    schema_version: int = 1
    profile: ProfileSection
    role: RoleSection = Field(default_factory=RoleSection)
    key_files: KeyFilesSection = Field(default_factory=KeyFilesSection)
    injection: InjectionSection = Field(default_factory=InjectionSection)
    cli: ProfileCliSection = Field(default_factory=ProfileCliSection)
    budget: BudgetSection = Field(default_factory=BudgetSection)
    enhancers: EnhancersSection = Field(default_factory=EnhancersSection)
