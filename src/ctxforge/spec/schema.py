"""Pydantic models for ctxforge configuration files."""

from __future__ import annotations

from pydantic import BaseModel, Field

# ─── Schema versioning ─────────────────────────────────────────────────────

CURRENT_PROFILE_VERSION = 7
CURRENT_PROJECT_VERSION = 2

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


class ToolDefinition(BaseModel):
    description: str = ""
    command: str
    args: list[str] = Field(default_factory=list)
    env: list[str] = Field(default_factory=list)
    setup: str = ""


class MempalaceSection(BaseModel):
    enabled: bool = False
    palace_path: str = ""
    autoload: bool = True
    checkpoint_interval: int = 1
    save_on_precompact: bool = True


class ProjectConfig(BaseModel):
    schema_version: int = 1
    project: ProjectSection = Field(default_factory=ProjectSection)
    cli: CliConfig = Field(default_factory=CliConfig)
    defaults: DefaultsConfig = Field(default_factory=DefaultsConfig)
    tools: dict[str, ToolDefinition] = Field(default_factory=dict)
    mempalace: MempalaceSection = Field(default_factory=MempalaceSection)


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


DEFAULT_WORK_RECORD: dict[str, str] = {
    "journal.md": "work journal — completed tasks, in-progress, TODOs",
    "pitfalls.md": "pitfalls — gotchas, lessons learned, warnings",
    "usermemo.md": "user memo — persistent notes and instructions from the user",
}


class WorkRecordSection(BaseModel):
    files: dict[str, str] = Field(default_factory=lambda: dict(DEFAULT_WORK_RECORD))


class EnhancersSection(BaseModel):
    enabled: list[str] = Field(default_factory=list)


class ToolsSection(BaseModel):
    disabled: list[str] = Field(default_factory=list)


class MemorySection(BaseModel):
    provider: str = "mempalace"
    enabled: bool = False
    scope: str = "profile"
    namespace: str = ""
    palace_path: str = ""
    autoload: bool = True
    save_on_checkpoint: bool = True
    checkpoint_interval: int = 15
    save_on_precompact: bool = True
    save_on_exit: bool = False
    cross_profile_search: bool = False


class ProfileConfig(BaseModel):
    schema_version: int = 1
    profile: ProfileSection
    role: RoleSection = Field(default_factory=RoleSection)
    work_record: WorkRecordSection = Field(default_factory=WorkRecordSection)
    key_files: KeyFilesSection = Field(default_factory=KeyFilesSection)
    injection: InjectionSection = Field(default_factory=InjectionSection)
    cli: ProfileCliSection = Field(default_factory=ProfileCliSection)
    budget: BudgetSection = Field(default_factory=BudgetSection)
    enhancers: EnhancersSection = Field(default_factory=EnhancersSection)
    tools: ToolsSection = Field(default_factory=ToolsSection)
    memory: MemorySection = Field(default_factory=MemorySection)
