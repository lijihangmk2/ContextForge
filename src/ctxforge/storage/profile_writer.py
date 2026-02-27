"""Write profile.toml to disk."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import tomli_w

from ctxforge.spec.schema import ProfileConfig


def write_profile(path: Path, config: ProfileConfig) -> None:
    """Write a ProfileConfig to a TOML file.

    Args:
        path: Target file path (e.g. .ctxforge/profiles/architect/profile.toml).
        config: Validated ProfileConfig instance.
    """
    data = _clean_empty(config.model_dump(exclude_none=True))
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        tomli_w.dump(data, f)


def _clean_empty(d: Any) -> Any:
    """Recursively remove empty dicts, empty lists, and None values."""
    if isinstance(d, dict):
        cleaned = {}
        for k, v in d.items():
            v = _clean_empty(v)
            if v is not None and v != {} and v != []:
                cleaned[k] = v
        return cleaned
    if isinstance(d, list):
        return [_clean_empty(item) for item in d if item is not None]
    return d
