"""Tests for chapter source ingestion, normalization, and manifest."""

from __future__ import annotations

from pathlib import Path

import pytest

from apore.setup.normalize import NormalizationError, validate_source_url
from apore.setup.sources import (
    MAX_SOURCE_BYTES,
    SourceError,
    add_file_source,
    add_url_source,
    compute_source_hash,
    delete_source,
    list_sources,
    load_manifest,
    normalized_texts,
    source_hash,
    valid_source_ids,
)


@pytest.fixture()
def chapter(tmp_path: Path) -> Path:
    root = tmp_path / "chapter"
    root.mkdir()
    return root


def test_add_markdown_source_normalizes_directly(chapter: Path):
    entry = add_file_source(chapter, "notes.md", b"# Notes\n\nSets are collections.")
    assert entry["normalize_status"] == "ok"
    assert entry["kind"] == "file"
    texts = normalized_texts(chapter)
    assert len(texts) == 1
    assert "Sets are collections" in texts[0]["text"]


def test_add_pdf_source_uses_converter(chapter: Path):
    def fake_convert(target: str) -> str:
        return "# Converted\n\nExtracted body text."

    entry = add_file_source(
        chapter, "slides.pdf", b"%PDF-1.4 binary", converter=fake_convert
    )
    assert entry["normalize_status"] == "ok"
    assert "Extracted body" in normalized_texts(chapter)[0]["text"]


def test_unsupported_file_rejected(chapter: Path):
    with pytest.raises(SourceError):
        add_file_source(chapter, "clip.mp4", b"binary")


def test_duplicate_content_rejected(chapter: Path):
    add_file_source(chapter, "a.md", b"same bytes")
    with pytest.raises(SourceError):
        add_file_source(chapter, "b.md", b"same bytes")


def test_path_traversal_rejected(chapter: Path):
    with pytest.raises(SourceError):
        add_file_source(chapter, "../evil.md", b"x")


def test_oversize_rejected(chapter: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("apore.setup.sources.MAX_SOURCE_BYTES", 10)
    with pytest.raises(SourceError):
        add_file_source(chapter, "big.md", b"more than ten bytes here")


def test_failed_normalization_is_recorded_not_raised(chapter: Path):
    def boom(target: str) -> str:
        raise NormalizationError("bad file")

    entry = add_file_source(chapter, "broken.pdf", b"data", converter=boom)
    assert entry["normalize_status"] == "failed"
    assert "bad file" in entry["normalize_error"]
    assert normalized_texts(chapter) == []


def test_source_hash_changes_with_source_set(chapter: Path):
    assert source_hash(chapter) is None
    add_file_source(chapter, "a.md", b"alpha")
    h1 = source_hash(chapter)
    assert h1 is not None
    add_file_source(chapter, "b.md", b"beta")
    h2 = source_hash(chapter)
    assert h1 != h2


def test_delete_source_removes_files_and_entry(chapter: Path):
    entry = add_file_source(chapter, "a.md", b"alpha")
    delete_source(chapter, entry["id"])
    assert load_manifest(chapter)["sources"] == []
    assert valid_source_ids(chapter) == set()


def test_delete_missing_source_raises(chapter: Path):
    with pytest.raises(KeyError):
        delete_source(chapter, "ghost")


def test_add_youtube_url_source(chapter: Path):
    def fake_convert(target: str) -> str:
        return "# Transcript\n\nSpoken content."

    entry = add_url_source(
        chapter, "https://www.youtube.com/watch?v=abc123", converter=fake_convert
    )
    assert entry["kind"] == "url"
    assert entry["normalize_status"] == "ok"
    assert "Spoken content" in normalized_texts(chapter)[0]["text"]


def test_duplicate_url_rejected(chapter: Path):
    url = "https://youtu.be/abc123"
    add_url_source(chapter, url, converter=lambda t: "text")
    with pytest.raises(SourceError):
        add_url_source(chapter, url, converter=lambda t: "text")


def test_validate_source_url_rejects_non_https():
    with pytest.raises(NormalizationError):
        validate_source_url("http://youtube.com/watch?v=x")


def test_validate_source_url_rejects_non_youtube():
    with pytest.raises(NormalizationError):
        validate_source_url("https://example.com/page")


def test_validate_source_url_rejects_private_host():
    with pytest.raises(NormalizationError):
        validate_source_url("https://127.0.0.1/watch?v=x")


def test_list_sources_shows_legacy_raw_files(chapter: Path):
    raw = chapter / "sources"
    raw.mkdir()
    (raw / "legacy.md").write_text("# Legacy", encoding="utf-8")
    listed = list_sources(chapter)
    assert len(listed) == 1
    assert listed[0]["normalize_status"] == "legacy"


def test_compute_source_hash_empty_is_none():
    assert compute_source_hash({"sources": []}) is None
