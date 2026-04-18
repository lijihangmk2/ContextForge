"""Tests for internal hook commands."""

import json
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from ctxforge.console.application import app

runner = CliRunner()


def test_memory_stop_hook_blocks_after_interval(tmp_path: Path) -> None:
    transcript = tmp_path / "session.jsonl"
    transcript.write_text(
        "\n".join(
            json.dumps({"message": {"role": "user", "content": f"msg {idx}"}})
            for idx in range(2)
        )
        + "\n",
        encoding="utf-8",
    )

    payload = json.dumps(
        {
            "session_id": "abc-123",
            "stop_hook_active": False,
            "transcript_path": str(transcript),
        }
    )
    with (
        patch("ctxforge.console.commands.hook.STATE_DIR", tmp_path / "hook_state"),
        patch("ctxforge.console.commands.hook.shutil.which", return_value="/usr/bin/mempalace"),
        patch("ctxforge.console.commands.hook.subprocess.run") as mock_run,
    ):
        result = runner.invoke(
            app,
            [
                "hook",
                "memory",
                "--event",
                "stop",
                "--harness",
                "claude-code",
                "--interval",
                "2",
                "--palace-path",
                str(tmp_path / "palace"),
                "--namespace",
                "profile/default",
                "--wing",
                "profile-default",
            ],
            input=payload,
        )
    assert result.exit_code == 0, result.output
    response = json.loads(result.stdout)
    assert response["decision"] == "block"
    assert "profile/default" in response["reason"]
    cmd = mock_run.call_args[0][0]
    assert cmd[:6] == [
        "/usr/bin/mempalace",
        "--palace",
        str(tmp_path / "palace"),
        "mine",
        str(tmp_path),
        "--mode",
    ]


def test_memory_precompact_hook_always_blocks() -> None:
    with (
        patch("ctxforge.console.commands.hook.STATE_DIR", Path("/tmp/ctxforge-hook-test")),
        patch("ctxforge.console.commands.hook.shutil.which", return_value="/usr/bin/mempalace"),
        patch("ctxforge.console.commands.hook.subprocess.run") as mock_run,
    ):
        result = runner.invoke(
            app,
            [
                "hook",
                "memory",
                "--event",
                "precompact",
                "--harness",
                "claude-code",
                "--palace-path",
                str(Path("/tmp/palace")),
                "--namespace",
                "profile/default",
                "--wing",
                "profile-default",
            ],
            input="{}",
        )
    assert result.exit_code == 0, result.output
    response = json.loads(result.stdout)
    assert response["decision"] == "block"
    assert "profile/default" in response["reason"]
    mock_run.assert_not_called()
