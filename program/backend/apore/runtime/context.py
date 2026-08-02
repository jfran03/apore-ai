"""Context assembly for LLM calls (PRD §5.3)."""

from __future__ import annotations

from pathlib import Path

from apore.knowledge.chapter import ChapterContext, ConceptGraph
from apore.runtime.grounding import build_grounding_slice
from apore.runtime.paths import get_program_root

_VALID_PROTOCOLS = {
    "generate-question",
    "generate-question-bank",
    "extract-signals",
    "tutor-turn",
    "grade-answer",
    "scratchpad-ask",
    "scratchpad-grade",
}


def assemble_prompt(
    protocol: str,
    learner_state_path: Path,
    *,
    concept_id: str,
    chapter: ChapterContext,
    graph: ConceptGraph,
    wiki_paths: list[Path],
    program_root: Path | None = None,
) -> dict:
    """Return {"system": str, "messages": [{"role": "user", "content": str}]}."""
    if protocol not in _VALID_PROTOCOLS:
        raise ValueError(f"Unknown protocol {protocol!r}; expected one of {_VALID_PROTOCOLS}")

    root = program_root if program_root is not None else get_program_root()

    system = (root / "AGENTS.md").read_text(encoding="utf-8")

    protocol_text = (root / "shared" / "protocols" / f"{protocol}.md").read_text(encoding="utf-8")

    grounding_text = build_grounding_slice(chapter, graph, concept_id, wiki_paths)

    learner_state_text = learner_state_path.read_text(encoding="utf-8")

    user_content = (
        f"## Protocol\n\n{protocol_text}\n\n"
        f"## Grounding Context\n\n{grounding_text}\n\n"
        f"## Learner State\n\n{learner_state_text}"
    )

    if protocol != "extract-signals":
        domain_md = chapter.chapter_root.parent.parent / "DOMAIN.md"
        if domain_md.is_file():
            domain_text = domain_md.read_text(encoding="utf-8").strip()
            if domain_text:
                user_content = f"## Domain Guidance\n\n{domain_text}\n\n{user_content}"

    return {
        "system": system,
        "messages": [{"role": "user", "content": user_content}],
    }
