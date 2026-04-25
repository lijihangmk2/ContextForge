"""System-level credential management for supported AI CLIs."""

from __future__ import annotations

import json
import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

from ctxforge.exceptions import CredentialError

CTXFORGE_HOME_ENV = "CTXFORGE_HOME"
MANIFEST_VERSION = 1
NAME_RE = re.compile(r"^[^/\\\\]+$")


@dataclass(frozen=True)
class CredentialSpec:
    """Tracked live credential files for one CLI."""

    cli_name: str
    tracked_files: tuple[str, ...]


@dataclass(frozen=True)
class ManagedCredential:
    """One stored credential snapshot."""

    cli_name: str
    name: str
    created_at: str
    updated_at: str
    file_count: int
    account_hint: str
    current: bool = False
    selected: bool = False


SPECS: dict[str, CredentialSpec] = {
    "claude": CredentialSpec(
        cli_name="claude",
        tracked_files=(
            ".claude/.credentials.json",
            ".claude.json",
        ),
    ),
    "codex": CredentialSpec(
        cli_name="codex",
        tracked_files=(
            ".codex/auth.json",
        ),
    ),
}


def get_ctxforge_home() -> Path:
    """Return the system-level ctxforge home directory."""
    configured = os.environ.get(CTXFORGE_HOME_ENV, "").strip()
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".ctxforge"


class CredentialsManager:
    """Manage multiple system-level credential snapshots."""

    def __init__(self, root: Path | None = None) -> None:
        base = root if root is not None else get_ctxforge_home() / "credentials"
        self.root = base
        self.manifest_path = self.root / "manifest.json"

    def ensure_store(self) -> None:
        """Create the credentials store if missing."""
        self.root.mkdir(parents=True, exist_ok=True)
        if not self.manifest_path.exists():
            self._write_manifest(self._default_manifest())

    def supported_clis(self) -> list[str]:
        """Return supported CLI names."""
        return list(SPECS)

    def has_managed_credentials(self, cli_name: str) -> bool:
        """Return whether the managed store already has credentials for one CLI."""
        self.ensure_store()
        manifest = self._load_manifest()
        return bool(self._cli_entries(manifest, cli_name))

    def has_live_credentials(self, cli_name: str) -> bool:
        """Return whether any tracked live credential file exists."""
        spec = self._get_spec(cli_name)
        return any(self._live_path(rel).exists() for rel in spec.tracked_files)

    def suggested_name(self, cli_name: str) -> str:
        """Return a stable default credential name derived from the live identity."""
        raw = self._extract_identity(cli_name).strip()
        if raw:
            return raw
        return f"{cli_name}-default"

    def capture(
        self,
        cli_name: str,
        name: str,
        *,
        overwrite: bool = False,
    ) -> ManagedCredential:
        """Capture the current live credentials into the managed store."""
        spec = self._get_spec(cli_name)
        self._validate_name(name)
        self.ensure_store()

        live_existing = [rel for rel in spec.tracked_files if self._live_path(rel).exists()]
        if not live_existing:
            raise CredentialError(f"No live {cli_name} credentials found to capture.")

        manifest = self._load_manifest()
        cli_entries = self._cli_entries(manifest, cli_name)
        already_exists = name in cli_entries
        if already_exists and not overwrite:
            raise CredentialError(f"Credential '{name}' already exists for {cli_name}.")

        snapshot_dir = self._snapshot_dir(cli_name, name)
        if snapshot_dir.exists():
            shutil.rmtree(snapshot_dir)
        snapshot_dir.mkdir(parents=True, exist_ok=True)

        stored_files: list[str] = []
        for rel in spec.tracked_files:
            live_path = self._live_path(rel)
            if not live_path.exists():
                continue
            target = snapshot_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(live_path, target)
            stored_files.append(rel)

        now = _utc_now()
        existing = cli_entries.get(name, {})
        cli_entries[name] = {
            "created_at": existing.get("created_at", now),
            "updated_at": now,
            "files": stored_files,
            "account_hint": self._extract_account_hint(cli_name),
        }
        self._write_manifest(manifest)
        return self.get(cli_name, name)

    def switch(self, cli_name: str, name: str) -> ManagedCredential:
        """Switch the live credential files to one managed snapshot."""
        self.ensure_store()
        manifest = self._load_manifest()
        cli_entries = self._cli_entries(manifest, cli_name)
        if name not in cli_entries:
            raise CredentialError(f"Credential '{name}' not found for {cli_name}.")

        spec = self._get_spec(cli_name)
        snapshot_dir = self._snapshot_dir(cli_name, name)
        for rel in spec.tracked_files:
            source = snapshot_dir / rel
            live = self._live_path(rel)
            if source.exists():
                live.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, live)
            elif live.exists():
                live.unlink()

        manifest.setdefault("active", {})[cli_name] = name
        cli_entries[name]["updated_at"] = _utc_now()
        self._write_manifest(manifest)
        return self.get(cli_name, name)

    def clear_live(self, cli_name: str) -> None:
        """Remove all tracked live credential files for one CLI."""
        spec = self._get_spec(cli_name)
        for rel in spec.tracked_files:
            path = self._live_path(rel)
            if path.exists():
                path.unlink()

    def remove(self, cli_name: str, name: str) -> None:
        """Remove one managed credential snapshot."""
        self.ensure_store()
        current = self.detect_current(cli_name)
        if current == name:
            raise CredentialError(
                f"Credential '{name}' is currently active for {cli_name}. Switch away first."
            )

        manifest = self._load_manifest()
        cli_entries = self._cli_entries(manifest, cli_name)
        if name not in cli_entries:
            raise CredentialError(f"Credential '{name}' not found for {cli_name}.")

        snapshot_dir = self._snapshot_dir(cli_name, name)
        if snapshot_dir.exists():
            shutil.rmtree(snapshot_dir)
        del cli_entries[name]

        active = manifest.setdefault("active", {})
        if active.get(cli_name) == name:
            active.pop(cli_name, None)
        self._write_manifest(manifest)

    def clean(self, cli_name: str | None = None) -> None:
        """Remove managed credential snapshots, but leave live auth files untouched."""
        self.ensure_store()

        if cli_name is None:
            if self.root.exists():
                shutil.rmtree(self.root)
            return

        manifest = self._load_manifest()
        self._get_spec(cli_name)
        snapshot_root = self.root / cli_name
        if snapshot_root.exists():
            shutil.rmtree(snapshot_root)

        credentials = manifest.setdefault("credentials", {})
        credentials[cli_name] = {}
        active = manifest.setdefault("active", {})
        active.pop(cli_name, None)
        self._write_manifest(manifest)

    def get(self, cli_name: str, name: str) -> ManagedCredential:
        """Return one managed credential."""
        current = self.detect_current(cli_name)
        manifest = self._load_manifest()
        cli_entries = self._cli_entries(manifest, cli_name)
        data = cli_entries.get(name)
        if data is None:
            raise CredentialError(f"Credential '{name}' not found for {cli_name}.")
        return ManagedCredential(
            cli_name=cli_name,
            name=name,
            created_at=str(data.get("created_at", "")),
            updated_at=str(data.get("updated_at", "")),
            file_count=len(data.get("files", [])),
            account_hint=str(data.get("account_hint", "")),
            current=current == name,
            selected=manifest.get("active", {}).get(cli_name) == name,
        )

    def list_credentials(self, cli_name: str | None = None) -> list[ManagedCredential]:
        """List managed credentials, optionally filtered by CLI."""
        self.ensure_store()
        manifest = self._load_manifest()
        cli_names = [cli_name] if cli_name else self.supported_clis()
        items: list[ManagedCredential] = []
        for current_cli in cli_names:
            current = self.detect_current(current_cli)
            active = manifest.get("active", {}).get(current_cli)
            for name, data in self._cli_entries(manifest, current_cli).items():
                items.append(
                    ManagedCredential(
                        cli_name=current_cli,
                        name=name,
                        created_at=str(data.get("created_at", "")),
                        updated_at=str(data.get("updated_at", "")),
                        file_count=len(data.get("files", [])),
                        account_hint=str(data.get("account_hint", "")),
                        current=current == name,
                        selected=active == name,
                    )
                )
        items.sort(key=lambda item: (item.cli_name, item.name))
        return items

    def detect_current(self, cli_name: str) -> str | None:
        """Detect which managed credential matches the current live files."""
        self.ensure_store()
        manifest = self._load_manifest()
        live_fingerprint = self._fingerprint_live(cli_name)
        for name in sorted(self._cli_entries(manifest, cli_name)):
            if live_fingerprint == self._fingerprint_snapshot(cli_name, name):
                return name
        return None

    def current_status(self, cli_name: str) -> tuple[bool, str | None]:
        """Return whether live files exist and whether they match a managed credential."""
        return self.has_live_credentials(cli_name), self.detect_current(cli_name)

    def _default_manifest(self) -> dict[str, Any]:
        return {
            "version": MANIFEST_VERSION,
            "active": {},
            "credentials": {cli_name: {} for cli_name in self.supported_clis()},
        }

    def _load_manifest(self) -> dict[str, Any]:
        if not self.manifest_path.exists():
            return self._default_manifest()
        try:
            raw = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CredentialError(f"Credential manifest is invalid: {exc}") from exc
        if not isinstance(raw, dict):
            raise CredentialError("Credential manifest is invalid: expected object.")
        raw.setdefault("version", MANIFEST_VERSION)
        raw.setdefault("active", {})
        credentials = raw.setdefault("credentials", {})
        if not isinstance(credentials, dict):
            raise CredentialError("Credential manifest is invalid: credentials must be an object.")
        for cli_name in self.supported_clis():
            credentials.setdefault(cli_name, {})
        return raw

    def _write_manifest(self, data: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _cli_entries(self, manifest: dict[str, Any], cli_name: str) -> dict[str, Any]:
        self._get_spec(cli_name)
        credentials = manifest.setdefault("credentials", {})
        entries = credentials.setdefault(cli_name, {})
        if not isinstance(entries, dict):
            raise CredentialError(f"Credential manifest is invalid for {cli_name}.")
        return entries

    def _get_spec(self, cli_name: str) -> CredentialSpec:
        try:
            return SPECS[cli_name]
        except KeyError as exc:
            raise CredentialError(f"Unsupported CLI: {cli_name}") from exc

    def _snapshot_dir(self, cli_name: str, name: str) -> Path:
        return self.root / cli_name / name

    def _live_path(self, rel: str) -> Path:
        return Path.home() / rel

    def _fingerprint_live(self, cli_name: str) -> dict[str, str]:
        spec = self._get_spec(cli_name)
        return {
            rel: self._hash_file(self._live_path(rel))
            for rel in spec.tracked_files
        }

    def _fingerprint_snapshot(self, cli_name: str, name: str) -> dict[str, str]:
        spec = self._get_spec(cli_name)
        snapshot_dir = self._snapshot_dir(cli_name, name)
        return {
            rel: self._hash_file(snapshot_dir / rel)
            for rel in spec.tracked_files
        }

    def _hash_file(self, path: Path) -> str:
        if not path.exists():
            return "missing"
        return sha256(path.read_bytes()).hexdigest()

    def _validate_name(self, name: str) -> None:
        normalized = name.strip()
        if not normalized:
            raise CredentialError("Credential name cannot be empty.")
        if normalized in {".", ".."} or not NAME_RE.match(normalized):
            raise CredentialError(f"Invalid credential name: {name}")

    def _extract_account_hint(self, cli_name: str) -> str:
        if cli_name == "claude":
            return self._extract_claude_hint()
        if cli_name == "codex":
            return self._extract_codex_hint()
        return ""

    def _extract_identity(self, cli_name: str) -> str:
        if cli_name == "claude":
            return self._load_json_value(
                self._live_path(".claude.json"),
                ("oauthAccount", "emailAddress"),
            )
        if cli_name == "codex":
            return self._load_json_value(
                self._live_path(".codex/auth.json"),
                ("tokens", "account_id"),
            )
        return ""

    def _extract_claude_hint(self) -> str:
        root_path = self._live_path(".claude.json")
        creds_path = self._live_path(".claude/.credentials.json")
        email = self._load_json_value(root_path, ("oauthAccount", "emailAddress"))
        org = self._load_json_value(root_path, ("oauthAccount", "organizationName"))
        tier = self._load_json_value(creds_path, ("claudeAiOauth", "subscriptionType"))
        parts = [part for part in (email, org, tier) if part]
        return " | ".join(parts)

    def _extract_codex_hint(self) -> str:
        auth_path = self._live_path(".codex/auth.json")
        mode = self._load_json_value(auth_path, ("auth_mode",))
        account_id = self._load_json_value(auth_path, ("tokens", "account_id"))
        parts = [part for part in (mode, account_id) if part]
        return " | ".join(parts)

    def _load_json_value(self, path: Path, keys: tuple[str, ...]) -> str:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return ""

        current: Any = data
        for key in keys:
            if not isinstance(current, dict):
                return ""
            current = current.get(key)
        return current if isinstance(current, str) else ""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
