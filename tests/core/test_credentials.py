"""Tests for system-level credential management."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ctxforge.core.credentials import CredentialsManager
from ctxforge.exceptions import CredentialError


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class TestCredentialsManager:
    def test_suggested_name_uses_unique_identifier(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        home = tmp_path / "home"
        monkeypatch.setenv("HOME", str(home))
        manager = CredentialsManager(root=tmp_path / "store")

        _write_json(
            home / ".claude" / ".credentials.json",
            {"claudeAiOauth": {"subscriptionType": "pro"}},
        )
        _write_json(
            home / ".claude.json",
            {"oauthAccount": {"emailAddress": "dev@example.com"}},
        )
        _write_json(
            home / ".codex" / "auth.json",
            {"auth_mode": "login", "tokens": {"account_id": "acct-123"}},
        )

        assert manager.suggested_name("claude") == "dev@example.com"
        assert manager.suggested_name("codex") == "acct-123"

    def test_capture_and_detect_current_claude(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        home = tmp_path / "home"
        monkeypatch.setenv("HOME", str(home))
        manager = CredentialsManager(root=tmp_path / "store")

        _write_json(
            home / ".claude" / ".credentials.json",
            {"claudeAiOauth": {"subscriptionType": "pro"}},
        )
        _write_json(
            home / ".claude.json",
            {"oauthAccount": {"emailAddress": "dev@example.com"}},
        )

        captured = manager.capture("claude", "work")

        assert captured.name == "work"
        assert manager.detect_current("claude") == "work"
        listed = manager.list_credentials("claude")
        assert len(listed) == 1
        assert listed[0].current is True
        assert "dev@example.com" in listed[0].account_hint

    def test_switch_restores_snapshot(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        home = tmp_path / "home"
        monkeypatch.setenv("HOME", str(home))
        manager = CredentialsManager(root=tmp_path / "store")

        auth_path = home / ".codex" / "auth.json"
        _write_json(auth_path, {"auth_mode": "login", "tokens": {"account_id": "acct-a"}})
        manager.capture("codex", "acct-a")

        _write_json(auth_path, {"auth_mode": "login", "tokens": {"account_id": "acct-b"}})
        manager.capture("codex", "acct-b")

        manager.switch("codex", "acct-a")

        live = json.loads(auth_path.read_text(encoding="utf-8"))
        assert live["tokens"]["account_id"] == "acct-a"
        assert manager.detect_current("codex") == "acct-a"

    def test_remove_blocks_current_credential(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        home = tmp_path / "home"
        monkeypatch.setenv("HOME", str(home))
        manager = CredentialsManager(root=tmp_path / "store")

        _write_json(
            home / ".codex" / "auth.json",
            {"auth_mode": "login", "tokens": {"account_id": "acct-a"}},
        )
        manager.capture("codex", "acct-a")

        with pytest.raises(CredentialError, match="currently active"):
            manager.remove("codex", "acct-a")

    def test_clean_removes_managed_snapshots_but_keeps_live_auth(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        home = tmp_path / "home"
        monkeypatch.setenv("HOME", str(home))
        manager = CredentialsManager(root=tmp_path / "store")

        auth_path = home / ".codex" / "auth.json"
        _write_json(auth_path, {"auth_mode": "login", "tokens": {"account_id": "acct-a"}})
        manager.capture("codex", "acct-a")

        manager.clean("codex")

        assert auth_path.exists()
        assert manager.list_credentials("codex") == []
