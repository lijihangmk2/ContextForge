"""Load and validate ctxforge TOML configuration files."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any, TypeVar

from pydantic import ValidationError

from ctxforge.exceptions import (
    InvalidProfileError,
    InvalidProjectError,
    ProfileNotFoundError,
    ProjectNotFoundError,
)
from ctxforge.spec.schema import ProfileConfig, ProjectConfig


def load_project(path: Path) -> ProjectConfig:
    """Load and validate a project.toml file.

    Args:
        path: Path to project.toml or to the .ctxforge/ directory.

    Raises:
        ProjectNotFoundError: If the file doesn't exist.
        InvalidProjectError: If the file is malformed.
    """
    if path.is_dir():
        path = path / "project.toml"

    if not path.exists():
        raise ProjectNotFoundError(f"project.toml not found at {path}")

    data = _load_toml(path, InvalidProjectError)
    return _validate(data, ProjectConfig, InvalidProjectError, "project.toml")


def load_profile(path: Path) -> ProfileConfig:
    """Load and validate a profile.toml file.

    Args:
        path: Path to profile.toml or to a profile directory.

    Raises:
        ProfileNotFoundError: If the file doesn't exist.
        InvalidProfileError: If the file is malformed.
    """
    if path.is_dir():
        path = path / "profile.toml"

    if not path.exists():
        raise ProfileNotFoundError(f"profile.toml not found at {path}")

    data = _load_toml(path, InvalidProfileError)
    return _validate(data, ProfileConfig, InvalidProfileError, "profile.toml")


def _load_toml(path: Path, error_cls: type[Exception]) -> dict[str, Any]:
    """Read and parse a TOML file."""
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except Exception as e:
        raise error_cls(f"Failed to parse {path}: {e}") from e


_T = TypeVar("_T")


def _validate(
    data: dict[str, Any],
    model: type[_T],
    error_cls: type[Exception],
    label: str,
) -> _T:
    """Validate a dict against a Pydantic model."""
    try:
        return model.model_validate(data)  # type: ignore[attr-defined,no-any-return]
    except ValidationError as e:
        raise error_cls(f"Invalid {label}: {e}") from e
