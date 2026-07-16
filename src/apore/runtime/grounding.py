"""Structured grounding slices for LLM prompts."""

from __future__ import annotations

from pathlib import Path

from markitdown import MarkItDown

from apore.knowledge.chapter import ChapterContext, ConceptGraph

_markitdown = MarkItDown()


def _read_wiki(path: Path) -> str:
    if path.suffix.lower() in {".md", ".txt"}:
        return path.read_text(encoding="utf-8")
    return _markitdown.convert(str(path)).text_content


def build_grounding_slice(
    chapter: ChapterContext,
    graph: ConceptGraph,
    concept_id: str,
    wiki_paths: list[Path],
) -> str:
    node = graph.get(concept_id)
    label = graph.label_for(concept_id)
    depth = node.depth if node else 0

    lines = [
        "## Target Concept",
        f"id: {concept_id}",
        f"label: {label}",
        f"depth: {depth}",
        "",
    ]

    prereq = graph.prerequisite_ids(concept_id)
    neighbors = graph.neighbor_ids(concept_id)
    if prereq or neighbors:
        lines.append("## DAG neighbors")
        for nid in prereq:
            n = graph.get(nid)
            nd = n.depth if n else "?"
            nl = graph.label_for(nid)
            lines.append(f"- {nid} (depth {nd}) — prerequisite: {nl}")
        for nid in neighbors:
            if nid in prereq:
                continue
            n = graph.get(nid)
            nd = n.depth if n else "?"
            nl = graph.label_for(nid)
            lines.append(f"- {nid} (depth {nd}): {nl}")
        lines.append("")

    lines.append("## Wiki content")
    if wiki_paths:
        for p in wiki_paths:
            lines.append(f"### {p.stem}")
            try:
                lines.append(_read_wiki(p))
            except Exception as exc:
                lines.append(f"(failed to read {p.name}: {exc})")
            lines.append("")
    else:
        lines.append(
            "(No wiki files matched this concept. Use only material that would appear "
            f"under wiki/{concept_id}.md once compiled.)"
        )

    return "\n".join(lines).strip()
