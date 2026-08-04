"""Shared multimodal message helpers for vision-capable provider calls.

OpenAI-style ``image_url`` data URIs are the wire format used by MarkItDown
and scratchpad turns. Anthropic Messages needs a thin conversion to
``image`` + ``base64`` source blocks.
"""

from __future__ import annotations

import base64
import re
from typing import Any
from urllib.parse import urlparse

_DATA_URI_RE = re.compile(
    r"^data:(?P<media_type>[^;]+);base64,(?P<data>.+)$",
    re.DOTALL,
)

ALLOWED_IMAGE_MEDIA_TYPES = frozenset({"image/jpeg", "image/png"})
# Scratchpad crops should stay well below chapter-source limits.
MAX_TURN_IMAGE_BYTES = 4 * 1024 * 1024


class MultimodalError(ValueError):
    """Raised when a multimodal message or data URI is invalid."""


def parse_data_uri(url: str) -> tuple[str, bytes]:
    """Return ``(media_type, raw_bytes)`` for a base64 data URI."""
    match = _DATA_URI_RE.match((url or "").strip())
    if not match:
        parsed = urlparse(url or "")
        if parsed.scheme in {"http", "https"}:
            raise MultimodalError(
                "Remote image URLs are not supported; send a base64 data URI."
            )
        raise MultimodalError("Image must be a base64 data URI.")
    media_type = match.group("media_type").strip().lower()
    if media_type not in ALLOWED_IMAGE_MEDIA_TYPES:
        raise MultimodalError(f"Unsupported image media type: {media_type!r}")
    data = match.group("data").strip()
    try:
        raw = base64.b64decode(data, validate=True)
    except Exception as exc:
        raise MultimodalError("Image data URI was not valid base64.") from exc
    if len(raw) == 0:
        raise MultimodalError("Image data URI was empty.")
    if len(raw) > MAX_TURN_IMAGE_BYTES:
        raise MultimodalError(
            f"Image exceeds the {MAX_TURN_IMAGE_BYTES // (1024 * 1024)} MB turn limit."
        )
    if media_type == "image/png" and not raw.startswith(b"\x89PNG\r\n\x1a\n"):
        raise MultimodalError("PNG data URI failed magic-byte validation.")
    if media_type == "image/jpeg" and not raw.startswith(b"\xff\xd8\xff"):
        raise MultimodalError("JPEG data URI failed magic-byte validation.")
    return media_type, raw


def validate_learner_image(data_uri: str) -> str:
    """Validate and return a normalized data URI string."""
    media_type, raw = parse_data_uri(data_uri)
    encoded = base64.b64encode(raw).decode("ascii")
    return f"data:{media_type};base64,{encoded}"


def build_user_content(
    *,
    text: str | None,
    image_data_uri: str | None,
    text_fallback: str = "[Scratchpad selection]",
) -> str | list[dict[str, Any]]:
    """Build OpenAI-shaped user content: plain string or text+image parts."""
    cleaned = (text or "").strip()
    if image_data_uri:
        uri = validate_learner_image(image_data_uri)
        parts: list[dict[str, Any]] = [
            {"type": "text", "text": cleaned or text_fallback},
            {"type": "image_url", "image_url": {"url": uri}},
        ]
        return parts
    return cleaned


def content_display_text(content: Any) -> str:
    """Flatten message content for transcript UI / markdown export."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return str(content or "")
    texts: list[str] = []
    has_image = False
    for part in content:
        if not isinstance(part, dict):
            continue
        if part.get("type") == "text":
            t = str(part.get("text") or "").strip()
            if t:
                texts.append(t)
        elif part.get("type") in {"image_url", "image"}:
            has_image = True
    joined = "\n".join(texts).strip()
    if has_image and not joined:
        return "[Scratchpad selection]"
    if has_image and "[Scratchpad selection]" not in joined:
        return f"{joined}\n[Scratchpad selection]".strip()
    return joined


def content_has_image(content: Any) -> bool:
    if not isinstance(content, list):
        return False
    return any(
        isinstance(part, dict) and part.get("type") in {"image_url", "image"}
        for part in content
    )


def _source_from_data_uri(url: str) -> dict[str, str]:
    media_type, raw = parse_data_uri(url)
    return {
        "type": "base64",
        "media_type": media_type,
        "data": base64.b64encode(raw).decode("ascii"),
    }


def to_anthropic_message(message: dict) -> dict:
    """Convert an OpenAI-shaped message into Anthropic Messages format."""
    role = message.get("role") or "user"
    content = message.get("content")
    if isinstance(content, str):
        return {"role": role, "content": content}
    if not isinstance(content, list):
        raise MultimodalError("Unsupported message content shape.")

    blocks: list[dict] = []
    for part in content:
        if not isinstance(part, dict):
            continue
        part_type = part.get("type")
        if part_type == "text":
            text = part.get("text") or ""
            if text:
                blocks.append({"type": "text", "text": text})
        elif part_type == "image_url":
            image_url = part.get("image_url") or {}
            url = image_url.get("url") if isinstance(image_url, dict) else None
            if not url:
                raise MultimodalError("image_url was missing a url.")
            blocks.append({"type": "image", "source": _source_from_data_uri(url)})
        elif part_type == "image":
            # Already Anthropic-shaped; pass through after light validation.
            source = part.get("source") or {}
            if not isinstance(source, dict) or source.get("type") != "base64":
                raise MultimodalError("Unsupported Anthropic image source.")
            media_type = str(source.get("media_type") or "").lower()
            if media_type not in ALLOWED_IMAGE_MEDIA_TYPES:
                raise MultimodalError(f"Unsupported image media type: {media_type!r}")
            blocks.append({"type": "image", "source": source})
        else:
            raise MultimodalError(f"Unsupported content type: {part_type!r}")
    if not blocks:
        raise MultimodalError("Message had no usable content blocks.")
    return {"role": role, "content": blocks}


def normalize_messages_for_anthropic(messages: list[dict]) -> list[dict]:
    return [to_anthropic_message(m) for m in messages]


def persistable_content(content: Any) -> Any:
    """Drop inline base64 from persisted transcripts; keep a display summary."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return content_display_text(content)
    if content_has_image(content):
        return content_display_text(content)
    # Text-only part lists collapse to a string for storage simplicity.
    return content_display_text(content)
