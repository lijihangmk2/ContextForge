"""Memory integration helpers for profile-scoped long-term context."""

from __future__ import annotations

import importlib.util
import re
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from ctxforge.spec.schema import MempalaceSection, ProjectConfig

DEFAULT_RESULTS = 5


@dataclass(frozen=True)
class MemoryBinding:
    """Resolved memory namespace for one profile."""

    provider: str
    namespace: str
    wing: str
    palace_path: Path
    checkpoint_interval: int
    cross_profile_search: bool


@dataclass(frozen=True)
class MemoryPreloadResult:
    """Resolved preload text for system prompt injection."""

    status: str
    content: str = ""

    @property
    def ok(self) -> bool:
        return self.status == "loaded" and bool(self.content.strip())


@dataclass(frozen=True)
class MemoryRuntimeStatus:
    """Runtime availability for MemPalace integration."""

    ok: bool
    message: str = ""


def resolve_memory_binding(
    project_root: Path,
    profile_name: str,
    project_config: ProjectConfig,
) -> MemoryBinding | None:
    """Resolve the configured profile memory binding."""
    mempalace = project_config.mempalace
    if not _is_memory_enabled(mempalace):
        return None

    namespace = _default_namespace(profile_name)
    wing = _default_wing(profile_name)
    palace_path = _resolve_palace_path(project_root, mempalace)

    return MemoryBinding(
        provider="mempalace",
        namespace=namespace,
        wing=wing,
        palace_path=palace_path,
        checkpoint_interval=max(1, mempalace.checkpoint_interval),
        cross_profile_search=False,
    )


def load_memory_preload(
    binding: MemoryBinding | None,
    *,
    command: str = "mempalace",
    results: int = DEFAULT_RESULTS,
) -> MemoryPreloadResult:
    """Load memory context from MemPalace for a new session."""
    if binding is None:
        return MemoryPreloadResult(status="disabled")

    if binding.provider != "mempalace":
        return MemoryPreloadResult(status="unsupported")

    executable = shutil.which(command)
    if executable is None:
        return MemoryPreloadResult(status="unavailable")

    query = _build_search_query(binding.namespace)
    cmd = [
        executable,
        "--palace",
        str(binding.palace_path),
        "search",
        query,
        "--wing",
        binding.wing,
        "--results",
        str(results),
    ]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if proc.returncode != 0:
        return MemoryPreloadResult(status="error")

    raw_stdout = proc.stdout if isinstance(proc.stdout, str) else ""
    content = raw_stdout.strip()
    if not content:
        return MemoryPreloadResult(status="empty")

    return MemoryPreloadResult(
        status="loaded",
        content=_format_memory_context(binding.namespace, content),
    )


def validate_memory_runtime(binding: MemoryBinding | None) -> MemoryRuntimeStatus:
    """Validate that MemPalace is installed for an enabled profile."""
    if binding is None:
        return MemoryRuntimeStatus(ok=True)

    return validate_mempalace_installation()


def validate_mempalace_installation() -> MemoryRuntimeStatus:
    """Validate that the MemPalace CLI and Python package are installed."""
    cli_path = _find_mempalace_cli()
    if cli_path is None:
        return MemoryRuntimeStatus(
            ok=False,
            message=(
                "MemPalace is enabled for this project, but the `mempalace` CLI "
                "is not installed or not on PATH."
            ),
        )

    if _resolve_mempalace_module_runner(cli_path) is None:
        return MemoryRuntimeStatus(
            ok=False,
            message=(
                "MemPalace is enabled for this project, but ctxforge could not resolve "
                "a Python runtime capable of importing `mempalace.mcp_server`."
            ),
        )

    return MemoryRuntimeStatus(ok=True)


def build_memory_system_prompt(binding: MemoryBinding | None) -> str:
    """Build static memory instructions for the active profile."""
    if binding is None:
        return ""

    return "\n".join(
        [
            "[Memory Namespace]",
            f"Provider: {binding.provider}",
            f"Namespace: {binding.namespace}",
            f"Wing: {binding.wing}",
            "Use this namespace as the long-term memory for the current profile.",
            "When the session asks you to save memory, write only to this profile memory.",
            (
                "If memory results conflict with current key files or work-record "
                "files, trust the files."
            ),
        ]
    )


def build_mempalace_mcp_server(binding: MemoryBinding | None) -> dict[str, dict[str, object]]:
    """Build the MemPalace MCP server definition for the active profile."""
    if binding is None:
        return {}

    cli_path = _find_mempalace_cli()
    runner = _resolve_mempalace_module_runner(cli_path)
    if runner is None:
        return {}

    return {
        "ctxforge-memory-mempalace": {
            "command": runner[0],
            "args": [*runner[1:], "--palace", str(binding.palace_path)],
        }
    }


def _is_memory_enabled(mempalace: MempalaceSection) -> bool:
    return mempalace.enabled


def _resolve_palace_path(project_root: Path, mempalace: MempalaceSection) -> Path:
    configured = mempalace.palace_path.strip()
    if configured:
        return Path(configured).expanduser()
    return project_root / ".ctxforge" / "memory" / "mempalace"


def _default_namespace(profile_name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", profile_name.strip().lower()).strip("-")
    return f"profile/{slug or 'default'}"


def _default_wing(profile_name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", profile_name.strip().lower()).strip("-")
    return f"profile-{slug or 'default'}"


def _build_search_query(namespace: str) -> str:
    return (
        f"agent namespace {namespace}; load past decisions, user preferences, "
        "unfinished work, recurring constraints, and stable context"
    )


def _format_memory_context(namespace: str, content: str) -> str:
    return "\n".join(
        [
            "[Memory Context]",
            f"Namespace: {namespace}",
            "Use this as supplemental long-term memory. If it conflicts with current key files "
            "or work-record files, trust the files.",
            content,
        ]
    )


def _find_mempalace_cli() -> Path | None:
    executable = shutil.which("mempalace")
    if not executable:
        return None
    return Path(executable)


def _resolve_mempalace_module_runner(cli_path: Path | None) -> list[str] | None:
    if importlib.util.find_spec("mempalace") is not None:
        return [sys.executable, "-m", "mempalace.mcp_server"]
    if cli_path is None:
        return None
    return _module_runner_from_shebang(cli_path)


def _module_runner_from_shebang(cli_path: Path) -> list[str] | None:
    try:
        first_line = cli_path.read_text(encoding="utf-8").splitlines()[0]
    except (OSError, IndexError, UnicodeDecodeError):
        return None
    if not first_line.startswith("#!"):
        return None

    parts = shlex.split(first_line[2:].strip())
    if not parts:
        return None

    if Path(parts[0]).name == "env":
        if len(parts) < 2:
            return None
        python_cmd = shutil.which(parts[1])
        if not python_cmd:
            return None
        return [python_cmd, "-m", "mempalace.mcp_server"]

    interpreter = Path(parts[0]).expanduser()
    if not interpreter.exists():
        return None
    return [str(interpreter), "-m", "mempalace.mcp_server"]
