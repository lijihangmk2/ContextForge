"""Profile manager — CRUD operations on profile directories."""

from __future__ import annotations

from pathlib import Path

from ctxforge.exceptions import ProfileNotFoundError
from ctxforge.spec.loader import load_profile
from ctxforge.spec.schema import ProfileConfig, ProfileSection
from ctxforge.storage.profile_writer import write_profile


class ProfileManager:
    """Manage profiles stored under .ctxforge/profiles/."""

    def __init__(self, profiles_dir: Path) -> None:
        self._dir = profiles_dir

    def list_names(self) -> list[str]:
        """Return sorted list of profile names (directory names)."""
        if not self._dir.exists():
            return []
        return sorted(
            d.name
            for d in self._dir.iterdir()
            if d.is_dir() and (d / "profile.toml").exists()
        )

    def exists(self, name: str) -> bool:
        return (self._dir / name / "profile.toml").exists()

    def load(self, name: str) -> ProfileConfig:
        """Load a profile by name.

        Raises:
            ProfileNotFoundError: If profile directory or file doesn't exist.
        """
        profile_dir = self._dir / name
        if not profile_dir.exists():
            raise ProfileNotFoundError(f"Profile '{name}' not found")
        return load_profile(profile_dir / "profile.toml")

    def create(
        self,
        name: str,
        description: str = "",
        role_prompt: str = "",
        key_files: list[str] | None = None,
    ) -> ProfileConfig:
        """Create a new profile and write it to disk.

        Returns:
            The created ProfileConfig.
        """
        config = ProfileConfig(
            profile=ProfileSection(name=name, description=description),
        )
        if role_prompt:
            config.role.prompt = role_prompt
        if key_files:
            config.key_files.paths = key_files

        profile_path = self._dir / name / "profile.toml"
        write_profile(profile_path, config)
        return config

    def resolve(self, name: str | None, default: str | None) -> str:
        """Resolve a profile name: explicit > default > error.

        Raises:
            ProfileNotFoundError: If no profile can be resolved or profile doesn't exist.
        """
        resolved = name or default
        if not resolved:
            names = self.list_names()
            if len(names) == 1:
                resolved = names[0]
            else:
                raise ProfileNotFoundError(
                    "No profile specified and no default configured"
                )
        if not self.exists(resolved):
            raise ProfileNotFoundError(f"Profile '{resolved}' not found")
        return resolved
