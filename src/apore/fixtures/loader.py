"""Runtime fixture adapter — grounding paths via domain chapter resolution."""

from __future__ import annotations

import json
from pathlib import Path

from apore.fixtures.aliases import fixture_to_domain_chapter
from apore.knowledge.chapter import get_wiki_paths, load_concept_graph, resolve_chapter


def load_manifest(manifest_path: Path) -> dict:
    """Load fixtures manifest JSON."""
    raw = manifest_path.read_text(encoding="utf-8")
    return json.loads(raw)


def get_grounding_paths(
    fixture_name: str,
    concept_id: str,
    program_root: Path | None = None,
) -> list[Path]:
    """Return wiki file paths for the concept from a synced upstream domain."""
    root = program_root if program_root is not None else Path(__file__).parent.parent.parent
    mapped = fixture_to_domain_chapter(fixture_name)
    if mapped is None:
        return []

    domain_id, chapter_id = mapped
    try:
        chapter = resolve_chapter(f"domain:{domain_id}/{chapter_id}", root)
    except FileNotFoundError:
        return []

    graph = load_concept_graph(chapter)
    return get_wiki_paths(chapter, concept_id, graph)
