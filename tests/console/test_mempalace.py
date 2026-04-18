"""Tests for ctxforge mempalace commands."""

from unittest.mock import patch

import tomllib
from typer.testing import CliRunner

from ctxforge.console.application import app

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
