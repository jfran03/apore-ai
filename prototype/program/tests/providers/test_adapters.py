"""Tests for AnthropicProvider and NIMProvider adapters."""

import os

import pytest

from apore.providers.base import Provider
from apore.providers.anthropic_adapter import AnthropicProvider
from apore.providers.nim_adapter import NIMProvider
from apore.providers import get_provider

# ---------------------------------------------------------------------------
# Contract tests (no API calls)
# ---------------------------------------------------------------------------

def test_anthropic_provider_is_provider():
    assert isinstance(AnthropicProvider(), Provider)


def test_nim_provider_is_provider():
    assert isinstance(NIMProvider(), Provider)


def test_get_provider_anthropic():
    provider = get_provider("anthropic")
    assert isinstance(provider, AnthropicProvider)


def test_get_provider_nim():
    provider = get_provider("nim")
    assert isinstance(provider, NIMProvider)


def test_get_provider_unknown_raises():
    with pytest.raises(ValueError, match="Unknown provider"):
        get_provider("unknown")


# ---------------------------------------------------------------------------
# Integration tests (real API calls — skipped without keys)
# ---------------------------------------------------------------------------

ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY")
NVIDIA_KEY = os.environ.get("NVIDIA_API_KEY")


@pytest.mark.skipif(not ANTHROPIC_KEY, reason="ANTHROPIC_API_KEY not set")
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


@pytest.mark.skipif(not NVIDIA_KEY, reason="NVIDIA_API_KEY not set")
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
