"""Tests for MarkItDown vision client adapters."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from apore.config.llm import LLMConfig, NoLLMConfigured, ResolvedLLM
from apore.providers.vision_client import (
    AnthropicVisionClient,
    VisionClientError,
    _source_from_data_uri,
    _to_anthropic_message,
    build_vision_client,
)


def test_source_from_data_uri_accepts_jpeg():
    raw = b"\xff\xd8\xff\xe0" + b"abcd"
    import base64

    data = base64.b64encode(raw).decode("ascii")
    source = _source_from_data_uri(f"data:image/jpeg;base64,{data}")
    assert source["type"] == "base64"
    assert source["media_type"] == "image/jpeg"
    assert source["data"] == data


def test_source_from_data_uri_rejects_svg():
    import base64

    data = base64.b64encode(b"<svg/>").decode("ascii")
    with pytest.raises(VisionClientError, match="Unsupported vision media type"):
        _source_from_data_uri(f"data:image/svg+xml;base64,{data}")


def test_to_anthropic_message_translates_image_url():
    import base64

    data = base64.b64encode(b"\x89PNG\r\n\x1a\n").decode("ascii")
    msg = _to_anthropic_message(
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Describe"},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{data}"},
                },
            ],
        }
    )
    assert msg["role"] == "user"
    assert msg["content"][0] == {"type": "text", "text": "Describe"}
    assert msg["content"][1]["type"] == "image"
    assert msg["content"][1]["source"]["media_type"] == "image/png"


def test_build_vision_client_anthropic(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "apore.providers.vision_client.resolve_active",
        lambda config: ResolvedLLM(
            provider_name="anthropic", model="claude-sonnet-4-5", api_key="sk-ant-x"
        ),
    )
    client, model = build_vision_client()
    assert isinstance(client, AnthropicVisionClient)
    assert model == "claude-sonnet-4-5"


def test_build_vision_client_nim(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "apore.providers.vision_client.resolve_active",
        lambda config: ResolvedLLM(
            provider_name="nim",
            model="meta/llama-3.2-90b-vision-instruct",
            api_key="nvapi-x",
        ),
    )
    client, model = build_vision_client()
    assert hasattr(client, "chat")
    assert hasattr(client.chat, "completions")
    assert model.startswith("meta/")


def test_build_vision_client_requires_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "apore.providers.vision_client.load_llm_config",
        lambda: LLMConfig(),
    )
    monkeypatch.setattr(
        "apore.providers.vision_client.resolve_active",
        lambda config: (_ for _ in ()).throw(NoLLMConfigured("none")),
    )
    with pytest.raises(NoLLMConfigured):
        build_vision_client()


def test_anthropic_completions_create_invokes_messages(monkeypatch: pytest.MonkeyPatch):
    import base64

    calls: list[dict] = []

    class FakeMessages:
        def create(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                content=[SimpleNamespace(type="text", text="Extracted text")]
            )

    class FakeAnthropic:
        def __init__(self, *args, **kwargs):
            self.messages = FakeMessages()

    monkeypatch.setattr("apore.providers.vision_client.anthropic.Anthropic", FakeAnthropic)
    client = AnthropicVisionClient("sk-ant-test")
    data = base64.b64encode(b"\xff\xd8\xff\xe0").decode("ascii")
    response = client.chat.completions.create(
        model="claude-sonnet-4-5",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe"},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{data}"},
                    },
                ],
            }
        ],
    )
    assert response.choices[0].message.content == "Extracted text"
    assert calls[0]["model"] == "claude-sonnet-4-5"
    assert calls[0]["messages"][0]["content"][1]["type"] == "image"
