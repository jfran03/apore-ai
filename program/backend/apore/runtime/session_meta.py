"""Session title generation for learner-state markdown files."""

from __future__ import annotations

import logging
from typing import Literal

from apore.knowledge.chapter import ChapterContext, ConceptGraph, load_concept_graph
from apore.providers.base import Provider

logger = logging.getLogger(__name__)

FocusMode = Literal["adaptive", "weak_points"]

_FOCUS_SUFFIX = {
    "adaptive": "Adaptive Practice",
    "weak_points": "Weak Areas Review",
}


def _parse_domain_chapter(knowledge_source: str) -> tuple[str, str]:
    if knowledge_source.startswith("domain:"):
        rest = knowledge_source.split(":", 1)[1]
        if "/" in rest:
            domain_id, chapter_id = rest.split("/", 1)
            return domain_id, chapter_id
    return knowledge_source, ""


def fallback_session_title(
    *,
    knowledge_source: str,
    focus_mode: FocusMode = "adaptive",
) -> str:
    """Deterministic title when LLM is unavailable."""
    domain_id, chapter_id = _parse_domain_chapter(knowledge_source)
    topic = chapter_id.replace("-", " ").replace("_", " ").title() if chapter_id else domain_id
    suffix = _FOCUS_SUFFIX.get(focus_mode, _FOCUS_SUFFIX["adaptive"])
    if domain_id and chapter_id:
        return f"{topic} — {suffix}"
    return f"{knowledge_source} — {suffix}"


def _concept_summary(
    graph: ConceptGraph,
    *,
    concept_ids: list[str] | None = None,
    limit: int = 8,
) -> str:
    if concept_ids:
        nodes = [graph.nodes[cid] for cid in concept_ids if cid in graph.nodes]
    else:
        nodes = sorted(graph.nodes.values(), key=lambda n: (n.depth, n.id))
    labels = [n.label for n in nodes]
    if not labels:
        return "(no concepts)"
    shown = labels[:limit]
    tail = f" (+{len(labels) - limit} more)" if len(labels) > limit else ""
    return ", ".join(shown) + tail


def generate_session_title(
    *,
    chapter: ChapterContext,
    knowledge_source: str,
    focus_mode: FocusMode,
    max_questions: int,
    provider: Provider | None,
    model: str,
    program_root,
    concept_ids: list[str] | None = None,
) -> str:
    """Return a human-readable session title; always succeeds via fallback."""
    fallback = fallback_session_title(
        knowledge_source=knowledge_source,
        focus_mode=focus_mode,
    )
    if provider is None:
        return fallback

    try:
        graph = load_concept_graph(chapter)
    except (FileNotFoundError, ValueError):
        return fallback

    domain_id, chapter_id = _parse_domain_chapter(knowledge_source)
    system = (program_root / "AGENTS.md").read_text(encoding="utf-8")
    protocol = (
        program_root / "shared" / "protocols" / "generate-session-title.md"
    ).read_text(encoding="utf-8")
    user_content = (
        f"## Protocol\n\n{protocol}\n\n"
        f"## Chapter Context\n\n"
        f"domain: {domain_id}\n"
        f"chapter: {chapter_id}\n"
        f"display_name: {chapter.display_name or chapter_id}\n"
        f"concepts: {_concept_summary(graph, concept_ids=concept_ids)}\n"
        f"focus_mode: {focus_mode}\n"
        f"max_questions: {max_questions}\n"
    )
    try:
        raw = provider.invoke(
            system,
            [{"role": "user", "content": user_content}],
            model,
            {"protocol": "generate-session-title"},
        )
    except Exception:
        logger.exception("Session title LLM call failed")
        return fallback

    title = (raw or "").strip().splitlines()[0].strip().strip('"').strip("'")
    if not title or len(title) > 120:
        return fallback
    return title
