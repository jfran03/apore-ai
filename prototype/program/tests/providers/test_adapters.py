"""Tests for AnthropicProvider and NIMProvider adapters."""

import pytest

from apore.config.llm import (
    LLMConfig,
    get_anthropic_api_key,
    get_nim_api_key,
    save_llm_config,
)
from apore.providers.base import Provider
from apore.providers.anthropic_adapter import AnthropicProvider
from apore.providers.nim_adapter import NIMProvider
from apore.providers import get_provider

# ---------------------------------------------------------------------------
# Contract tests (no API calls)
# ---------------------------------------------------------------------------

def test_anthropic_provider_is_provider(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    assert isinstance(AnthropicProvider(), Provider)


def test_nim_provider_is_provider(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "test-key")
    assert isinstance(NIMProvider(), Provider)


def test_get_provider_anthropic(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    provider = get_provider("anthropic")
    assert isinstance(provider, AnthropicProvider)


def test_get_provider_nim(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "test-key")
    provider = get_provider("nim")
    assert isinstance(provider, NIMProvider)


def test_get_provider_unknown_raises():
    with pytest.raises(ValueError, match="Unknown provider"):
        get_provider("unknown")


def test_nim_provider_reads_disk_config(tmp_path, monkeypatch):
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    save_llm_config(
        LLMConfig(anthropic_api_key=None, nim_api_key="nvapi-disk-key", model=""),
        program_root=tmp_path,
    )
    monkeypatch.setattr("apore.config.llm.get_program_root", lambda: tmp_path)
    assert isinstance(NIMProvider(), Provider)


def test_anthropic_provider_reads_disk_config(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    save_llm_config(
        LLMConfig(anthropic_api_key="sk-ant-disk-key", nim_api_key=None, model=""),
        program_root=tmp_path,
    )
    monkeypatch.setattr("apore.config.llm.get_program_root", lambda: tmp_path)
    assert isinstance(AnthropicProvider(), Provider)


def test_nim_provider_raises_without_key(monkeypatch):
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.setattr(
        "apore.config.llm.get_program_root",
        lambda: __import__("pathlib").Path("/nonexistent-apore-config-root"),
    )
    with pytest.raises(ValueError, match="nim_api_key"):
        NIMProvider()


def test_anthropic_provider_raises_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(
        "apore.config.llm.get_program_root",
        lambda: __import__("pathlib").Path("/nonexistent-apore-config-root"),
    )
    with pytest.raises(ValueError, match="anthropic_api_key"):
        AnthropicProvider()


# ---------------------------------------------------------------------------
# Integration tests (real API calls — skipped without keys)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not get_anthropic_api_key(), reason="Anthropic API key not configured")
def test_anthropic_live():
    from apore.providers.anthropic_adapter import DEFAULT_MODEL
    provider = AnthropicProvider()
    result = provider.invoke(
        system_prompt="You are a helpful assistant.",
        messages=[{"role": "user", "content": "Say hello in one word."}],
        model=DEFAULT_MODEL,
        config={"max_tokens": 16},
    )
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.skipif(not get_nim_api_key(), reason="NVIDIA NIM API key not configured")
def test_nim_live():
    from apore.providers.nim_adapter import DEFAULT_MODEL
    provider = NIMProvider()
    result = provider.invoke(
        system_prompt="You are a helpful assistant.",
        messages=[{"role": "user", "content": "Say hello in one word."}],
        model=DEFAULT_MODEL,
        config={"max_tokens": 16},
    )
    assert isinstance(result, str)
    assert len(result) > 0
