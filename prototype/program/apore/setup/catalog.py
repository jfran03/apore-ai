"""List knowledge sources for setup UI."""

from __future__ import annotations

import json
from pathlib import Path

from apore.fixtures.loader import load_manifest
from apore.knowledge.chapter import find_chapter_with_graph


def _chapter_status(chapter_root: Path) -> dict:
    sources = chapter_root / "sources"
    graph = chapter_root / "concept-graph.json"
    wiki = chapter_root / "wiki"
    source_files = []
    if sources.is_dir():
        source_files = [p.name for p in sources.iterdir() if p.is_file()]
    wiki_count = len(list(wiki.glob("*.md"))) if wiki.is_dir() else 0
    return {
        "sources_present": sources.is_dir() and bool(source_files),
        "source_count": len(source_files),
        "source_files": source_files,
        "has_concept_graph": graph.is_file(),
        "wiki_count": wiki_count,
    }


def list_knowledge(program_root: Path) -> dict:
    manifest = load_manifest(program_root / "apore" / "fixtures" / "manifest.json")
    fixtures = []
    for name, spec in manifest.get("fixtures", {}).items():
        target = program_root / spec["target"]
        chapter_root = find_chapter_with_graph(target) if target.exists() else None
        fixtures.append(
            {
                "name": name,
                "knowledge_source": f"fixture:{name}",
                "description": spec.get("description", ""),
                "commit": spec.get("commit", ""),
                "fetched": target.exists(),
                "chapter_ready": chapter_root is not None,
            }
        )

    domains = []
    domains_root = program_root / "domains"
    if domains_root.is_dir():
        for domain_path in sorted(domains_root.iterdir()):
            if not domain_path.is_dir():
                continue
            chapters_dir = domain_path / "chapters"
            if not chapters_dir.is_dir():
                continue
            chapters = []
            for chapter_path in sorted(chapters_dir.iterdir()):
                if chapter_path.is_dir():
                    chapters.append(
                        {
                            "id": chapter_path.name,
                            "knowledge_source": f"domain:{domain_path.name}/{chapter_path.name}",
                            **_chapter_status(chapter_path),
                        }
                    )
            domains.append({"id": domain_path.name, "chapters": chapters})

    return {"fixtures": fixtures, "domains": domains}
