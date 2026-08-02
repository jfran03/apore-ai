"""OpenAI-compatible vision clients for MarkItDown image conversion.

MarkItDown's ImageConverter calls ``client.chat.completions.create`` with a
multimodal message that includes a data-URI ``image_url``. NVIDIA NIM already
exposes that shape. Anthropic does not, so this module provides a thin adapter
that translates the request into Anthropic Messages image blocks.

Returned objects are intentionally duck-typed: only the MarkItDown call path is
supported.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import anthropic
from openai import OpenAI

from apore.config.llm import NoLLMConfigured, ResolvedLLM, load_llm_config, resolve_active
from apore.providers.multimodal import (
    MultimodalError,
    parse_data_uri,
    to_anthropic_message as _convert_to_anthropic_message,
)
from apore.providers.nim_adapter import NIMProvider

# Bound MarkItDown image calls so a hung vision request cannot stall upload forever.
VISION_TIMEOUT_SECONDS = 60.0
VISION_MAX_TOKENS = 2048


class VisionClientError(RuntimeError):
    """Raised when a vision request cannot be completed."""


def _to_anthropic_message(message: dict) -> dict:
    """Backward-compatible wrapper used by MarkItDown tests."""
    try:
        return _convert_to_anthropic_message(message)
    except MultimodalError as exc:
        text = str(exc).replace("Unsupported image media type", "Unsupported vision media type")
        raise VisionClientError(text) from exc


def _source_from_data_uri(url: str) -> dict:
    """Backward-compatible wrapper used by MarkItDown tests."""
    import base64

    try:
        media_type, raw = parse_data_uri(url)
    except MultimodalError as exc:
        text = str(exc).replace("Unsupported image media type", "Unsupported vision media type")
        raise VisionClientError(text) from exc
    return {
        "type": "base64",
        "media_type": media_type,
        "data": base64.b64encode(raw).decode("ascii"),
    }


@dataclass
class _MessageContent:
    content: str | None


@dataclass
class _Choice:
    message: _MessageContent


@dataclass
class _CompletionResponse:
    choices: list[_Choice]


class _AnthropicCompletions:
    def __init__(self, client: anthropic.Anthropic) -> None:
        self._client = client

    def create(self, *, model: str, messages: list[dict], **kwargs: Any) -> _CompletionResponse:
        if not messages:
            raise VisionClientError("Vision request had no messages.")
        # MarkItDown sends a single user turn with mixed text + image_url parts.
        try:
            converted = [_to_anthropic_message(msg) for msg in messages]
        except VisionClientError:
            raise
        try:
            response = self._client.messages.create(
                model=model,
                max_tokens=int(kwargs.get("max_tokens") or VISION_MAX_TOKENS),
                messages=converted,
            )
        except Exception as exc:  # Anthropic raises several exception types
            raise VisionClientError(
                f"Vision model request failed ({type(exc).__name__}): {exc}. "
                "Confirm the configured Anthropic model supports image input."
            ) from exc
        text_parts = [
            block.text
            for block in response.content
            if getattr(block, "type", None) == "text" and getattr(block, "text", None)
        ]
        content = "\n".join(text_parts).strip() if text_parts else None
        return _CompletionResponse(choices=[_Choice(message=_MessageContent(content=content))])


class _AnthropicChat:
    def __init__(self, client: anthropic.Anthropic) -> None:
        self.completions = _AnthropicCompletions(client)


class AnthropicVisionClient:
    """Duck-types the OpenAI chat.completions surface MarkItDown expects."""

    def __init__(self, api_key: str) -> None:
        self._client = anthropic.Anthropic(
            api_key=api_key,
            timeout=VISION_TIMEOUT_SECONDS,
        )
        self.chat = _AnthropicChat(self._client)


class _TimedOpenAICompletions:
    """Wrap OpenAI completions so MarkItDown calls get a max_tokens bound."""

    def __init__(self, completions: Any) -> None:
        self._completions = completions

    def create(self, *, model: str, messages: list[dict], **kwargs: Any) -> Any:
        if "max_tokens" not in kwargs:
            kwargs["max_tokens"] = VISION_MAX_TOKENS
        try:
            return self._completions.create(model=model, messages=messages, **kwargs)
        except Exception as exc:
            raise VisionClientError(
                f"Vision model request failed ({type(exc).__name__}): {exc}. "
                "Confirm the configured model supports image input."
            ) from exc


class _TimedOpenAIChat:
    def __init__(self, chat: Any) -> None:
        self.completions = _TimedOpenAICompletions(chat.completions)


class TimedOpenAIVisionClient:
    """OpenAI client with timeout + max_tokens defaults for MarkItDown."""

    def __init__(self, client: OpenAI) -> None:
        self._client = client
        self.chat = _TimedOpenAIChat(client.chat)


def build_vision_client(
    resolved: ResolvedLLM | None = None,
) -> tuple[Any, str]:
    """Return ``(llm_client, model)`` for MarkItDown image conversion."""
    active = resolved or resolve_active(load_llm_config())
    if active.provider_name == "anthropic":
        return AnthropicVisionClient(active.api_key), active.model
    if active.provider_name == "nim":
        client = OpenAI(
            base_url=NIMProvider._BASE_URL,
            api_key=active.api_key,
            timeout=VISION_TIMEOUT_SECONDS,
        )
        return TimedOpenAIVisionClient(client), active.model
    raise NoLLMConfigured(
        f"Provider {active.provider_name!r} does not support vision image conversion."
    )
