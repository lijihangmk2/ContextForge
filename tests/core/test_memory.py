"""Tests for MemPalace memory helpers."""

import subprocess
from pathlib import Path
from unittest.mock import patch

from ctxforge.core.memory import (
    build_mempalace_mcp_server,
    load_memory_preload,
    resolve_memory_binding,
    validate_mempalace_installation,
)
from ctxforge.spec.schema import MempalaceSection, ProjectConfig, ProjectSection


class TestResolveMemoryBinding:
    def test_returns_none_when_disabled(self, tmp_path: Path):
        project = ProjectConfig(project=ProjectSection(name="test"))
        binding = resolve_memory_binding(tmp_path, "dev", project)
        assert binding is None

    def test_uses_project_scoped_default_palace(self, tmp_path: Path):
        project = ProjectConfig(
            project=ProjectSection(name="test"),
            mempalace=MempalaceSection(enabled=True),
        )
        binding = resolve_memory_binding(tmp_path, "Dev Agent", project)
        assert binding is not None
        assert binding.namespace == "profile/dev-agent"
        assert binding.wing == "profile-dev-agent"
        assert binding.palace_path == tmp_path / ".ctxforge" / "memory" / "mempalace"


class TestLoadMemoryPreload:
    def test_returns_unavailable_when_cli_missing(self, tmp_path: Path):
        project = ProjectConfig(
            project=ProjectSection(name="test"),
            mempalace=MempalaceSection(enabled=True),
        )
        binding = resolve_memory_binding(tmp_path, "dev", project)

        with patch("ctxforge.core.memory.shutil.which", return_value=None):
            result = load_memory_preload(binding)

        assert result.status == "unavailable"

    def test_formats_loaded_context(self, tmp_path: Path):
        project = ProjectConfig(
            project=ProjectSection(name="test"),
            mempalace=MempalaceSection(enabled=True),
        )
        binding = resolve_memory_binding(tmp_path, "dev", project)
        proc = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="Found prior decision",
        )

        with (
            patch("ctxforge.core.memory.shutil.which", return_value="/usr/bin/mempalace"),
            patch("ctxforge.core.memory.subprocess.run", return_value=proc) as mock_run,
        ):
            result = load_memory_preload(binding)

        assert result.ok
        assert "[Memory Context]" in result.content
        assert "profile/dev" in result.content
        call_args = mock_run.call_args[0][0]
        assert call_args[:4] == [
            "/usr/bin/mempalace",
            "--palace",
            str(tmp_path / ".ctxforge" / "memory" / "mempalace"),
            "search",
        ]


class TestMempalaceRuntime:
    def test_validate_accepts_pipx_shebang(self, tmp_path: Path):
        cli = tmp_path / "mempalace"
        interpreter = tmp_path / "pipx-python"
        interpreter.write_text("", encoding="utf-8")
        cli.write_text(f"#!{interpreter}\n", encoding="utf-8")

        with (
            patch("ctxforge.core.memory.shutil.which", return_value=str(cli)),
            patch("ctxforge.core.memory.importlib.util.find_spec", return_value=None),
        ):
            result = validate_mempalace_installation()

        assert result.ok

    def test_build_mcp_server_uses_pipx_interpreter(self, tmp_path: Path):
        project = ProjectConfig(
            project=ProjectSection(name="test"),
            mempalace=MempalaceSection(enabled=True),
        )
        binding = resolve_memory_binding(tmp_path, "dev", project)
        cli = tmp_path / "mempalace"
        interpreter = tmp_path / "pipx-python"
        interpreter.write_text("", encoding="utf-8")
        cli.write_text(f"#!{interpreter}\n", encoding="utf-8")

        with (
            patch("ctxforge.core.memory.shutil.which", return_value=str(cli)),
            patch("ctxforge.core.memory.importlib.util.find_spec", return_value=None),
        ):
            server = build_mempalace_mcp_server(binding)

        assert server["ctxforge-memory-mempalace"]["command"] == str(interpreter)
