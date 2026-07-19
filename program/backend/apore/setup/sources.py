"""Immutable chapter source manifest and ingestion.

Sources are stored under ``sources/`` and never mutated after ingest. Each source
is normalized to markdown under ``sources/_normalized/`` and recorded in
``sources/_manifest.json`` with its content hash, so a change in the source set
can be detected (staleness) and cited by the compiler.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from apore.setup.normalize import (
    NormalizationError,
    is_supported_file,
    normalize_file,
    normalize_url,
    validate_source_url,
)

SOURCES_DIRNAME = "sources"
NORMALIZED_DIRNAME = "_normalized"
MANIFEST_NAME = "_manifest.json"

MAX_SOURCE_BYTES = 25 * 1024 * 1024
MAX_SOURCES_PER_CHAPTER = 50

_RESERVED_NAMES = {NORMALIZED_DIRNAME, MANIFEST_NAME, ".gitkeep", "README.md"}


class SourceError(ValueError):
    """Raised for invalid source ingestion requests."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sources_dir(chapter_root: Path) -> Path:
    return chapter_root / SOURCES_DIRNAME


def normalized_dir(chapter_root: Path) -> Path:
    return sources_dir(chapter_root) / NORMALIZED_DIRNAME


def manifest_path(chapter_root: Path) -> Path:
    return sources_dir(chapter_root) / MANIFEST_NAME


def _slug(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return text or "source"


def _safe_name(name: str) -> str:
    base = Path(name).name
    if not base or base != name or ".." in base:
        raise SourceError(f"Invalid filename: {name!r}")
    return base


def load_manifest(chapter_root: Path) -> dict:
    path = manifest_path(chapter_root)
    if not path.is_file():
        return {"version": 1, "sources": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"version": 1, "sources": []}
    if not isinstance(data.get("sources"), list):
        data["sources"] = []
    return data


def save_manifest(chapter_root: Path, manifest: dict) -> None:
    sources_dir(chapter_root).mkdir(parents=True, exist_ok=True)
    manifest_path(chapter_root).write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )


def _unique_id(existing: set[str], base: str) -> str:
    if base not in existing:
        return base
    n = 2
    while f"{base}-{n}" in existing:
        n += 1
    return f"{base}-{n}"


def compute_source_hash(manifest: dict) -> str | None:
    """Stable hash over the current source set; None when there are no sources."""
    entries = manifest.get("sources") or []
    if not entries:
        return None
    parts = sorted(f"{e.get('id')}:{e.get('sha256')}" for e in entries)
    digest = hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()
    return digest


def source_hash(chapter_root: Path) -> str | None:
    return compute_source_hash(load_manifest(chapter_root))


def valid_source_ids(chapter_root: Path) -> set[str]:
    return {e["id"] for e in load_manifest(chapter_root).get("sources", []) if e.get("id")}


def list_sources(chapter_root: Path) -> list[dict]:
    """Public view of the source set (manifest, or legacy raw files fallback)."""
    manifest = load_manifest(chapter_root)
    entries = manifest.get("sources") or []
    if entries:
        return [_public_entry(e) for e in entries]

    legacy: list[dict] = []
    directory = sources_dir(chapter_root)
    if directory.is_dir():
        for path in sorted(directory.iterdir()):
            if not path.is_file() or path.name in _RESERVED_NAMES:
                continue
            legacy.append(
                {
                    "id": _slug(path.name),
                    "kind": "file",
                    "display_name": path.name,
                    "media_type": None,
                    "size": path.stat().st_size,
                    "ingested_at": None,
                    "normalize_status": "legacy",
                    "normalize_error": None,
                }
            )
    return legacy


def _public_entry(entry: dict) -> dict:
    return {
        "id": entry.get("id"),
        "kind": entry.get("kind"),
        "display_name": entry.get("url") or entry.get("original_name"),
        "media_type": entry.get("media_type"),
        "size": entry.get("size"),
        "ingested_at": entry.get("ingested_at"),
        "normalize_status": entry.get("normalize_status"),
        "normalize_error": entry.get("normalize_error"),
    }


def normalized_texts(chapter_root: Path) -> list[dict]:
    """Compiler input: successfully normalized sources with their markdown text."""
    out: list[dict] = []
    ndir = normalized_dir(chapter_root)
    for entry in load_manifest(chapter_root).get("sources", []):
        if entry.get("normalize_status") != "ok":
            continue
        norm_name = entry.get("normalized_name")
        if not norm_name:
            continue
        norm_path = ndir / norm_name
        if not norm_path.is_file():
            continue
        out.append(
            {
                "id": entry["id"],
                "label": entry.get("url") or entry.get("original_name") or entry["id"],
                "text": norm_path.read_text(encoding="utf-8"),
            }
        )
    return out


def _require_chapter(chapter_root: Path) -> None:
    if not chapter_root.is_dir():
        raise SourceError("Chapter not found")


def add_file_source(
    chapter_root: Path,
    original_name: str,
    content: bytes,
    *,
    media_type: str | None = None,
    converter=None,
) -> dict:
    """Store a file source immutably, normalize it, and record it in the manifest."""
    _require_chapter(chapter_root)
    safe = _safe_name(original_name)
    if not is_supported_file(safe):
        raise SourceError(f"Unsupported file type: {Path(safe).suffix or safe!r}")
    if len(content) == 0:
        raise SourceError(f"{safe} is empty")
    if len(content) > MAX_SOURCE_BYTES:
        raise SourceError(
            f"{safe} exceeds the {MAX_SOURCE_BYTES // (1024 * 1024)} MB source limit"
        )

    manifest = load_manifest(chapter_root)
    entries = manifest["sources"]
    if len(entries) >= MAX_SOURCES_PER_CHAPTER:
        raise SourceError(
            f"Chapter already has the maximum of {MAX_SOURCES_PER_CHAPTER} sources"
        )

    sha = hashlib.sha256(content).hexdigest()
    if any(e.get("sha256") == sha for e in entries):
        raise SourceError(f"{safe} is a duplicate of an existing source")

    directory = sources_dir(chapter_root)
    directory.mkdir(parents=True, exist_ok=True)
    stored_name = _dedupe_stored_name(directory, safe)
    (directory / stored_name).write_bytes(content)

    existing_ids = {e["id"] for e in entries}
    source_id = _unique_id(existing_ids, _slug(safe))

    entry = {
        "id": source_id,
        "kind": "file",
        "original_name": safe,
        "stored_name": stored_name,
        "url": None,
        "media_type": media_type,
        "sha256": sha,
        "size": len(content),
        "ingested_at": _now_iso(),
        "normalized_name": None,
        "normalize_status": "pending",
        "normalize_error": None,
    }

    ndir = normalized_dir(chapter_root)
    ndir.mkdir(parents=True, exist_ok=True)
    try:
        text = normalize_file(directory / stored_name, converter=converter)
        norm_name = f"{source_id}.md"
        (ndir / norm_name).write_text(text, encoding="utf-8")
        entry["normalized_name"] = norm_name
        entry["normalize_status"] = "ok"
    except NormalizationError as exc:
        entry["normalize_status"] = "failed"
        entry["normalize_error"] = str(exc)

    entries.append(entry)
    save_manifest(chapter_root, manifest)
    return _public_entry(entry)


def add_url_source(chapter_root: Path, url: str, *, converter=None) -> dict:
    """Validate a URL source, normalize it, and record it in the manifest."""
    _require_chapter(chapter_root)
    validated = validate_source_url(url)

    manifest = load_manifest(chapter_root)
    entries = manifest["sources"]
    if len(entries) >= MAX_SOURCES_PER_CHAPTER:
        raise SourceError(
            f"Chapter already has the maximum of {MAX_SOURCES_PER_CHAPTER} sources"
        )
    if any(e.get("url") == validated for e in entries):
        raise SourceError("This URL has already been added")

    existing_ids = {e["id"] for e in entries}
    source_id = _unique_id(existing_ids, _slug(validated)[:48])

    entry = {
        "id": source_id,
        "kind": "url",
        "original_name": None,
        "stored_name": None,
        "url": validated,
        "media_type": "text/uri-list",
        "sha256": hashlib.sha256(validated.encode("utf-8")).hexdigest(),
        "size": 0,
        "ingested_at": _now_iso(),
        "normalized_name": None,
        "normalize_status": "pending",
        "normalize_error": None,
    }

    ndir = normalized_dir(chapter_root)
    ndir.mkdir(parents=True, exist_ok=True)
    try:
        text = normalize_url(validated, converter=converter)
        norm_name = f"{source_id}.md"
        (ndir / norm_name).write_text(text, encoding="utf-8")
        entry["normalized_name"] = norm_name
        entry["normalize_status"] = "ok"
        entry["size"] = len(text.encode("utf-8"))
    except NormalizationError as exc:
        entry["normalize_status"] = "failed"
        entry["normalize_error"] = str(exc)

    entries.append(entry)
    save_manifest(chapter_root, manifest)
    return _public_entry(entry)


def delete_source(chapter_root: Path, source_id: str) -> None:
    """Remove a source, its stored bytes, and its normalized markdown."""
    manifest = load_manifest(chapter_root)
    entries = manifest["sources"]
    match = next((e for e in entries if e.get("id") == source_id), None)
    if match is None:
        raise KeyError(f"Source not found: {source_id!r}")

    if match.get("stored_name"):
        stored = sources_dir(chapter_root) / match["stored_name"]
        if stored.is_file():
            stored.unlink()
    if match.get("normalized_name"):
        norm = normalized_dir(chapter_root) / match["normalized_name"]
        if norm.is_file():
            norm.unlink()

    manifest["sources"] = [e for e in entries if e.get("id") != source_id]
    save_manifest(chapter_root, manifest)


def _dedupe_stored_name(directory: Path, name: str) -> str:
    if not (directory / name).exists():
        return name
    stem = Path(name).stem
    suffix = Path(name).suffix
    n = 2
    while (directory / f"{stem}-{n}{suffix}").exists():
        n += 1
    return f"{stem}-{n}{suffix}"
