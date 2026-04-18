"""Integration tests for CLI commands."""

import io
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from ctxforge.console.application import app
from ctxforge.core.profile import ProfileManager
from ctxforge.core.project import Project
from ctxforge.spec.schema import ProfileCliSection
from ctxforge.storage.profile_writer import write_profile
from ctxforge.storage.project_writer import write_project

runner = CliRunner()


class TestInitCommand:
    def test_init_creates_structure(self, tmp_path: Path):
        # language → key files prompt → profile name → description → auto_approve → decline run
        with (
            patch("ctxforge.console.commands.init.detect_ai_clis", return_value=["claude"]),
            patch("ctxforge.console.commands.init.detect_doc_candidates", return_value=[]),
        ):
            result = runner.invoke(
                app,
                ["init", str(tmp_path)],
                input="English\n\ndefault\nGeneral assistant\nn\nn\n",
            )
        assert result.exit_code == 0, result.output
        assert (tmp_path / ".ctxforge" / "project.toml").exists()
        assert (tmp_path / ".ctxforge" / "profiles" / "default" / "profile.toml").exists()

    def test_init_no_cli(self, tmp_path: Path):
        # language → key files prompt → profile name → description → auto_approve → decline run
        with (
            patch("ctxforge.console.commands.init.detect_ai_clis", return_value=[]),
            patch("ctxforge.console.commands.init.detect_doc_candidates", return_value=[]),
        ):
            result = runner.invoke(
                app,
                ["init", str(tmp_path)],
                input="English\n\ndefault\n\nn\nn\n",
            )
        assert result.exit_code == 0, result.output
        assert "No AI CLI tools detected" in result.output

    def test_init_with_doc_detection(self, tmp_path: Path):
        """Init with doc detection — all candidates accepted via checkbox."""
        candidates = ["README.md", "CHANGELOG.md", "docs/guide.md"]
        with (
            patch("ctxforge.console.commands.init.detect_ai_clis", return_value=["claude"]),
            patch(
                "ctxforge.console.commands.init.detect_doc_candidates",
                return_value=candidates,
            ) as mock_detect,
            patch(
                "ctxforge.console.commands.init._select_key_files",
                return_value=candidates,
            ),
        ):
            # language → (checkbox mocked) → profile name → description → auto_approve → decline run
            result = runner.invoke(
                app,
                ["init", str(tmp_path)],
                input="English\ndefault\nGeneral assistant\nn\nn\n",
            )
        assert result.exit_code == 0, result.output
        mock_detect.assert_called_once()

    def test_init_select_none(self, tmp_path: Path):
        """Init with doc detection — user deselects all in checkbox."""
        candidates = ["README.md"]
        with (
            patch("ctxforge.console.commands.init.detect_ai_clis", return_value=["claude"]),
            patch(
                "ctxforge.console.commands.init.detect_doc_candidates",
                return_value=candidates,
            ),
            patch(
                "ctxforge.console.commands.init._select_key_files",
                return_value=[],
            ),
        ):
            # language → (checkbox mocked) → profile name → description → auto_approve → decline run
            result = runner.invoke(
                app,
                ["init", str(tmp_path)],
                input="English\ndefault\n\nn\nn\n",
            )
        assert result.exit_code == 0, result.output

    def test_init_select_one(self, tmp_path: Path):
        """Init with doc detection — user selects a single file in checkbox."""
        candidates = ["README.md", "pyproject.toml"]
        with (
            patch("ctxforge.console.commands.init.detect_ai_clis", return_value=["claude"]),
            patch(
                "ctxforge.console.commands.init.detect_doc_candidates",
                return_value=candidates,
            ),
            patch(
                "ctxforge.console.commands.init._select_key_files",
                return_value=["README.md"],
            ),
        ):
            # language → (checkbox mocked) → profile name → description → auto_approve → decline run
            result = runner.invoke(
                app,
                ["init", str(tmp_path)],
                input="English\ndefault\n\nn\nn\n",
            )
        assert result.exit_code == 0, result.output

    def test_init_partial_select(self, tmp_path: Path):
        """Init with doc detection — user selects specific files in checkbox."""
        candidates = ["README.md", "docs/architecture.md", "CHANGELOG.md", "CONTRIBUTING.md"]
        with (
            patch("ctxforge.console.commands.init.detect_ai_clis", return_value=["claude"]),
            patch(
                "ctxforge.console.commands.init.detect_doc_candidates",
                return_value=candidates,
            ),
            patch(
                "ctxforge.console.commands.init._select_key_files",
                return_value=["README.md", "pyproject.toml"],
            ),
        ):
            # language → (checkbox mocked) → profile name → description → auto_approve → decline run
            result = runner.invoke(
                app,
                ["init", str(tmp_path)],
                input="English\ndefault\n\nn\nn\n",
            )
        assert result.exit_code == 0, result.output

    def test_reinit_skip_profile(self, ctxforge_project: Path):
        """Re-init with existing profiles, user declines creating new one."""
        with patch("ctxforge.console.commands.init.detect_ai_clis", return_value=["claude"]):
            # language → decline new profile
            result = runner.invoke(
                app,
                ["init", str(ctxforge_project)],
                input="English\nn\n",
            )
        assert result.exit_code == 0, result.output
        assert "Existing profiles" in result.output
        assert "Updated" in result.output

    def test_reinit_create_new_profile(self, ctxforge_project: Path):
        """Re-init with existing profiles, user creates a new one."""
        with (
            patch("ctxforge.console.commands.init.detect_ai_clis", return_value=["claude"]),
            patch("ctxforge.console.commands.init.detect_doc_candidates", return_value=[]),
        ):
            # language → accept new profile → key files prompt
            # → name → desc → auto_approve → decline run
            result = runner.invoke(
                app,
                ["init", str(ctxforge_project)],
                input="English\ny\n\nreviewer\nCode review\nn\nn\n",
            )
        assert result.exit_code == 0, result.output
        assert (
            ctxforge_project / ".ctxforge" / "profiles" / "reviewer" / "profile.toml"
        ).exists()


class TestLaunchSession:
    def test_launch_session_normal(self, ctxforge_project: Path):
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("ctxforge.runner.claude.subprocess.run", return_value=mock_result):
            from ctxforge.console.commands.run import launch_session

            exit_code = launch_session(ctxforge_project, "default")
        assert exit_code == 0

    def test_launch_session_compress(self, ctxforge_project: Path):
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("ctxforge.runner.claude.subprocess.run", return_value=mock_result) as mock_run:
            from ctxforge.console.commands.run import launch_session

            exit_code = launch_session(ctxforge_project, "default", compress=True)
        assert exit_code == 0
        # Verify compress greeting was used (contains "compress" keyword)
        call_args = mock_run.call_args[0][0]
        # The greeting is passed via -p flag
        full_cmd = " ".join(call_args)
        assert "compress" in full_cmd.lower()

    def test_launch_session_normalizes_profile_when_key_files_section_missing(
        self, ctxforge_project: Path,
    ):
        from ctxforge.console.commands.run import launch_session

        profile_path = (
            ctxforge_project / ".ctxforge" / "profiles" / "default" / "profile.toml"
        )
        profile_path.write_text(
            '\n'.join(
                [
                    "schema_version = 6",
                    "",
                    "[profile]",
                    'name = "default"',
                    'description = "Default profile"',
                    "",
                    "[role]",
                    'prompt = "You are a helpful assistant."',
                    "",
                    "[work_record.files]",
                    '"journal.md" = "work journal — completed tasks, in-progress, TODOs"',
                    '"pitfalls.md" = "pitfalls — gotchas, lessons learned, warnings"',
                    '"usermemo.md" = "user memo — persistent notes and instructions from the user"',
                    "",
                    "[injection]",
                    'strategy = "simple"',
                    'order = "role_first"',
                    "greeting = true",
                    "",
                    "[cli]",
                    'name = "claude"',
                    "auto_approve = false",
                    "",
                    "[budget]",
                    "max_tokens = 24000",
                    "",
                ]
            ),
            encoding="utf-8",
        )

        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("ctxforge.runner.claude.subprocess.run", return_value=mock_result):
            exit_code = launch_session(ctxforge_project, "default")

        assert exit_code == 0
        profile_text = profile_path.read_text(encoding="utf-8")
        assert "[key_files]" in profile_text
        assert "paths = []" in profile_text

    def test_launch_session_injects_memory_context_for_new_session(
        self, ctxforge_project: Path,
    ):
        from ctxforge.console.commands.run import launch_session

        project = Project.load(ctxforge_project)
        project.config.mempalace.enabled = True
        write_project(project.ctxforge_dir / "project.toml", project.config)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.ok = True

        with (
            patch("ctxforge.core.memory.shutil.which", return_value="/usr/bin/mempalace"),
            patch(
                "ctxforge.core.memory.importlib.util.find_spec",
                return_value=object(),
            ),
            patch(
                "ctxforge.console.commands.run.load_memory_preload",
                return_value=MagicMock(
                    status="loaded",
                    ok=True,
                    content="[Memory Context]\nRecovered context",
                ),
            ),
            patch("ctxforge.runner.claude.subprocess.run", return_value=mock_result) as mock_run,
        ):
            exit_code = launch_session(ctxforge_project, "default")

        assert exit_code == 0
        cmd = mock_run.call_args[0][0]
        injected_prompt = cmd[cmd.index("--append-system-prompt") + 1]
        assert "[Memory Context]" in injected_prompt
        assert "Recovered context" in injected_prompt

    def test_launch_session_errors_when_memory_enabled_but_mempalace_missing(
        self, ctxforge_project: Path,
    ):
        from ctxforge.console.commands.run import launch_session

        project = Project.load(ctxforge_project)
        project.config.mempalace.enabled = True
        write_project(project.ctxforge_dir / "project.toml", project.config)

        with (
            patch("ctxforge.core.memory.shutil.which", return_value=None),
            patch("ctxforge.runner.claude.subprocess.run") as mock_run,
        ):
            exit_code = launch_session(ctxforge_project, "default")

        assert exit_code == 1
        mock_run.assert_not_called()

    def test_launch_session_codex_resume_uses_saved_session(self, ctxforge_project: Path):
        from ctxforge.console.commands.run import launch_session

        pm = ProfileManager(ctxforge_project / ".ctxforge" / "profiles")
        profile = pm.load("default")
        profile.cli = ProfileCliSection(name="codex")
        write_profile(pm.profile_path("default"), profile)
        session_file = pm.profile_path("default").parent / ".session"
        session_file.write_text("real-codex-session", encoding="utf-8")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.ok = True
        mock_result.session_id = None
        mock_proc = MagicMock()
        mock_proc.wait.return_value = 0

        with (
            patch("ctxforge.console.commands.run._ask_session_action", return_value="resume"),
            patch("ctxforge.runner.codex.subprocess.Popen", return_value=mock_proc) as mock_run,
        ):
            exit_code = launch_session(ctxforge_project, "default")

        assert exit_code == 0
        call_args = mock_run.call_args[0][0]
        assert call_args[:3] == ["codex", "resume", "real-codex-session"]
        assert len(call_args) == 3

    def test_launch_session_claude_resume_uses_saved_session(self, ctxforge_project: Path):
        from ctxforge.console.commands.run import launch_session

        pm = ProfileManager(ctxforge_project / ".ctxforge" / "profiles")
        session_file = pm.profile_path("default").parent / ".session"
        session_file.write_text("real-claude-session", encoding="utf-8")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.ok = True

        with (
            patch("ctxforge.console.commands.run._ask_session_action", return_value="resume"),
            patch("ctxforge.runner.claude.subprocess.run", return_value=mock_result) as mock_run,
        ):
            exit_code = launch_session(ctxforge_project, "default")

        assert exit_code == 0
        call_args = mock_run.call_args[0][0]
        assert call_args[:3] == ["claude", "--resume", "real-claude-session"]

    def test_launch_session_claude_starts_new_session_when_profile_has_no_owned_session(
        self, ctxforge_project: Path,
    ):
        from ctxforge.console.commands.run import launch_session

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.ok = True

        with (
            patch(
                "ctxforge.console.commands.run._discover_claude_session_id",
                return_value=None,
            ),
            patch("ctxforge.runner.claude.subprocess.run", return_value=mock_result) as mock_run,
        ):
            exit_code = launch_session(ctxforge_project, "default")

        assert exit_code == 0
        call_args = mock_run.call_args[0][0]
        assert call_args[0] == "claude"
        assert "--resume" not in call_args
        assert "--session-id" in call_args

    def test_launch_session_claude_ignores_stale_session_file_not_owned_by_profile(
        self, ctxforge_project: Path,
    ):
        from ctxforge.console.commands.run import launch_session

        pm = ProfileManager(ctxforge_project / ".ctxforge" / "profiles")
        profile_dir = pm.profile_path("default").parent
        (profile_dir / ".session").write_text("foreign-claude-session", encoding="utf-8")
        (profile_dir / "sessions.json").write_text(
            json.dumps(
                [
                    {
                        "session_id": "owned-claude-session",
                        "cwd": str(ctxforge_project),
                        "modified_at": "2026-04-01T01:00:00+00:00",
                        "preview": "owned profile session",
                    }
                ]
            ),
            encoding="utf-8",
        )

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.ok = True

        with (
            patch("ctxforge.console.commands.run._ask_session_action", return_value="resume"),
            patch("ctxforge.runner.claude.subprocess.run", return_value=mock_result) as mock_run,
        ):
            exit_code = launch_session(ctxforge_project, "default")

        assert exit_code == 0
        call_args = mock_run.call_args[0][0]
        assert call_args[:3] == ["claude", "--resume", "owned-claude-session"]

    def test_launch_session_claude_list_sessions_selects_choice(
        self, ctxforge_project: Path,
    ):
        from ctxforge.console.commands.run import launch_session

        pm = ProfileManager(ctxforge_project / ".ctxforge" / "profiles")
        session_file = pm.profile_path("default").parent / ".session"
        session_file.write_text("real-claude-session", encoding="utf-8")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.ok = True

        with (
            patch("ctxforge.console.commands.run._ask_session_action", return_value="list"),
            patch(
                "ctxforge.console.commands.run._select_claude_session",
                return_value="picked-claude-session",
            ),
            patch("ctxforge.runner.claude.subprocess.run", return_value=mock_result) as mock_run,
        ):
            exit_code = launch_session(ctxforge_project, "default")

        assert exit_code == 0
        call_args = mock_run.call_args[0][0]
        assert call_args[:3] == ["claude", "--resume", "picked-claude-session"]
        assert session_file.read_text(encoding="utf-8") == "picked-claude-session"

    def test_select_claude_session_shows_preview(self):
        from ctxforge.console.commands.run import _select_claude_session
        from ctxforge.runner.claude import ClaudeSessionInfo

        sessions = [
            ClaudeSessionInfo(
                session_id="picked-claude-session",
                cwd="/repo",
                modified_at=datetime(2026, 4, 1, 1, 0, tzinfo=timezone.utc),
                path=Path("/tmp/session.jsonl"),
                preview="Claude 最后一条用户可识别的消息预览",
            )
        ]

        profile_dir = Path("/tmp/profile")
        stdin = io.StringIO("1\n")
        with (
            patch(
                "ctxforge.console.commands.run.ClaudeRunner.list_sessions",
                return_value=sessions,
            ),
            patch("ctxforge.console.commands.run._load_profile_sessions", return_value=[]),
            patch("sys.stdin", stdin),
            patch("sys.stdout.isatty", return_value=True),
            patch("ctxforge.console.commands.run.console.print") as mock_print,
        ):
            selected = _select_claude_session(profile_dir, Path("/repo"))

        assert selected == "picked-claude-session"
        rendered = " ".join(str(call.args[0]) for call in mock_print.call_args_list if call.args)
        assert "Claude 最后一条用户可识别的消息预览" in rendered

    def test_launch_session_codex_new_session_saves_real_session_id(self, ctxforge_project: Path):
        from ctxforge.console.commands.run import launch_session

        pm = ProfileManager(ctxforge_project / ".ctxforge" / "profiles")
        profile = pm.load("default")
        profile.cli = ProfileCliSection(name="codex")
        write_profile(pm.profile_path("default"), profile)
        session_file = pm.profile_path("default").parent / ".session"
        session_file.write_text("stale-random-uuid", encoding="utf-8")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.ok = True
        mock_result.session_id = "real-codex-session"

        with (
            patch("ctxforge.console.commands.run._ask_session_action", return_value="new"),
            patch("ctxforge.console.commands.run.get_runner") as mock_get_runner,
        ):
            mock_runner = MagicMock()

            def run_side_effect(*args, **kwargs):
                callback = kwargs.get("on_session_started")
                assert callable(callback)
                callback("real-codex-session")
                assert session_file.read_text(encoding="utf-8") == "real-codex-session"
                return mock_result

            mock_runner.run.side_effect = run_side_effect
            mock_get_runner.return_value = mock_runner
            exit_code = launch_session(ctxforge_project, "default")

        assert exit_code == 0
        assert session_file.read_text(encoding="utf-8") == "real-codex-session"

    def test_launch_session_codex_starts_new_session_when_profile_has_no_owned_session(
        self, ctxforge_project: Path,
    ):
        from ctxforge.console.commands.run import launch_session

        pm = ProfileManager(ctxforge_project / ".ctxforge" / "profiles")
        profile = pm.load("default")
        profile.cli = ProfileCliSection(name="codex")
        write_profile(pm.profile_path("default"), profile)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.ok = True
        mock_result.session_id = None
        mock_proc = MagicMock()
        mock_proc.poll.side_effect = [None, 0]
        mock_proc.wait.return_value = 0

        with (
            patch(
                "ctxforge.console.commands.run._discover_recent_codex_session_id",
                return_value=None,
            ),
            patch("ctxforge.runner.codex.subprocess.Popen", return_value=mock_proc) as mock_run,
            patch("ctxforge.runner.codex.CodexRunner.find_latest_session_id", return_value=None),
        ):
            exit_code = launch_session(ctxforge_project, "default")

        assert exit_code == 0
        call_args = mock_run.call_args[0][0]
        assert call_args[0] == "codex"
        assert "resume" not in call_args

    def test_launch_session_codex_ignores_stale_session_file_not_owned_by_profile(
        self, ctxforge_project: Path,
    ):
        from ctxforge.console.commands.run import launch_session

        pm = ProfileManager(ctxforge_project / ".ctxforge" / "profiles")
        profile = pm.load("default")
        profile.cli = ProfileCliSection(name="codex")
        write_profile(pm.profile_path("default"), profile)
        profile_dir = pm.profile_path("default").parent
        (profile_dir / ".session").write_text("foreign-session", encoding="utf-8")
        (profile_dir / "sessions.json").write_text(
            json.dumps(
                [
                    {
                        "session_id": "owned-codex-session",
                        "cwd": str(ctxforge_project),
                        "modified_at": "2026-04-01T01:00:00+00:00",
                        "preview": "owned profile session",
                    }
                ]
            ),
            encoding="utf-8",
        )

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.ok = True
        mock_result.session_id = None
        mock_proc = MagicMock()
        mock_proc.wait.return_value = 0

        with (
            patch("ctxforge.console.commands.run._ask_session_action", return_value="resume"),
            patch("ctxforge.runner.codex.subprocess.Popen", return_value=mock_proc) as mock_run,
        ):
            exit_code = launch_session(ctxforge_project, "default")

        assert exit_code == 0
        call_args = mock_run.call_args[0][0]
        assert call_args[:3] == ["codex", "resume", "owned-codex-session"]

    def test_launch_session_codex_list_sessions_selects_choice(
        self, ctxforge_project: Path,
    ):
        from ctxforge.console.commands.run import launch_session

        pm = ProfileManager(ctxforge_project / ".ctxforge" / "profiles")
        profile = pm.load("default")
        profile.cli = ProfileCliSection(name="codex")
        write_profile(pm.profile_path("default"), profile)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.ok = True
        mock_result.session_id = None
        mock_proc = MagicMock()
        mock_proc.wait.return_value = 0

        with (
            patch(
                "ctxforge.console.commands.run._discover_recent_codex_session_id",
                return_value="recent-codex-session",
            ),
            patch("ctxforge.console.commands.run._ask_session_action", return_value="list"),
            patch(
                "ctxforge.console.commands.run._select_codex_session",
                return_value="picked-codex-session",
            ),
            patch("ctxforge.runner.codex.subprocess.Popen", return_value=mock_proc) as mock_run,
        ):
            exit_code = launch_session(ctxforge_project, "default")

        assert exit_code == 0
        call_args = mock_run.call_args[0][0]
        assert call_args[:3] == ["codex", "resume", "picked-codex-session"]
        session_file = pm.profile_path("default").parent / ".session"
        assert session_file.read_text(encoding="utf-8") == "picked-codex-session"

    def test_launch_session_codex_list_all_sessions_selects_choice(
        self, ctxforge_project: Path,
    ):
        from ctxforge.console.commands.run import launch_session

        pm = ProfileManager(ctxforge_project / ".ctxforge" / "profiles")
        profile = pm.load("default")
        profile.cli = ProfileCliSection(name="codex")
        write_profile(pm.profile_path("default"), profile)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.ok = True
        mock_result.session_id = None
        mock_proc = MagicMock()
        mock_proc.wait.return_value = 0

        with (
            patch(
                "ctxforge.console.commands.run._discover_recent_codex_session_id",
                return_value="recent-codex-session",
            ),
            patch("ctxforge.console.commands.run._ask_session_action", return_value="list_all"),
            patch(
                "ctxforge.console.commands.run._select_codex_global_session",
                return_value="picked-global-codex-session",
            ),
            patch("ctxforge.runner.codex.subprocess.Popen", return_value=mock_proc) as mock_run,
        ):
            exit_code = launch_session(ctxforge_project, "default")

        assert exit_code == 0
        call_args = mock_run.call_args[0][0]
        assert call_args[:3] == ["codex", "resume", "picked-global-codex-session"]
        session_file = pm.profile_path("default").parent / ".session"
        assert session_file.read_text(encoding="utf-8") == "picked-global-codex-session"

    def test_select_codex_session_shows_preview(self):
        from ctxforge.console.commands.run import _select_codex_session
        from ctxforge.runner.codex import CodexSessionInfo

        sessions = [
            CodexSessionInfo(
                session_id="picked-codex-session",
                cwd="/repo",
                created_at=datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc),
                modified_at=datetime(2026, 4, 1, 1, 0, tzinfo=timezone.utc),
                path=Path("/tmp/session.jsonl"),
                preview="最后一条用户可识别的消息预览",
            )
        ]

        profile_dir = Path("/tmp/profile")
        stdin = io.StringIO("1\n")
        with (
            patch("ctxforge.console.commands.run.CodexRunner.list_sessions", return_value=sessions),
            patch("ctxforge.console.commands.run._load_profile_sessions", return_value=[]),
            patch("sys.stdin", stdin),
            patch("sys.stdout.isatty", return_value=True),
            patch("ctxforge.console.commands.run.console.print") as mock_print,
        ):
            selected = _select_codex_session(profile_dir, Path("/repo"))

        assert selected == "picked-codex-session"
        rendered = " ".join(str(call.args[0]) for call in mock_print.call_args_list if call.args)
        assert "最后一条用户可识别的消息预览" in rendered

    def test_select_codex_global_session_lists_all_sessions(self):
        from ctxforge.console.commands.run import _select_codex_global_session
        from ctxforge.runner.codex import CodexSessionInfo

        sessions = [
            CodexSessionInfo(
                session_id="global-codex-session",
                cwd="/other-repo",
                created_at=datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc),
                modified_at=datetime(2026, 4, 1, 1, 0, tzinfo=timezone.utc),
                path=Path("/tmp/session.jsonl"),
                preview="来自其他项目的全局 session 预览",
            )
        ]

        profile_dir = Path("/tmp/profile")
        stdin = io.StringIO("1\n")
        with (
            patch(
                "ctxforge.console.commands.run.CodexRunner.list_sessions",
                return_value=sessions,
            ) as mock_list_sessions,
            patch("ctxforge.console.commands.run._load_profile_sessions", return_value=[]),
            patch("sys.stdin", stdin),
            patch("sys.stdout.isatty", return_value=True),
        ):
            selected = _select_codex_global_session(profile_dir, Path("/repo"))

        assert selected == "global-codex-session"
        mock_list_sessions.assert_called_once_with(cwd=None)

    def test_select_codex_global_session_ignores_profile_index(self, ctxforge_project: Path):
        from ctxforge.console.commands.run import _select_codex_global_session
        from ctxforge.runner.codex import CodexSessionInfo

        pm = ProfileManager(ctxforge_project / ".ctxforge" / "profiles")
        profile_dir = pm.profile_path("default").parent
        (profile_dir / "sessions.json").write_text(
            json.dumps(
                [
                    {
                        "session_id": "profile-owned-session",
                        "cwd": str(ctxforge_project),
                        "modified_at": "2026-04-01T01:00:00+00:00",
                        "preview": "profile scoped preview",
                    }
                ]
            ),
            encoding="utf-8",
        )

        sessions = [
            CodexSessionInfo(
                session_id="global-codex-session",
                cwd="/other-repo",
                created_at=datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc),
                modified_at=datetime(2026, 4, 1, 1, 0, tzinfo=timezone.utc),
                path=Path("/tmp/session.jsonl"),
                preview="来自其他项目的全局 session 预览",
            )
        ]

        stdin = io.StringIO("1\n")
        with (
            patch(
                "ctxforge.console.commands.run.CodexRunner.list_sessions",
                return_value=sessions,
            ) as mock_list_sessions,
            patch("sys.stdin", stdin),
            patch("sys.stdout.isatty", return_value=True),
        ):
            selected = _select_codex_global_session(profile_dir, ctxforge_project)

        assert selected == "global-codex-session"
        mock_list_sessions.assert_called_once_with(cwd=None)

    def test_ask_session_action_supports_list_all(self):
        from ctxforge.console.commands.run import _ask_session_action

        stdin = io.StringIO("la\n")
        with (
            patch("sys.stdin", stdin),
            patch("sys.stdin.isatty", return_value=True),
        ):
            action = _ask_session_action(allow_list=True, allow_list_all=True)

        assert action == "list_all"

    def test_select_codex_session_prefers_profile_index(self, ctxforge_project: Path):
        from ctxforge.console.commands.run import _select_codex_session

        pm = ProfileManager(ctxforge_project / ".ctxforge" / "profiles")
        profile_dir = pm.profile_path("default").parent
        (profile_dir / "sessions.json").write_text(
            json.dumps(
                [
                    {
                        "session_id": "profile-owned-session",
                        "cwd": str(ctxforge_project),
                        "modified_at": "2026-04-01T01:00:00+00:00",
                        "preview": "profile scoped preview",
                    }
                ]
            ),
            encoding="utf-8",
        )

        stdin = io.StringIO("1\n")
        with (
            patch("ctxforge.console.commands.run.CodexRunner.list_sessions") as mock_list_sessions,
            patch("sys.stdin", stdin),
            patch("sys.stdout.isatty", return_value=True),
        ):
            selected = _select_codex_session(profile_dir, ctxforge_project)

        assert selected == "profile-owned-session"
        mock_list_sessions.assert_not_called()


class TestRunCommand:
    def test_run_default_profile(self, ctxforge_project: Path, monkeypatch):
        monkeypatch.chdir(ctxforge_project)
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("ctxforge.runner.claude.subprocess.run", return_value=mock_result) as mock_run:
            result = runner.invoke(app, ["run"])
        assert result.exit_code == 0, result.output
        # Should call claude with --append-system-prompt
        call_args = mock_run.call_args[0][0]
        assert call_args[0] == "claude"

    def test_run_named_profile(self, ctxforge_project: Path, monkeypatch):
        monkeypatch.chdir(ctxforge_project)
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("ctxforge.runner.claude.subprocess.run", return_value=mock_result):
            result = runner.invoke(app, ["run", "default"])
        assert result.exit_code == 0, result.output


class TestProfileCommands:
    def test_profile_list(self, ctxforge_project: Path, monkeypatch):
        monkeypatch.chdir(ctxforge_project)
        result = runner.invoke(app, ["profile", "list"])
        assert result.exit_code == 0, result.output
        assert "default" in result.output

    def test_profile_show(self, ctxforge_project: Path, monkeypatch):
        monkeypatch.chdir(ctxforge_project)
        result = runner.invoke(app, ["profile", "show", "default"])
        assert result.exit_code == 0, result.output
        assert "default" in result.output

    def test_profile_create(self, ctxforge_project: Path, monkeypatch):
        monkeypatch.chdir(ctxforge_project)
        result = runner.invoke(
            app, ["profile", "create", "reviewer", "--desc", "Review code"]
        )
        assert result.exit_code == 0, result.output
        assert "Created profile 'reviewer'" in result.output
        assert (
            ctxforge_project / ".ctxforge" / "profiles" / "reviewer" / "profile.toml"
        ).exists()

    def test_profile_edit_interactive(self, ctxforge_project: Path, monkeypatch):
        monkeypatch.chdir(ctxforge_project)
        # Interactive: keep name, change desc, keep prompt, skip cli/auto_approve
        result = runner.invoke(
            app, ["profile", "edit", "default"],
            input="default\nUpdated desc\n\n\nn\n",
        )
        assert result.exit_code == 0, result.output
        assert "Updated profile 'default'" in result.output

    def test_profile_edit_rename(self, ctxforge_project: Path, monkeypatch):
        monkeypatch.chdir(ctxforge_project)
        # Interactive: rename to "main", keep desc/prompt, skip cli/auto_approve
        result = runner.invoke(
            app, ["profile", "edit", "default"],
            input="main\n\n\n\nn\n",
        )
        assert result.exit_code == 0, result.output
        assert "Renamed" in result.output
        assert (
            ctxforge_project / ".ctxforge" / "profiles" / "main" / "profile.toml"
        ).exists()

    def test_profile_create_duplicate(self, ctxforge_project: Path, monkeypatch):
        monkeypatch.chdir(ctxforge_project)
        result = runner.invoke(app, ["profile", "create", "default"])
        assert result.exit_code == 1


class TestCleanCommand:
    def test_clean_removes_ctxforge_dir(self, ctxforge_project: Path):
        result = runner.invoke(
            app, ["clean", str(ctxforge_project)], input="y\n"
        )
        assert result.exit_code == 0, result.output
        assert "Removed" in result.output
        assert not (ctxforge_project / ".ctxforge").exists()

    def test_clean_cancelled(self, ctxforge_project: Path):
        result = runner.invoke(
            app, ["clean", str(ctxforge_project)], input="n\n"
        )
        assert result.exit_code == 0, result.output
        assert "Cancelled" in result.output
        assert (ctxforge_project / ".ctxforge").exists()

    def test_clean_removes_slash_commands(self, ctxforge_project: Path):
        """Clean also removes .claude/commands/ctx-*.md files."""
        commands_dir = ctxforge_project / ".claude" / "commands"
        commands_dir.mkdir(parents=True)
        for name in ["ctx-profile.md", "ctx-files.md", "ctx-update.md", "ctx-compress.md"]:
            (commands_dir / name).write_text("test")
        # Also place a non-ctxforge command to ensure it survives
        (commands_dir / "other.md").write_text("keep")

        result = runner.invoke(
            app, ["clean", str(ctxforge_project)], input="y\n"
        )
        assert result.exit_code == 0, result.output
        assert "slash command" in result.output
        assert not (commands_dir / "ctx-profile.md").exists()
        assert (commands_dir / "other.md").exists()

    def test_clean_nothing_to_clean(self, tmp_path: Path):
        result = runner.invoke(app, ["clean", str(tmp_path)])
        assert result.exit_code == 0, result.output
        assert "Nothing to clean" in result.output


class TestVersionFlag:
    def test_version(self):
        result = runner.invoke(app, ["--version"])
        assert "1.4.8" in result.output


class TestSetProcTitle:
    def test_main_calls_setproctitle(self):
        """main() sets the process title to 'ctxforge'."""
        with (
            patch("ctxforge.console.application.setproctitle") as mock_spt,
            patch("ctxforge.console.application.app"),
        ):
            from ctxforge.console.application import main

            main()
            mock_spt.assert_called_once_with("ctxforge")
