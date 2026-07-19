"""Tests for versioned chapter compile artifacts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apore.setup.artifacts import (
    ArtifactValidationError,
    CompiledArtifact,
    CompiledEdge,
    CompiledWikiPage,
    chapter_artifact_status,
    compute_depths,
    default_teaching_order,
    detect_cycle,
    load_approval,
    load_compile_state,
    publish_staging,
    resolve_teaching_order,
    save_approval,
    save_compile_state,
    staging_dir,
    validate_compiled_artifact,
    write_artifact_files,
    write_teaching_order,
)


def _artifact() -> CompiledArtifact:
    return CompiledArtifact(
        pages=[
            CompiledWikiPage(
                concept_id="sets_definition",
                label="Definition of a Set",
                body="A set is a collection of distinct elements.",
                citations=["notes.md"],
            ),
            CompiledWikiPage(
                concept_id="set_operations",
                label="Set Operations",
                body="Union and intersection combine sets.",
                citations=["notes.md"],
            ),
        ],
        edges=[CompiledEdge(source="sets_definition", target="set_operations")],
    )


def test_validate_accepts_well_formed_artifact():
    errors = validate_compiled_artifact(_artifact(), {"notes.md"})
    assert errors == []


def test_validate_rejects_missing_citation():
    art = CompiledArtifact(
        pages=[
            CompiledWikiPage(
                concept_id="sets_definition",
                label="Sets",
                body="text",
                citations=[],
            )
        ]
    )
    errors = validate_compiled_artifact(art, {"notes.md"})
    assert any("no source citations" in e for e in errors)


def test_validate_rejects_unknown_citation():
    art = CompiledArtifact(
        pages=[
            CompiledWikiPage(
                concept_id="sets_definition",
                label="Sets",
                body="text",
                citations=["ghost.md"],
            )
        ]
    )
    errors = validate_compiled_artifact(art, {"notes.md"})
    assert any("unknown source" in e for e in errors)


def test_validate_rejects_duplicate_concept_ids():
    art = CompiledArtifact(
        pages=[
            CompiledWikiPage("dup", "A", "body", ["notes.md"]),
            CompiledWikiPage("dup", "B", "body", ["notes.md"]),
        ]
    )
    errors = validate_compiled_artifact(art, {"notes.md"})
    assert any("duplicate concept_id" in e for e in errors)


def test_validate_rejects_invalid_concept_id():
    art = CompiledArtifact(
        pages=[CompiledWikiPage("Bad Id!", "A", "body", ["notes.md"])]
    )
    errors = validate_compiled_artifact(art, {"notes.md"})
    assert any("invalid concept_id" in e for e in errors)


def test_validate_rejects_edge_to_unknown_concept():
    art = CompiledArtifact(
        pages=[CompiledWikiPage("a", "A", "body", ["notes.md"])],
        edges=[CompiledEdge(source="a", target="ghost")],
    )
    errors = validate_compiled_artifact(art, {"notes.md"})
    assert any("unknown target concept" in e for e in errors)


def test_detect_cycle_finds_loop():
    edges = [
        CompiledEdge("a", "b"),
        CompiledEdge("b", "c"),
        CompiledEdge("c", "a"),
    ]
    cycle = detect_cycle(["a", "b", "c"], edges)
    assert cycle is not None
    assert cycle[0] == cycle[-1]


def test_validate_rejects_cyclic_graph():
    art = CompiledArtifact(
        pages=[
            CompiledWikiPage("a", "A", "body", ["notes.md"]),
            CompiledWikiPage("b", "B", "body", ["notes.md"]),
        ],
        edges=[CompiledEdge("a", "b"), CompiledEdge("b", "a")],
    )
    errors = validate_compiled_artifact(art, {"notes.md"})
    assert any("cyclic" in e for e in errors)


def test_compute_depths_longest_path():
    edges = [CompiledEdge("a", "b"), CompiledEdge("b", "c"), CompiledEdge("a", "c")]
    depths = compute_depths(["a", "b", "c"], edges)
    assert depths == {"a": 0, "b": 1, "c": 2}


def test_write_artifact_files_materializes_tree(tmp_path: Path):
    target = tmp_path / "staging"
    target.mkdir()
    write_artifact_files(target, _artifact(), source_hash="hash123", version=1)
    graph = json.loads((target / "concept-graph.json").read_text(encoding="utf-8"))
    assert {n["id"] for n in graph["nodes"]} == {"sets_definition", "set_operations"}
    assert (target / "wiki" / "sets_definition.md").is_file()
    assert (target / "_index.md").is_file()
    meta = json.loads((target / "compile.json").read_text(encoding="utf-8"))
    assert meta["source_hash"] == "hash123"
    assert meta["version"] == 1


def test_publish_staging_replaces_published(tmp_path: Path):
    chapter = tmp_path / "chapter"
    chapter.mkdir()
    (chapter / "wiki").mkdir()
    (chapter / "wiki" / "old.md").write_text("old", encoding="utf-8")

    staging = staging_dir(chapter)
    staging.mkdir(parents=True)
    write_artifact_files(staging, _artifact(), source_hash="h", version=2)

    publish_staging(chapter)
    assert (chapter / "wiki" / "sets_definition.md").is_file()
    assert not (chapter / "wiki" / "old.md").is_file()


def test_publish_staging_missing_raises(tmp_path: Path):
    chapter = tmp_path / "chapter"
    chapter.mkdir()
    with pytest.raises(FileNotFoundError):
        publish_staging(chapter)


def test_compile_state_round_trip(tmp_path: Path):
    chapter = tmp_path / "chapter"
    chapter.mkdir()
    assert load_compile_state(chapter)["stage"] == "idle"
    save_compile_state(
        chapter,
        {
            "stage": "compiling",
            "version": 1,
            "source_hash": "h",
            "progress": {"done": 1, "total": 3},
            "run_token": "tok",
        },
    )
    state = load_compile_state(chapter)
    assert state["stage"] == "compiling"
    assert state["progress"] == {"done": 1, "total": 3}
    assert state["updated_at"] is not None


def test_load_approval_synthesizes_legacy(tmp_path: Path):
    chapter = tmp_path / "chapter"
    (chapter / "wiki").mkdir(parents=True)
    (chapter / "wiki" / "a.md").write_text("# A", encoding="utf-8")
    (chapter / "concept-graph.json").write_text(
        json.dumps({"nodes": [{"id": "a"}], "edges": []}), encoding="utf-8"
    )
    approval = load_approval(chapter)
    assert approval is not None
    assert approval["legacy"] is True
    assert approval["source_hash"] is None


def test_save_and_load_approval(tmp_path: Path):
    chapter = tmp_path / "chapter"
    chapter.mkdir()
    save_approval(chapter, version=3, source_hash="abc")
    approval = load_approval(chapter)
    assert approval["version"] == 3
    assert approval["source_hash"] == "abc"
    assert approval["legacy"] is False


def test_status_reports_stale_when_source_changed(tmp_path: Path):
    chapter = tmp_path / "chapter"
    chapter.mkdir()
    save_approval(chapter, version=1, source_hash="oldhash")
    status = chapter_artifact_status(chapter, current_source_hash="newhash")
    assert status["is_approved"] is True
    assert status["is_stale"] is True


def test_status_not_stale_for_legacy(tmp_path: Path):
    chapter = tmp_path / "chapter"
    (chapter / "wiki").mkdir(parents=True)
    (chapter / "wiki" / "a.md").write_text("# A", encoding="utf-8")
    (chapter / "concept-graph.json").write_text(
        json.dumps({"nodes": [{"id": "a"}], "edges": []}), encoding="utf-8"
    )
    status = chapter_artifact_status(chapter, current_source_hash="whatever")
    assert status["is_approved"] is True
    assert status["is_stale"] is False


def test_status_marks_interrupted_when_not_live(tmp_path: Path):
    chapter = tmp_path / "chapter"
    chapter.mkdir()
    save_compile_state(
        chapter,
        {"stage": "compiling", "version": 1, "source_hash": "h", "run_token": "gone"},
    )
    status = chapter_artifact_status(
        chapter, current_source_hash="h", live_run_tokens=set()
    )
    assert status["compile"]["stage"] == "interrupted"


def test_status_keeps_running_when_live(tmp_path: Path):
    chapter = tmp_path / "chapter"
    chapter.mkdir()
    save_compile_state(
        chapter,
        {"stage": "compiling", "version": 1, "source_hash": "h", "run_token": "live"},
    )
    status = chapter_artifact_status(
        chapter, current_source_hash="h", live_run_tokens={"live"}
    )
    assert status["compile"]["stage"] == "compiling"


def test_from_dict_parses_pages_and_edges():
    art = CompiledArtifact.from_dict(
        {
            "pages": [
                {
                    "concept_id": "a",
                    "label": "A",
                    "body": "text",
                    "citations": ["notes.md"],
                }
            ],
            "edges": [{"source": "a", "target": "b"}],
        }
    )
    assert len(art.pages) == 1
    assert art.pages[0].concept_id == "a"
    assert art.edges[0].target == "b"


# ---------------------------------------------------------------------------
# Teaching order
# ---------------------------------------------------------------------------


def _graph_with_depths() -> dict:
    return {
        "nodes": [
            {"id": "b", "label": "B", "depth": 1},
            {"id": "a", "label": "A", "depth": 0},
            {"id": "c", "label": "C", "depth": 1},
        ],
        "edges": [{"source": "a", "target": "b", "relation": "prerequisite_of"}],
    }


def test_default_teaching_order_is_depth_then_id():
    graph = _graph_with_depths()
    assert default_teaching_order(graph["nodes"]) == ["a", "b", "c"]


def test_resolve_falls_back_to_default_without_stored_order():
    assert resolve_teaching_order(_graph_with_depths()) == ["a", "b", "c"]


def test_resolve_uses_valid_stored_order():
    graph = _graph_with_depths()
    graph["teaching_order"] = ["c", "a", "b"]
    assert resolve_teaching_order(graph) == ["c", "a", "b"]


def test_resolve_ignores_stale_stored_order():
    graph = _graph_with_depths()
    graph["teaching_order"] = ["a", "b"]  # missing "c"
    assert resolve_teaching_order(graph) == ["a", "b", "c"]


def test_write_teaching_order_persists_without_touching_edges_or_depth(tmp_path: Path):
    directory = tmp_path / "chapter"
    directory.mkdir()
    graph = _graph_with_depths()
    (directory / "concept-graph.json").write_text(json.dumps(graph), encoding="utf-8")

    write_teaching_order(directory, ["c", "b", "a"])

    saved = json.loads((directory / "concept-graph.json").read_text(encoding="utf-8"))
    assert saved["teaching_order"] == ["c", "b", "a"]
    assert saved["edges"] == graph["edges"]
    assert {n["id"]: n["depth"] for n in saved["nodes"]} == {"a": 0, "b": 1, "c": 1}


def test_write_teaching_order_rejects_non_permutation(tmp_path: Path):
    directory = tmp_path / "chapter"
    directory.mkdir()
    (directory / "concept-graph.json").write_text(
        json.dumps(_graph_with_depths()), encoding="utf-8"
    )

    with pytest.raises(ArtifactValidationError):
        write_teaching_order(directory, ["a", "b"])
    with pytest.raises(ArtifactValidationError):
        write_teaching_order(directory, ["a", "b", "d"])
