"""Tests for the bounded LLM chapter compiler."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apore.providers.base import Provider
from apore.setup.artifacts import ArtifactValidationError, staging_dir
from apore.setup.compile import (
    CompileError,
    compile_to_staging,
    parse_compile_response,
    run_compile,
)
from apore.setup.sources import add_file_source

_PROGRAM = Path(__file__).resolve().parents[2]


class FakeProvider(Provider):
    def __init__(self, response: str):
        self._response = response

    def invoke(self, system_prompt, messages, model, config):
        return self._response


def _valid_response(citation: str) -> str:
    return json.dumps(
        {
            "pages": [
                {
                    "concept_id": "sets",
                    "label": "Sets",
                    "body": "A set is a collection.",
                    "citations": [citation],
                },
                {
                    "concept_id": "operations",
                    "label": "Operations",
                    "body": "Union and intersection.",
                    "citations": [citation],
                },
            ],
            "edges": [{"source": "sets", "target": "operations"}],
        }
    )


@pytest.fixture()
def chapter(tmp_path: Path) -> Path:
    root = tmp_path / "chapter"
    root.mkdir()
    add_file_source(root, "notes.md", b"# Notes\n\nSets and operations.")
    return root


def test_parse_compile_response_strips_fences():
    raw = "```json\n" + _valid_response("notes-md") + "\n```"
    artifact = parse_compile_response(raw)
    assert len(artifact.pages) == 2
    assert artifact.edges[0].target == "operations"


def test_parse_compile_response_rejects_non_json():
    with pytest.raises(CompileError):
        parse_compile_response("this is not json")


def test_run_compile_reads_sources(chapter: Path):
    class CapturingProvider(Provider):
        def __init__(self):
            self.messages = None

        def invoke(self, system_prompt, messages, model, config):
            self.messages = messages
            return _valid_response("notes-md")

    provider = CapturingProvider()
    artifact = run_compile(
        chapter, provider=provider, model="m", program_root=_PROGRAM
    )
    assert {p.concept_id for p in artifact.pages} == {"sets", "operations"}
    user_content = provider.messages[0]["content"]
    assert "untrusted evidence" in user_content
    assert "<untrusted_source id=\"notes-md\">" in user_content
    assert "</untrusted_source>" in user_content


def test_run_compile_without_sources_raises(tmp_path: Path):
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(CompileError):
        run_compile(
            empty,
            provider=FakeProvider(_valid_response("x")),
            model="m",
            program_root=_PROGRAM,
        )


def test_compile_to_staging_writes_files(chapter: Path):
    summary = compile_to_staging(
        chapter,
        provider=FakeProvider(_valid_response("notes-md")),
        model="m",
        program_root=_PROGRAM,
        version=1,
        source_hash="hash",
    )
    assert summary["concept_count"] == 2
    staging = staging_dir(chapter)
    assert (staging / "wiki" / "sets.md").is_file()
    graph = json.loads((staging / "concept-graph.json").read_text(encoding="utf-8"))
    assert len(graph["nodes"]) == 2


def test_compile_to_staging_rejects_invalid_citation(chapter: Path):
    with pytest.raises(ArtifactValidationError):
        compile_to_staging(
            chapter,
            provider=FakeProvider(_valid_response("ghost_source")),
            model="m",
            program_root=_PROGRAM,
            version=1,
            source_hash="hash",
        )


def test_compile_to_staging_does_not_touch_published(chapter: Path):
    published_wiki = chapter / "wiki"
    published_wiki.mkdir()
    (published_wiki / "keep.md").write_text("approved", encoding="utf-8")
    with pytest.raises(ArtifactValidationError):
        compile_to_staging(
            chapter,
            provider=FakeProvider(_valid_response("ghost_source")),
            model="m",
            program_root=_PROGRAM,
            version=1,
            source_hash="hash",
        )
    assert (published_wiki / "keep.md").read_text(encoding="utf-8") == "approved"
