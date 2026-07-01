"""List knowledge sources for setup UI."""

from __future__ import annotations

import json
from pathlib import Path

from apore.fixtures.loader import load_manifest
from apore.knowledge.chapter import find_chapter_with_graph


def _question_bank_status(chapter_root: Path) -> dict:
    bank_path = chapter_root / "question-bank.json"
    if not bank_path.is_file():
        return {"has_question_bank": False, "question_bank_count": 0}
    try:
        raw = json.loads(bank_path.read_text(encoding="utf-8"))
        count = len(raw.get("questions") or [])
    except (json.JSONDecodeError, OSError):
        count = 0
    return {"has_question_bank": count > 0, "question_bank_count": count}


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
        **_question_bank_status(chapter_root),
    }


def list_knowledge(program_root: Path) -> dict:
    manifest = load_manifest(program_root / "apore" / "fixtures" / "manifest.json")
    fixtures = []
    for name, spec in manifest.get("fixtures", {}).items():
        target = program_root / spec["target"]
        domain_id = spec.get("domain_id", "discrete-math")
        chapter_id = spec.get("chapter_id", "01-set-theory")
        chapter_root = find_chapter_with_graph(target) if target.exists() else None
        fixtures.append(
            {
                "name": name,
                "knowledge_source": f"domain:{domain_id}/{chapter_id}",
                "domain_id": domain_id,
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
            if not domain_path.is_dir() or domain_path.name.startswith("_"):
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
