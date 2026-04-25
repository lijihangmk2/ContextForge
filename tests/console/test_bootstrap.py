from __future__ import annotations

from unittest.mock import patch

import pytest

from ctxforge import bootstrap


class TestBootstrapDiagnostics:
    def test_format_diagnostics_with_env_mismatch(self):
        with (
            patch("ctxforge.bootstrap.sys.executable", "/tmp/pipx/venv/bin/python"),
            patch("ctxforge.bootstrap.sys.prefix", "/tmp/pipx/venv"),
            patch.dict("ctxforge.bootstrap.os.environ", {"VIRTUAL_ENV": "/workspace/.venv"}),
        ):
            lines = bootstrap._format_startup_diagnostics()

        joined = "\n".join(lines)
        assert "Environment mismatch detected" in joined
        assert "/workspace/.venv" in joined
        assert "/tmp/pipx/venv/bin/python" in joined

    def test_format_diagnostics_without_virtual_env(self):
        with (
            patch("ctxforge.bootstrap.sys.executable", "/tmp/pipx/venv/bin/python"),
            patch("ctxforge.bootstrap.sys.prefix", "/tmp/pipx/venv"),
            patch.dict("ctxforge.bootstrap.os.environ", {}, clear=True),
        ):
            lines = bootstrap._format_startup_diagnostics()

        assert any("VIRTUAL_ENV    = <unset>" in line for line in lines)

    def test_main_prints_diagnostics_on_import_keyboard_interrupt(
        self,
        capsys: pytest.CaptureFixture[str],
    ):
        original_import = __import__

        def fake_import(name: str, globals=None, locals=None, fromlist=(), level: int = 0):
            if name == "ctxforge.console.application":
                raise KeyboardInterrupt
            return original_import(name, globals, locals, fromlist, level)

        with (
            patch("builtins.__import__", side_effect=fake_import),
            patch("ctxforge.bootstrap.sys.executable", "/tmp/pipx/venv/bin/python"),
            patch("ctxforge.bootstrap.sys.prefix", "/tmp/pipx/venv"),
            patch.dict("ctxforge.bootstrap.os.environ", {"VIRTUAL_ENV": "/workspace/.venv"}),
        ):
            with pytest.raises(SystemExit) as exc_info:
                bootstrap.main()

        assert exc_info.value.code == 130
        stderr = capsys.readouterr().err
        assert "Startup failed before CLI initialization" in stderr
        assert "Environment mismatch detected" in stderr
