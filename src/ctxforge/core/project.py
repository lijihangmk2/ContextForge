"""Project — locate and load .ctxforge/ configuration."""

from __future__ import annotations

from pathlib import Path

from ctxforge.exceptions import ProjectNotFoundError
from ctxforge.spec.loader import load_project
from ctxforge.spec.schema import ProjectConfig

CTXFORGE_DIR = ".ctxforge"
PROJECT_TOML = "project.toml"


class Project:
    """Represents a ctxforge-managed project."""

    def __init__(self, root: Path, config: ProjectConfig) -> None:
        self.root = root
        self.config = config

    @property
    def ctxforge_dir(self) -> Path:
        return self.root / CTXFORGE_DIR

    @property
    def profiles_dir(self) -> Path:
        return self.ctxforge_dir / "profiles"

    @classmethod
    def load(cls, start: Path | None = None) -> Project:
        """Find .ctxforge/ by walking up from *start* and load project.toml.

        Raises:
            ProjectNotFoundError: If no .ctxforge/ directory is found.
        """
        root = find_project_root(start or Path.cwd())
        config = load_project(root / CTXFORGE_DIR / PROJECT_TOML)
        return cls(root, config)


def find_project_root(start: Path) -> Path:
    """Walk up from *start* looking for a directory containing .ctxforge/.

    Raises:
        ProjectNotFoundError: If .ctxforge/ is not found up to filesystem root.
    """
    current = start.resolve()
    while True:
        if (current / CTXFORGE_DIR).is_dir():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    raise ProjectNotFoundError(
        f"No {CTXFORGE_DIR}/ found from {start} to filesystem root"
    )
