"""Tests for ctxforge mempalace commands."""

import json
from unittest.mock import patch

import tomllib
from typer.testing import CliRunner

from ctxforge.console.application import app
from ctxforge.spec.schema import ProfileCliSection
from ctxforge.storage.profile_writer import write_profile

runner = CliRunner()


def test_enable_checks_runtime(ctxforge_project, monkeypatch):
    monkeypatch.chdir(ctxforge_project)
    with (
        patch("ctxforge.core.memory.shutil.which", return_value="/usr/bin/mempalace"),
        patch("ctxforge.core.memory.importlib.util.find_spec", return_value=object()),
    ):
        result = runner.invoke(app, ["mempalace", "enable"])
    assert result.exit_code == 0, result.output
    assert "Enabled MemPalace" in result.output
    assert "Checkpoint interval: 1" in result.output


def test_enable_fails_when_unavailable(ctxforge_project, monkeypatch):
    monkeypatch.chdir(ctxforge_project)
    with patch("ctxforge.core.memory.shutil.which", return_value=None):
        result = runner.invoke(app, ["mempalace", "enable"])
    assert result.exit_code == 1
    assert "not on PATH" in result.output


def test_status_checks_runtime(ctxforge_project, monkeypatch):
    monkeypatch.chdir(ctxforge_project)
    with patch("ctxforge.core.memory.shutil.which", return_value=None):
        result = runner.invoke(app, ["mempalace", "status"])
    assert result.exit_code == 0, result.output
    assert "Runtime:" in result.output
    assert "unavailable" in result.output


def test_set_interval_requires_enabled(ctxforge_project, monkeypatch):
    monkeypatch.chdir(ctxforge_project)
    result = runner.invoke(app, ["mempalace", "set", "interval", "5"])
    assert result.exit_code == 1
    assert "enable" in result.output


def test_set_interval_updates_project_config(ctxforge_project, monkeypatch):
    monkeypatch.chdir(ctxforge_project)
    with (
        patch("ctxforge.core.memory.shutil.which", return_value="/usr/bin/mempalace"),
        patch("ctxforge.core.memory.importlib.util.find_spec", return_value=object()),
    ):
        enable = runner.invoke(app, ["mempalace", "enable"])
    assert enable.exit_code == 0, enable.output

    result = runner.invoke(app, ["mempalace", "set", "interval", "5"])
    assert result.exit_code == 0, result.output
    assert "interval to 5" in result.output

    with open(ctxforge_project / ".ctxforge" / "project.toml", "rb") as f:
        data = tomllib.load(f)
    assert data["mempalace"]["checkpoint_interval"] == 5


def test_set_interval_clears_managed_hooks_instead_of_status_namespace(
    ctxforge_project,
    monkeypatch,
):
    monkeypatch.chdir(ctxforge_project)
    settings_path = ctxforge_project / ".claude" / "settings.local.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        json.dumps(
            {
                "hooks": {
                    "Stop": [
                        {
                            "matcher": "*",
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "ctxforge hook memory --namespace profile/status",
                                }
                            ],
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    with (
        patch("ctxforge.core.memory.shutil.which", return_value="/usr/bin/mempalace"),
        patch("ctxforge.core.memory.importlib.util.find_spec", return_value=object()),
    ):
        enable = runner.invoke(app, ["mempalace", "enable"])
    assert enable.exit_code == 0, enable.output

    result = runner.invoke(app, ["mempalace", "set", "interval", "5"])
    assert result.exit_code == 0, result.output

    data = json.loads(settings_path.read_text(encoding="utf-8"))
    assert "hooks" not in data


def test_debug_reports_codex_limitations(ctxforge_project, monkeypatch):
    monkeypatch.chdir(ctxforge_project)
    profile_path = (
        ctxforge_project / ".ctxforge" / "profiles" / "default" / "profile.toml"
    )
    from ctxforge.spec.loader import load_profile

    profile = load_profile(profile_path)
    profile.cli = ProfileCliSection(name="codex")
    write_profile(profile_path, profile)

    with (
        patch("ctxforge.core.memory.shutil.which", return_value="/usr/bin/mempalace"),
        patch("ctxforge.core.memory.importlib.util.find_spec", return_value=object()),
    ):
        enable = runner.invoke(app, ["mempalace", "enable"])
    assert enable.exit_code == 0, enable.output

    with patch(
        "ctxforge.console.commands.mempalace.load_memory_preload",
        return_value=type("Preload", (), {"status": "error"})(),
    ):
        result = runner.invoke(app, ["mempalace", "debug", "default"])

    assert result.exit_code == 0, result.output
    assert "CLI: codex" in result.output
    assert "Autosave support: no" in result.output
    assert "Codex MCP support: no" in result.output
