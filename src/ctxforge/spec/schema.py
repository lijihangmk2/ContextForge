"""Pydantic models for ctxforge configuration files."""

from __future__ import annotations

from pydantic import BaseModel, Field

# ─── project.toml models ────────────────────────────────────────────────────


class ProjectSection(BaseModel):
    name: str = ""
    description: str = ""


class CliConfig(BaseModel):
    detected: list[str] = Field(default_factory=list)
    active: str | None = None


class DefaultsConfig(BaseModel):
    profile: str | None = None
    language: str | None = None  # output language preference, e.g. "中文", "English"
    model: str | None = None  # LLM model for project analysis, e.g. "gpt-4o-mini"


class ProjectConfig(BaseModel):
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


class EnhancersSection(BaseModel):
    enabled: list[str] = Field(default_factory=list)


class ProfileConfig(BaseModel):
    profile: ProfileSection
    role: RoleSection = Field(default_factory=RoleSection)
    key_files: KeyFilesSection = Field(default_factory=KeyFilesSection)
    injection: InjectionSection = Field(default_factory=InjectionSection)
    budget: BudgetSection = Field(default_factory=BudgetSection)
    enhancers: EnhancersSection = Field(default_factory=EnhancersSection)
