"""Fixture bootstrap builds concept-graph from apore-lite-style wiki layout."""

from pathlib import Path

from apore.knowledge.chapter import find_chapter_with_graph, load_concept_graph, resolve_chapter
from apore.setup.stub_compile import bootstrap_chapter_from_wiki, find_fixture_chapter_root


def test_bootstrap_chapter_from_wiki(tmp_path: Path) -> None:
    fixture_root = tmp_path / ".fixtures" / "apore-lite"
    chapter = fixture_root / "discrete-math" / "chapters" / "01-set-theory"
    wiki = chapter / "wiki"
    wiki.mkdir(parents=True)
    (wiki / "what-is-a-set.md").write_text("# What is a Set\n\nBody.", encoding="utf-8")
    (wiki / "set-operations.md").write_text("# Set Operations\n\nBody.", encoding="utf-8")

    assert find_fixture_chapter_root(fixture_root) == chapter
    summary = bootstrap_chapter_from_wiki(chapter)
    assert summary["status"] == "bootstrapped"
    assert summary["nodes"] == 2
    assert find_chapter_with_graph(fixture_root) == chapter

    ctx = resolve_chapter("fixture:apore-lite", tmp_path)
    graph = load_concept_graph(ctx)
    assert graph.label_for("what_is_a_set") == "What Is A Set"
    assert graph.label_for("set_operations") == "Set Operations"
