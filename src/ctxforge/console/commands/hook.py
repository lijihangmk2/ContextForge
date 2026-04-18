"""Internal hook commands used by ctxforge-managed integrations."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import typer

hook_app = typer.Typer(help="Internal hook utilities.", no_args_is_help=True)

STATE_DIR = Path.home() / ".ctxforge" / "hook_state"


@hook_app.command("memory")
def memory_command(
    event: str = typer.Option(..., "--event"),
    harness: str = typer.Option(..., "--harness"),
    interval: int = typer.Option(15, "--interval"),
    palace_path: str = typer.Option("", "--palace-path"),
    namespace: str = typer.Option("", "--namespace"),
    wing: str = typer.Option("", "--wing"),
) -> None:
    """Run the ctxforge memory hook and print JSON to stdout."""
    payload = _read_stdin_json()
    if event == "stop":
        _run_stop_hook(
            payload,
            harness=harness,
            interval=max(1, interval),
            palace_path=palace_path,
            namespace=namespace,
            wing=wing,
        )
        return
    if event == "precompact":
        _run_precompact_hook(
            payload,
            harness=harness,
            palace_path=palace_path,
            namespace=namespace,
            wing=wing,
        )
        return
    raise typer.Exit(1)


def _read_stdin_json() -> dict[str, object]:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return {}
    return data if isinstance(data, dict) else {}


def _run_stop_hook(
    payload: dict[str, object],
    *,
    harness: str,
    interval: int,
    palace_path: str,
    namespace: str,
    wing: str,
) -> None:
    parsed = _parse_payload(payload, harness)
    stop_hook_active = bool(parsed["stop_hook_active"])
    transcript_path = str(parsed["transcript_path"])
    session_id = str(parsed["session_id"])
    if stop_hook_active:
        _output({})
        return

    exchange_count = _count_human_messages(transcript_path)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    last_save_file = STATE_DIR / f"{session_id}_last_save"
    last_save = 0
    if last_save_file.exists():
        try:
            last_save = int(last_save_file.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            last_save = 0
    since_last = exchange_count - last_save
    if since_last >= interval and exchange_count > 0:
        last_save_file.write_text(str(exchange_count), encoding="utf-8")
        _auto_ingest_transcript(transcript_path, palace_path=palace_path, wing=wing)
        _output(
            {
                "decision": "block",
                "reason": (
                    "AUTO-SAVE checkpoint. Save key topics, decisions, quotes, code, "
                    f"and unresolved work from this session to MemPalace using namespace "
                    f'"{namespace}" and wing "{wing}". '
                    "Use only the current profile memory. Continue the conversation after saving."
                ),
            }
        )
        return
    _output({})


def _run_precompact_hook(
    payload: dict[str, object],
    *,
    harness: str,
    palace_path: str,
    namespace: str,
    wing: str,
) -> None:
    parsed = _parse_payload(payload, harness)
    transcript_path = str(parsed["transcript_path"])
    _auto_ingest_transcript(transcript_path, palace_path=palace_path, wing=wing)
    _output(
        {
            "decision": "block",
            "reason": (
                "COMPACTION IMMINENT. Save ALL topics, decisions, quotes, code, and "
                f"important context from this session to MemPalace using namespace "
                f'"{namespace}" and wing "{wing}". '
                "Be thorough, then allow compaction to proceed."
            ),
        }
    )


def _parse_payload(payload: dict[str, object], harness: str) -> dict[str, object]:
    if harness != "claude-code":
        return {
            "session_id": "unknown",
            "stop_hook_active": False,
            "transcript_path": "",
        }
    raw_session_id = str(payload.get("session_id", "unknown"))
    return {
        "session_id": _sanitize_session_id(raw_session_id),
        "stop_hook_active": bool(payload.get("stop_hook_active", False)),
        "transcript_path": str(payload.get("transcript_path", "")),
    }


def _sanitize_session_id(value: str) -> str:
    sanitized = re.sub(r"[^a-zA-Z0-9_-]", "", value)
    return sanitized or "unknown"


def _count_human_messages(transcript_path: str) -> int:
    path = Path(transcript_path).expanduser()
    if not path.is_file():
        return 0
    count = 0
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                message = entry.get("message", {})
                if not isinstance(message, dict) or message.get("role") != "user":
                    continue
                content = message.get("content", "")
                if isinstance(content, str) and "<command-message>" in content:
                    continue
                if isinstance(content, list):
                    text = " ".join(
                        item.get("text", "")
                        for item in content
                        if isinstance(item, dict)
                    )
                    if "<command-message>" in text:
                        continue
                count += 1
    except OSError:
        return 0
    return count


def _auto_ingest_transcript(transcript_path: str, *, palace_path: str, wing: str) -> None:
    transcript = Path(transcript_path).expanduser()
    if not transcript.is_file():
        return
    mempalace = shutil.which("mempalace")
    if not mempalace:
        return

    convo_dir = str(transcript.parent)
    cmd = [
        mempalace,
        "--palace",
        palace_path,
        "mine",
        convo_dir,
        "--mode",
        "convos",
        "--wing",
        wing,
        "--agent",
        "ctxforge",
    ]
    try:
        subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return


def _output(data: dict[str, object]) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))
