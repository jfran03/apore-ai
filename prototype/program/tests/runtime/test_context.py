"""Tests for apore.runtime.context.assemble_prompt."""

from __future__ import annotations

import json

import pytest
from pathlib import Path

from apore.knowledge.chapter import ChapterContext, ConceptGraph, ConceptNode, load_concept_graph
from apore.runtime.context import assemble_prompt


def _make_fixture(tmp_path: Path) -> tuple[Path, Path, Path, ChapterContext, ConceptGraph]:
    root = tmp_path / "program"
    (root / "shared" / "protocols").mkdir(parents=True)

    (root / "AGENTS.md").write_text("# Tutor Harness\nSystem content here.", encoding="utf-8")
    (root / "shared" / "protocols" / "generate-question.md").write_text(
        "# Protocol: generate-question\nProtocol instructions here.", encoding="utf-8"
    )
    (root / "shared" / "protocols" / "extract-signals.md").write_text(
        "# Protocol: extract-signals\nExtract instructions here.", encoding="utf-8"
    )
    (root / "shared" / "protocols" / "generate-question-bank.md").write_text(
        "# Protocol: generate-question-bank\nBank generation instructions here.",
        encoding="utf-8",
    )

    chapter_root = root / "domains" / "t" / "chapters" / "01"
    wiki_dir = chapter_root / "wiki"
    wiki_dir.mkdir(parents=True)
    wiki_file = wiki_dir / "concept_a.md"
    wiki_file.write_text("# Concept A\n\nThis is the concept definition.", encoding="utf-8")
    graph_data = {
        "nodes": [{"id": "concept_a", "label": "Concept A", "depth": 0}],
        "edges": [],
    }
    (chapter_root / "concept-graph.json").write_text(json.dumps(graph_data), encoding="utf-8")

    state_file = tmp_path / "learner-state.md"
    state_file.write_text(
        "# Learner State\n\n## Scalar\n0.5\n\n## Mastery\n",
        encoding="utf-8",
    )

    chapter = ChapterContext(
        knowledge_source="domain:t/01",
        chapter_root=chapter_root,
        display_name="t / 01",
    )
    graph = load_concept_graph(chapter)
    return root, wiki_file, state_file, chapter, graph


def _assemble(protocol: str, root, wiki, state, chapter, graph):
    return assemble_prompt(
        protocol,
        state,
        concept_id="concept_a",
        chapter=chapter,
        graph=graph,
        wiki_paths=[wiki],
        program_root=root,
    )


def test_returns_dict_with_system_and_messages(tmp_path: Path):
    root, wiki, state, chapter, graph = _make_fixture(tmp_path)
    result = _assemble("generate-question", root, wiki, state, chapter, graph)
    assert isinstance(result, dict)
    assert "system" in result
    assert "messages" in result


def test_messages_is_single_user_message(tmp_path: Path):
    root, wiki, state, chapter, graph = _make_fixture(tmp_path)
    result = _assemble("generate-question", root, wiki, state, chapter, graph)
    msgs = result["messages"]
    assert len(msgs) == 1
    assert msgs[0]["role"] == "user"


def test_system_contains_agents_md_content(tmp_path: Path):
    root, wiki, state, chapter, graph = _make_fixture(tmp_path)
    result = _assemble("generate-question", root, wiki, state, chapter, graph)
    assert "Tutor Harness" in result["system"]


def test_user_message_contains_target_concept(tmp_path: Path):
    root, wiki, state, chapter, graph = _make_fixture(tmp_path)
    result = _assemble("generate-question", root, wiki, state, chapter, graph)
    content = result["messages"][0]["content"]
    assert "## Target Concept" in content
    assert "label: Concept A" in content
    assert "concept definition" in content


def test_user_message_has_section_headers(tmp_path: Path):
    root, wiki, state, chapter, graph = _make_fixture(tmp_path)
    result = _assemble("generate-question", root, wiki, state, chapter, graph)
    content = result["messages"][0]["content"]
    assert "## Protocol" in content
    assert "## Grounding Context" in content
    assert "## Learner State" in content


def test_invalid_protocol_raises_value_error(tmp_path: Path):
    root, wiki, state, chapter, graph = _make_fixture(tmp_path)
    with pytest.raises(ValueError, match="Unknown protocol"):
        _assemble("unknown-protocol", root, wiki, state, chapter, graph)


def test_generate_question_bank_protocol(tmp_path: Path):
    root, wiki, state, chapter, graph = _make_fixture(tmp_path)
    result = _assemble("generate-question-bank", root, wiki, state, chapter, graph)
    assert "generate-question-bank" in result["messages"][0]["content"]
