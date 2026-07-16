"""Tests for structured grounding slices."""

from __future__ import annotations

import json
from pathlib import Path

from apore.knowledge.chapter import ChapterContext, load_concept_graph, resolve_chapter
from apore.runtime.grounding import build_grounding_slice


def test_build_grounding_slice_includes_target_concept(tmp_path: Path):
    chapter_root = tmp_path / "ch"
    wiki = chapter_root / "wiki"
    wiki.mkdir(parents=True)
    graph = {
        "nodes": [
            {"id": "set_theory_intro", "label": "Introduction to Set Theory", "depth": 1},
            {"id": "sets_definition", "label": "Definition of a Set", "depth": 0},
        ],
        "edges": [
            {
                "source": "sets_definition",
                "target": "set_theory_intro",
                "relation": "prerequisite_of",
            }
        ],
    }
    (chapter_root / "concept-graph.json").write_text(json.dumps(graph), encoding="utf-8")
    (wiki / "set_theory_intro.md").write_text("# Intro\n\nBody.", encoding="utf-8")

    chapter = ChapterContext(
        knowledge_source="domain:test/01",
        chapter_root=chapter_root,
        display_name="test / 01",
    )
    cg = load_concept_graph(chapter)
    text = build_grounding_slice(chapter, cg, "set_theory_intro", [wiki / "set_theory_intro.md"])

    assert "## Target Concept" in text
    assert "id: set_theory_intro" in text
    assert "label: Introduction to Set Theory" in text
    assert "depth: 1" in text
    assert "## Wiki content" in text
    assert "Body." in text


def test_resolve_chapter_domain(tmp_path: Path):
    root = tmp_path / "program"
    chapter = root / "domains" / "d1" / "chapters" / "c1"
    chapter.mkdir(parents=True)
    (chapter / "concept-graph.json").write_text('{"nodes":[],"edges":[]}', encoding="utf-8")

    ctx = resolve_chapter("domain:d1/c1", root)
    assert ctx.chapter_root == chapter
