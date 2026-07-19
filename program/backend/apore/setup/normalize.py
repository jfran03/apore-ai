"""Normalize uploaded sources into markdown via MarkItDown.

File bytes and remote URLs are converted to markdown text that the compiler and
tutor can read. Plain markdown/text is read directly; everything else goes
through MarkItDown. URL ingestion is restricted to public HTTPS YouTube links to
avoid server-side request forgery against private networks.
"""

from __future__ import annotations

import ipaddress
from pathlib import Path
from urllib.parse import urlparse

_DIRECT_TEXT_EXTS = {".md", ".markdown", ".txt"}

# Document formats the bundled MarkItDown package converts reliably. Image OCR
# and audio transcription need optional extras, so they are intentionally out.
SUPPORTED_FILE_EXTS = {
    ".pdf",
    ".html",
    ".htm",
    ".md",
    ".markdown",
    ".txt",
    ".docx",
    ".pptx",
    ".xlsx",
    ".csv",
    ".json",
    ".xml",
    ".epub",
}

_ALLOWED_URL_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
}


class NormalizationError(ValueError):
    """Raised when a source cannot be normalized into markdown."""


def _markitdown_convert(target: str) -> str:
    from markitdown import MarkItDown

    return MarkItDown().convert(target).text_content


def is_supported_file(name: str) -> bool:
    return Path(name).suffix.lower() in SUPPORTED_FILE_EXTS


def _host_is_private(host: str) -> bool:
    if host in {"localhost", "localhost.localdomain"}:
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved


def validate_source_url(url: str) -> str:
    """Validate a remote source URL. Returns the URL or raises NormalizationError."""
    parsed = urlparse(url.strip())
    if parsed.scheme != "https":
        raise NormalizationError("Only HTTPS URLs are supported.")
    host = (parsed.hostname or "").lower()
    if not host:
        raise NormalizationError("URL is missing a host.")
    if _host_is_private(host):
        raise NormalizationError("Private-network URLs are not allowed.")
    if host not in _ALLOWED_URL_HOSTS:
        raise NormalizationError("Only YouTube URLs are supported for now.")
    return url.strip()


def normalize_file(path: Path, *, converter=None) -> str:
    """Convert a stored source file to markdown text."""
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_FILE_EXTS:
        raise NormalizationError(f"Unsupported file type: {suffix or path.name!r}")
    if suffix in _DIRECT_TEXT_EXTS:
        return path.read_text(encoding="utf-8", errors="replace")
    convert = converter or _markitdown_convert
    try:
        text = convert(str(path))
    except Exception as exc:  # MarkItDown raises a variety of errors
        raise NormalizationError(f"Could not convert {path.name}: {exc}") from exc
    if not text or not text.strip():
        raise NormalizationError(f"No text extracted from {path.name}")
    return text


def normalize_url(url: str, *, converter=None) -> str:
    """Validate and convert a remote source URL to markdown text."""
    validated = validate_source_url(url)
    convert = converter or _markitdown_convert
    try:
        text = convert(validated)
    except Exception as exc:
        raise NormalizationError(f"Could not fetch {validated}: {exc}") from exc
    if not text or not text.strip():
        raise NormalizationError(f"No text extracted from {validated}")
    return text
