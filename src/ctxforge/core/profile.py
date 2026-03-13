"""Profile manager — CRUD operations on profile directories."""

from __future__ import annotations

from pathlib import Path

from ctxforge.exceptions import ProfileNotFoundError
from ctxforge.spec.loader import load_profile
from ctxforge.spec.schema import (
    CURRENT_PROFILE_VERSION,
    ProfileCliSection,
    ProfileConfig,
    ProfileSection,
)
from ctxforge.storage.profile_writer import write_profile


class ProfileManager:
    """Manage profiles stored under .ctxforge/profiles/."""

    def __init__(self, profiles_dir: Path) -> None:
        self._dir = profiles_dir

    @property
    def profiles_dir(self) -> Path:
        return self._dir

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

    def profile_path(self, name: str) -> Path:
        """Return the path to a profile's profile.toml."""
        return self._dir / name / "profile.toml"

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
        cli_name: str | None = None,
        auto_approve: bool = False,
    ) -> ProfileConfig:
        """Create a new profile and write it to disk.

        Returns:
            The created ProfileConfig.
        """
        config = ProfileConfig(
            schema_version=CURRENT_PROFILE_VERSION,
            profile=ProfileSection(name=name, description=description),
        )
        if role_prompt:
            config.role.prompt = role_prompt
        if key_files:
            config.key_files.paths = key_files
        if cli_name or auto_approve:
            config.cli = ProfileCliSection(
                name=cli_name, auto_approve=auto_approve,
            )

        profile_path = self._dir / name / "profile.toml"
        write_profile(profile_path, config)
        return config

    def edit(
        self,
        name: str,
        *,
        new_name: str | None = None,
        description: str | None = None,
        role_prompt: str | None = None,
        cli_name: str | None = None,
        auto_approve: bool | None = None,
    ) -> ProfileConfig:
        """Edit an existing profile's settings.

        Args:
            name: Current profile name.
            new_name: Rename the profile (directory + config).
            description: New description (empty string to clear).
            role_prompt: New role prompt (empty string to clear).
            cli_name: CLI to use for this profile.
            auto_approve: Whether to skip permission prompts.

        Returns:
            The updated ProfileConfig.

        Raises:
            ProfileNotFoundError: If the profile doesn't exist.
            CForgeError: If the new name conflicts with an existing profile.
        """
        from ctxforge.exceptions import CForgeError

        if not self.exists(name):
            raise ProfileNotFoundError(f"Profile '{name}' not found")

        if new_name and new_name != name and self.exists(new_name):
            raise CForgeError(f"Profile '{new_name}' already exists")

        config = self.load(name)

        if description is not None:
            config.profile.description = description
        if role_prompt is not None:
            config.role.prompt = role_prompt
        if cli_name is not None:
            config.cli.name = cli_name
        if auto_approve is not None:
            config.cli.auto_approve = auto_approve

        target_name = new_name if new_name else name
        config.profile.name = target_name

        if new_name and new_name != name:
            old_dir = self._dir / name
            new_dir = self._dir / new_name
            old_dir.rename(new_dir)
            write_profile(new_dir / "profile.toml", config)
        else:
            write_profile(self._dir / name / "profile.toml", config)

        return config

    def resolve(self, name: str | None) -> str:
        """Resolve a profile name: explicit > single-profile auto > error.

        Raises:
            ProfileNotFoundError: If no profile can be resolved or profile doesn't exist.
        """
        if name:
            if not self.exists(name):
                raise ProfileNotFoundError(f"Profile '{name}' not found")
            return name
        names = self.list_names()
        if len(names) == 1:
            return names[0]
        raise ProfileNotFoundError(
            "Multiple profiles found — please specify one"
        )
