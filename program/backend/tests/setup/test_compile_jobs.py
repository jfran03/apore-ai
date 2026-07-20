"""Tests for the durable compile job lifecycle."""

from __future__ import annotations

from pathlib import Path

import pytest

from apore.providers.stub import StubProvider
from apore.setup import compile_jobs
from apore.setup.artifacts import load_approval, save_compile_state
from apore.setup.compile_jobs import (
    _run_compile_job,
    approve_compile,
    get_compile_status,
    load_wiki_preview,
    start_compile,
)
from apore.setup.sources import add_file_source

_PROGRAM = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def clear_registry():
    compile_jobs.reset_jobs_for_testing()
    yield
    compile_jobs.reset_jobs_for_testing()


@pytest.fixture()
def chapter(tmp_path: Path) -> Path:
    root = tmp_path / "chapter"
    root.mkdir()
    add_file_source(root, "notes.md", b"# Notes\n\nSets and operations content.")
    return root


def _compile_sync(chapter: Path) -> dict:
    return start_compile(
        chapter,
        provider=StubProvider(),
        model="stub-model",
        program_root=_PROGRAM,
        thread_runner=_run_compile_job,
    )


def test_start_compile_reaches_ready(chapter: Path):
    status = _compile_sync(chapter)
    assert status["stage"] == "ready"
    assert status["version"] == 1


def test_start_compile_without_sources_raises(tmp_path: Path):
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ValueError):
        _compile_sync(empty)


def test_approve_publishes_and_records(chapter: Path):
    _compile_sync(chapter)
    status = approve_compile(chapter)
    assert status["is_approved"] is True
    assert (chapter / "wiki" / "chapter_overview.md").is_file()
    assert (chapter / "concept-graph.json").is_file()
    approval = load_approval(chapter)
    assert approval["legacy"] is False
    assert approval["source_hash"] is not None


def test_approve_without_ready_raises(chapter: Path):
    with pytest.raises(ValueError):
        approve_compile(chapter)


def test_stale_after_source_change(chapter: Path):
    _compile_sync(chapter)
    approve_compile(chapter)
    add_file_source(chapter, "extra.md", b"# Extra\n\nMore material.")
    from apore.setup.artifacts import chapter_artifact_status
    from apore.setup.sources import source_hash

    status = chapter_artifact_status(
        chapter,
        current_source_hash=source_hash(chapter),
        live_run_tokens=set(),
    )
    assert status["is_stale"] is True


def test_interrupted_when_registry_empty(chapter: Path):
    save_compile_state(
        chapter,
        {"stage": "compiling", "version": 1, "source_hash": "h", "run_token": "gone"},
    )
    status = get_compile_status(chapter)
    assert status["stage"] == "interrupted"


def test_wiki_preview_from_staging(chapter: Path):
    _compile_sync(chapter)
    preview = load_wiki_preview(chapter, "staging")
    assert preview["source"] == "staging"
    assert any(p["concept_id"] == "chapter_overview" for p in preview["pages"])


def test_wiki_preview_published_after_approve(chapter: Path):
    _compile_sync(chapter)
    approve_compile(chapter)
    preview = load_wiki_preview(chapter, "published")
    assert preview["pages"]
    assert "chapter_overview" in preview["pages"][0]["body"] or preview["pages"][0][
        "body"
    ].startswith("#")


def test_wiki_preview_resolves_kebab_filenames(tmp_path: Path):
    """Snake-case concept ids resolve to kebab-case wiki files (bootstrap layout)."""
    import json

    root = tmp_path / "chapter"
    wiki = root / "wiki"
    wiki.mkdir(parents=True)
    graph = {
        "nodes": [
            {
                "id": "set_operations",
                "label": "Set Operations",
                "source_file": "set-operations.md",
                "depth": 0,
            }
        ],
        "edges": [],
    }
    (root / "concept-graph.json").write_text(json.dumps(graph), encoding="utf-8")
    (wiki / "set-operations.md").write_text(
        "# Set Operations\n\nUnion and intersection.\n", encoding="utf-8"
    )
    (root / ".approved.json").write_text(json.dumps({"version": 1}), encoding="utf-8")

    preview = load_wiki_preview(root, "published")
    page = preview["pages"][0]
    assert page["concept_id"] == "set_operations"
    assert "Union and intersection." in page["body"]
