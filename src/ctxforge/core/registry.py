"""MCP Registry client — search and fetch tool configs from the official registry."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field

_BASE_URL = "https://registry.modelcontextprotocol.io/v0"
_TIMEOUT = 15


@dataclass
class RegistryPackage:
    """Resolved package info from the MCP registry."""

    name: str
    description: str
    registry_type: str  # "npm" | "pypi"
    identifier: str  # e.g. "tavily-mcp", "@anthropic-ai/mcp-server-puppeteer"
    version: str
    env_vars: list[str] = field(default_factory=list)
    env_descriptions: dict[str, str] = field(default_factory=dict)

    @property
    def command(self) -> str:
        if self.registry_type == "npm":
            return "npx"
        if self.registry_type == "pypi":
            return "uvx"
        return self.identifier

    @property
    def args(self) -> list[str]:
        if self.registry_type == "npm":
            return ["-y", f"{self.identifier}@latest"]
        if self.registry_type == "pypi":
            return [self.identifier]
        return []

    @property
    def short_name(self) -> str:
        """Extract a short tool name from the registry name.

        e.g. 'io.github.anthropics/puppeteer-mcp' -> 'puppeteer-mcp'
        """
        return self.name.rsplit("/", 1)[-1] if "/" in self.name else self.name


class RegistryError(Exception):
    pass


_GITHUB_RE = r"^https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$"


def is_github_url(value: str) -> bool:
    """Check if a string looks like a GitHub repository URL."""
    import re

    return bool(re.match(_GITHUB_RE, value))


def _parse_server_json(data: dict[str, object]) -> RegistryPackage | None:
    """Parse a server.json dict into a RegistryPackage."""
    packages = data.get("packages", [])
    if not isinstance(packages, list):
        return None
    pkg = _pick_package(packages)  # type: ignore[arg-type]
    if pkg is None:
        return None

    env_vars: list[str] = []
    env_descs: dict[str, str] = {}
    for ev in pkg.get("environmentVariables", []):  # type: ignore[union-attr]
        if isinstance(ev, dict):
            name = ev.get("name", "")
            if name:
                env_vars.append(name)
                desc = ev.get("description", "")
                if desc:
                    env_descs[name] = desc

    return RegistryPackage(
        name=str(data.get("name", "")),
        description=str(data.get("description", "")),
        registry_type=str(pkg.get("registryType", "")),
        identifier=str(pkg.get("identifier", "")),
        version=str(pkg.get("version", "")),
        env_vars=env_vars,
        env_descriptions=env_descs,
    )


def fetch_from_github(url: str) -> RegistryPackage:
    """Fetch server.json from a GitHub repository URL."""
    import re

    m = re.match(_GITHUB_RE, url)
    if not m:
        raise RegistryError(f"Not a valid GitHub URL: {url}")

    owner, repo = m.group(1), m.group(2)

    # Try common branches and locations
    candidates = [
        f"https://raw.githubusercontent.com/{owner}/{repo}/main/server.json",
        f"https://raw.githubusercontent.com/{owner}/{repo}/master/server.json",
    ]

    data: dict[str, object] | None = None
    for raw_url in candidates:
        try:
            req = urllib.request.Request(raw_url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                data = json.loads(resp.read())
            break
        except urllib.error.HTTPError:
            continue
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RegistryError(f"Failed to fetch server.json: {exc}") from exc

    if data is None:
        raise RegistryError(
            f"No server.json found in {owner}/{repo}. "
            "This project may not follow the MCP server.json standard."
        )

    pkg = _parse_server_json(data)
    if pkg is None:
        raise RegistryError(f"server.json in {owner}/{repo} has no usable package definition.")
    return pkg


def search(query: str, *, limit: int = 10) -> list[RegistryPackage]:
    """Search the MCP registry for servers matching *query*."""
    url = f"{_BASE_URL}/servers?search={urllib.request.quote(query)}&limit={limit}"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            data = json.loads(resp.read())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RegistryError(f"Failed to query MCP registry: {exc}") from exc

    results: list[RegistryPackage] = []
    for entry in data.get("servers", []):
        server = entry.get("server", {})
        packages = server.get("packages", [])
        # Pick the first stdio package (prefer npm over others)
        pkg = _pick_package(packages)
        if pkg is None:
            continue

        env_vars: list[str] = []
        env_descs: dict[str, str] = {}
        for ev in pkg.get("environmentVariables", []):
            name = ev.get("name", "")
            if name:
                env_vars.append(name)
                desc = ev.get("description", "")
                if desc:
                    env_descs[name] = desc

        results.append(
            RegistryPackage(
                name=server.get("name", ""),
                description=server.get("description", ""),
                registry_type=pkg.get("registryType", ""),
                identifier=pkg.get("identifier", ""),
                version=pkg.get("version", ""),
                env_vars=env_vars,
                env_descriptions=env_descs,
            )
        )
    return results


def _pick_package(packages: list[dict[str, object]]) -> dict[str, object] | None:
    """Pick the best package entry — prefer npm stdio."""
    stdio_pkgs = [
        p for p in packages
        if isinstance(p.get("transport"), dict)
        and p["transport"].get("type") == "stdio"  # type: ignore[union-attr]
    ]
    if not stdio_pkgs:
        return packages[0] if packages else None
    # Prefer npm
    for p in stdio_pkgs:
        if p.get("registryType") == "npm":
            return p
    return stdio_pkgs[0]
