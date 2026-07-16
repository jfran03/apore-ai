"""Persisted BYOK LLM configuration and provider resolution."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from apore.runtime.paths import get_program_root

CONFIG_DIRNAME = ".apore"
CONFIG_FILENAME = "config.json"

DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-5"
DEFAULT_NIM_MODEL = "meta/llama-3.3-70b-instruct"

DEFAULT_MODELS = {
    "anthropic": DEFAULT_ANTHROPIC_MODEL,
    "nim": DEFAULT_NIM_MODEL,
}


class NoLLMConfigured(ValueError):
    """Raised when no provider keys are configured."""


@dataclass
class LLMConfig:
    anthropic_api_key: str | None = None
    nim_api_key: str | None = None
    model: str = ""


@dataclass
class ResolvedLLM:
    provider_name: str
    model: str
    api_key: str


def get_config_path(program_root: Path | None = None) -> Path:
    root = program_root or get_program_root()
    return root / CONFIG_DIRNAME / CONFIG_FILENAME


def _clean_key(raw: str | None) -> str | None:
    if raw is None:
        return None
    value = raw.strip()
    return value if value else None


def _clean_model(raw: str | None) -> str:
    if raw is None:
        return ""
    return raw.strip()


def _read_disk_config(path: Path) -> dict:
    if not path.exists():
        return {}
    raw = path.read_text(encoding="utf-8")
    if not raw.strip():
        return {}
    data = json.loads(raw)
    if not isinstance(data, dict):
        return {}
    return data


def load_llm_config(program_root: Path | None = None) -> LLMConfig:
    path = get_config_path(program_root)
    data = _read_disk_config(path)

    anthropic_api_key = _clean_key(data.get("anthropic_api_key"))
    nim_api_key = _clean_key(data.get("nim_api_key"))
    model = _clean_model(data.get("model"))

    if anthropic_api_key is None:
        anthropic_api_key = _clean_key(os.environ.get("ANTHROPIC_API_KEY"))
    if nim_api_key is None:
        nim_api_key = _clean_key(os.environ.get("NVIDIA_API_KEY"))

    return LLMConfig(
        anthropic_api_key=anthropic_api_key,
        nim_api_key=nim_api_key,
        model=model,
    )


def save_llm_config(config: LLMConfig, program_root: Path | None = None) -> None:
    path = get_config_path(program_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(config), indent=2), encoding="utf-8")


def key_is_set(value: str | None) -> bool:
    return _clean_key(value) is not None


def key_hint(value: str | None) -> str | None:
    key = _clean_key(value)
    if key is None:
        return None
    if len(key) <= 4:
        return "*" * len(key)
    return f"***{key[-4:]}"


def resolve_active(config: LLMConfig) -> ResolvedLLM:
    anthropic_key = _clean_key(config.anthropic_api_key)
    nim_key = _clean_key(config.nim_api_key)

    if anthropic_key:
        provider_name = "anthropic"
        api_key = anthropic_key
    elif nim_key:
        provider_name = "nim"
        api_key = nim_key
    else:
        raise NoLLMConfigured(
            "No API key configured. Add an Anthropic or NVIDIA NIM key in Settings."
        )

    model_override = _clean_model(config.model)
    model = model_override if model_override else DEFAULT_MODELS[provider_name]
    return ResolvedLLM(provider_name=provider_name, model=model, api_key=api_key)


def get_active_provider(program_root: Path | None = None) -> str | None:
    try:
        return resolve_active(load_llm_config(program_root)).provider_name
    except NoLLMConfigured:
        return None


def get_active_model(program_root: Path | None = None) -> str | None:
    try:
        return resolve_active(load_llm_config(program_root)).model
    except NoLLMConfigured:
        return None


def get_anthropic_api_key(program_root: Path | None = None) -> str | None:
    return _clean_key(load_llm_config(program_root).anthropic_api_key)


def get_nim_api_key(program_root: Path | None = None) -> str | None:
    return _clean_key(load_llm_config(program_root).nim_api_key)


def get_provider_config(program_root: Path | None = None) -> dict:
    config = load_llm_config(program_root)
    try:
        resolved = resolve_active(config)
        active_provider = resolved.provider_name
        active_model = resolved.model
    except NoLLMConfigured:
        active_provider = None
        active_model = None
    return {
        "anthropic_api_key_set": key_is_set(config.anthropic_api_key),
        "anthropic_api_key_hint": key_hint(config.anthropic_api_key),
        "nim_api_key_set": key_is_set(config.nim_api_key),
        "nim_api_key_hint": key_hint(config.nim_api_key),
        "model": config.model,
        "active_provider": active_provider,
        "active_model": active_model,
    }


def set_provider_config(
    *,
    anthropic_api_key: str | None = None,
    nim_api_key: str | None = None,
    model: str | None = None,
    program_root: Path | None = None,
) -> dict:
    config = load_llm_config(program_root)
    if anthropic_api_key is not None:
        config.anthropic_api_key = _clean_key(anthropic_api_key)
    if nim_api_key is not None:
        config.nim_api_key = _clean_key(nim_api_key)
    if model is not None:
        config.model = _clean_model(model)
    save_llm_config(config, program_root)
    return get_provider_config(program_root)

