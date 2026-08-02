"""Tests for multimodal message helpers."""

from __future__ import annotations

import base64

import pytest

from apore.providers.multimodal import (
    MultimodalError,
    build_user_content,
    content_display_text,
    parse_data_uri,
    persistable_content,
    to_anthropic_message,
    validate_learner_image,
)


def _png_uri() -> str:
    raw = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
    return f"data:image/png;base64,{base64.b64encode(raw).decode('ascii')}"


def test_validate_png_data_uri():
    uri = validate_learner_image(_png_uri())
    assert uri.startswith("data:image/png;base64,")


def test_reject_svg():
    data = base64.b64encode(b"<svg/>").decode("ascii")
    with pytest.raises(MultimodalError, match="Unsupported image media type"):
        parse_data_uri(f"data:image/svg+xml;base64,{data}")


def test_build_user_content_with_image():
    content = build_user_content(text="Check this", image_data_uri=_png_uri())
    assert isinstance(content, list)
    assert content[0]["type"] == "text"
    assert content[1]["type"] == "image_url"


def test_display_and_persist_collapse_images():
    content = build_user_content(text="", image_data_uri=_png_uri())
    assert content_display_text(content) == "[Scratchpad selection]"
    assert persistable_content(content) == "[Scratchpad selection]"


def test_to_anthropic_message():
    content = build_user_content(text="Describe", image_data_uri=_png_uri())
    msg = to_anthropic_message({"role": "user", "content": content})
    assert msg["content"][0]["type"] == "text"
    assert msg["content"][1]["type"] == "image"
    assert msg["content"][1]["source"]["media_type"] == "image/png"
