"""LLM provider dispatch — routes to OpenAI / Anthropic / Google native SDKs."""

from __future__ import annotations

PROVIDER_OPENAI = "openai"
PROVIDER_ANTHROPIC = "anthropic"
PROVIDER_GOOGLE = "google"

_MODEL_PREFIXES: list[tuple[str, str]] = [
    ("gpt-", PROVIDER_OPENAI),
    ("o1-", PROVIDER_OPENAI),
    ("o3-", PROVIDER_OPENAI),
    ("o4-", PROVIDER_OPENAI),
    ("claude-", PROVIDER_ANTHROPIC),
    ("gemini-", PROVIDER_GOOGLE),
]

CLI_DEFAULT_MODELS: dict[str, str] = {
    "claude": "claude-sonnet-4-20250514",
    "codex": "o4-mini",
    "copilot": "gpt-4o",
    "aider": "claude-sonnet-4-20250514",
    "q": "claude-sonnet-4-20250514",
    "goose": "claude-sonnet-4-20250514",
}

DEFAULT_MODEL = "claude-sonnet-4-20250514"


class SDKNotInstalledError(Exception):
    """Raised when the required SDK for a provider is not installed."""


def detect_provider(model: str) -> str:
    """Detect the LLM provider from a model name prefix.

    Raises:
        ValueError: If the model name doesn't match any known prefix.
    """
    lower = model.lower()
    for prefix, provider in _MODEL_PREFIXES:
        if lower.startswith(prefix):
            return provider
    msg = f"Unknown model prefix: {model}"
    raise ValueError(msg)


def get_default_model(active_cli: str | None) -> str:
    """Return the default model for the given active CLI tool."""
    if active_cli and active_cli in CLI_DEFAULT_MODELS:
        return CLI_DEFAULT_MODELS[active_cli]
    return DEFAULT_MODEL


def call_llm(model: str, system_prompt: str, user_prompt: str) -> str:
    """Call an LLM via its native SDK, dispatching by model prefix.

    Falls back to a CLI tool (e.g. ``claude``) when the SDK is not installed
    but a compatible CLI is available on ``PATH``.

    Returns:
        The text response from the model.

    Raises:
        SDKNotInstalledError: If the required SDK is not installed and no CLI
            fallback is available.
        ValueError: If the model prefix is not recognised.
    """
    provider = detect_provider(model)
    try:
        if provider == PROVIDER_OPENAI:
            return _call_openai(model, system_prompt, user_prompt)
        if provider == PROVIDER_ANTHROPIC:
            return _call_anthropic(model, system_prompt, user_prompt)
        return _call_google(model, system_prompt, user_prompt)
    except SDKNotInstalledError:
        return _try_cli_fallback(provider, model, system_prompt, user_prompt)


def _is_o_series(model: str) -> bool:
    """Check if a model is an OpenAI o-series (o1/o3/o4) that doesn't support temperature."""
    lower = model.lower()
    return lower.startswith(("o1-", "o3-", "o4-"))


def _call_openai(model: str, system_prompt: str, user_prompt: str) -> str:
    try:
        from openai import OpenAI  # type: ignore[import-not-found]
    except ImportError:
        raise SDKNotInstalledError(
            "openai is not installed. Install it with: pip install ctxforge[openai]"
        )

    client = OpenAI()
    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    kwargs: dict[str, object] = {"model": model, "messages": messages}
    if not _is_o_series(model):
        kwargs["temperature"] = 0.2
    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content or ""


def _call_anthropic(model: str, system_prompt: str, user_prompt: str) -> str:
    try:
        from anthropic import Anthropic  # type: ignore[import-not-found]
    except ImportError:
        raise SDKNotInstalledError(
            "anthropic is not installed. Install it with: pip install ctxforge[anthropic]"
        )

    client = Anthropic()
    response = client.messages.create(
        model=model,
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
        temperature=0.2,
    )
    block = response.content[0]
    return block.text if hasattr(block, "text") else ""


def _call_google(model: str, system_prompt: str, user_prompt: str) -> str:
    try:
        import google.generativeai as genai  # type: ignore[import-not-found]
    except ImportError:
        raise SDKNotInstalledError(
            "google-generativeai is not installed. Install it with: pip install ctxforge[google]"
        )

    gen_model = genai.GenerativeModel(model, system_instruction=system_prompt)
    response = gen_model.generate_content(user_prompt)
    return response.text or ""


# ---------------------------------------------------------------------------
# CLI fallback
# ---------------------------------------------------------------------------


def _try_cli_fallback(
    provider: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
) -> str:
    """Attempt to call the LLM via a CLI tool when the SDK is missing.

    Raises:
        SDKNotInstalledError: If no CLI fallback is available or it fails.
    """
    from ctxforge.llm.cli_fallback import (
        CLIFallbackError,
        call_via_cli,
        get_fallback_cli,
        is_cli_available,
    )

    cli_name = get_fallback_cli(provider)
    if cli_name is None or not is_cli_available(cli_name):
        raise SDKNotInstalledError(_sdk_install_message(provider, cli_name))

    try:
        return call_via_cli(cli_name, model, system_prompt, user_prompt)
    except CLIFallbackError as exc:
        raise SDKNotInstalledError(
            f"{_sdk_install_message(provider, cli_name)}\n"
            f"CLI fallback also failed: {exc}"
        ) from exc


def _sdk_install_message(provider: str, cli_name: str | None) -> str:
    """Build a user-friendly error message for a missing SDK."""
    install_hint = f"pip install ctxforge[{provider}]"
    if cli_name is not None:
        return (
            f"{provider} SDK is not installed and the '{cli_name}' CLI is not"
            f" available.\nEither install the SDK: {install_hint}\n"
            f"Or install the CLI: https://docs.anthropic.com/en/docs/claude-cli"
        )
    return f"{provider} SDK is not installed. Install it with: {install_hint}"
