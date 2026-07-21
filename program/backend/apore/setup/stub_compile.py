"""Minimal chapter compile: sources/ → concept-graph.json + wiki/."""

from __future__ import annotations

import json
import re
from pathlib import Path

from markitdown import MarkItDown

_SOURCE_EXTS = {".pdf", ".html", ".htm", ".md", ".txt"}
_markitdown = MarkItDown()


def _to_snake(stem: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "_", stem).strip("_").lower()
    return text or "concept"


def _humanize(stem: str) -> str:
    text = re.sub(r"[_-]+", " ", stem).strip()
    return text.title() if text else stem


def _extract_text(path: Path) -> str:
    if path.suffix.lower() in {".md", ".txt"}:
        return path.read_text(encoding="utf-8")
    return _markitdown.convert(str(path)).text_content


def stub_compile_chapter(chapter_root: Path) -> dict:
    """Build concept-graph and wiki pages from sources/. Returns summary dict."""
    sources_dir = chapter_root / "sources"
    wiki_dir = chapter_root / "wiki"
    wiki_dir.mkdir(parents=True, exist_ok=True)

    if not sources_dir.is_dir():
        raise FileNotFoundError(f"sources/ not found under {chapter_root}")

    source_files = sorted(
        p for p in sources_dir.iterdir() if p.is_file() and p.suffix.lower() in _SOURCE_EXTS
    )
    if not source_files:
        raise ValueError("No source files found (supported: pdf, html, md, txt)")

    nodes: list[dict] = []
    for path in source_files:
        node_id = _to_snake(path.stem)
        label = _humanize(path.stem)
        nodes.append(
            {
                "id": node_id,
                "label": label,
                "source_file": path.name,
                "depth": 0,
            }
        )
        body = _extract_text(path)
        wiki_path = wiki_dir / f"{node_id}.md"
        wiki_path.write_text(
            f"# {label}\n\n{body}\n\n> Source: {path.name}\n",
            encoding="utf-8",
        )

    graph = {"nodes": nodes, "edges": []}
    graph_path = chapter_root / "concept-graph.json"
    graph_path.write_text(json.dumps(graph, indent=2) + "\n", encoding="utf-8")

    return {
        "nodes": len(nodes),
        "wiki_files": len(nodes),
        "concept_graph": str(graph_path),
    }


def bootstrap_chapter_from_wiki(chapter_root: Path) -> dict:
    """Build concept-graph.json from existing wiki/*.md (apore-lite layout).

    Does not rewrite wiki pages. Safe to call when graph already exists.
    """
    wiki_dir = chapter_root / "wiki"
    if not wiki_dir.is_dir():
        raise FileNotFoundError(f"wiki/ not found under {chapter_root}")

    wiki_files = sorted(
        p for p in wiki_dir.glob("*.md") if p.is_file() and p.name != "_index.md"
    )
    if not wiki_files:
        raise ValueError(f"No wiki pages under {wiki_dir}")

    graph_path = chapter_root / "concept-graph.json"
    if graph_path.is_file():
        raw = json.loads(graph_path.read_text(encoding="utf-8"))
        existing = raw.get("nodes") or []
        if existing:
            return {
                "nodes": len(existing),
                "wiki_files": len(wiki_files),
                "concept_graph": str(graph_path),
                "status": "already_present",
            }

    nodes: list[dict] = []
    for index, path in enumerate(wiki_files):
        node_id = _to_snake(path.stem)
        label = _humanize(path.stem)
        nodes.append(
            {
                "id": node_id,
                "label": label,
                "source_file": path.name,
                "depth": index,
            }
        )

    edges: list[dict] = []
    for index in range(1, len(nodes)):
        edges.append(
            {
                "source": nodes[index - 1]["id"],
                "target": nodes[index]["id"],
                "relation": "prerequisite_of",
                "provenance": "fixture_bootstrap",
                "confidence": "INFERRED",
            }
        )

    graph = {"nodes": nodes, "edges": edges}
    graph_path.write_text(json.dumps(graph, indent=2) + "\n", encoding="utf-8")

    return {
        "nodes": len(nodes),
        "wiki_files": len(wiki_files),
        "concept_graph": str(graph_path),
        "status": "bootstrapped",
    }


def find_fixture_chapter_root(fixture_root: Path) -> Path | None:
    """Pick the best chapter directory under a fetched fixture."""
    from apore.knowledge.chapter import find_chapter_with_graph

    ready = find_chapter_with_graph(fixture_root)
    if ready is not None:
        return ready

    best: tuple[Path, int] | None = None
    for wiki_dir in fixture_root.glob("**/wiki"):
        if not wiki_dir.is_dir():
            continue
        count = sum(
            1 for p in wiki_dir.glob("*.md") if p.is_file() and p.name != "_index.md"
        )
        if count == 0:
            continue
        chapter_root = wiki_dir.parent
        if best is None or count > best[1]:
            best = (chapter_root, count)
    return best[0] if best else None
