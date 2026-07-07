"""Resolve chapter roots and concept graphs from fixtures or user domains."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from apore.fixtures.aliases import fixture_to_domain_chapter


@dataclass(frozen=True)
class ConceptNode:
    id: str
    label: str
    depth: int
    source_file: str | None = None


@dataclass
class ConceptGraph:
    nodes: dict[str, ConceptNode] = field(default_factory=dict)
    edges: list[dict] = field(default_factory=list)

    def get(self, concept_id: str) -> ConceptNode | None:
        return self.nodes.get(concept_id)

    def label_for(self, concept_id: str) -> str:
        node = self.nodes.get(concept_id)
        if node:
            return node.label
        return _humanize_id(concept_id)

    def prerequisite_ids(self, concept_id: str) -> list[str]:
        out: list[str] = []
        for edge in self.edges:
            if edge.get("target") == concept_id and edge.get("relation") == "prerequisite_of":
                src = edge.get("source")
                if isinstance(src, str):
                    out.append(src)
        return out

    def neighbor_ids(self, concept_id: str) -> list[str]:
        seen: set[str] = set()
        for edge in self.edges:
            src, tgt = edge.get("source"), edge.get("target")
            if tgt == concept_id and isinstance(src, str):
                seen.add(src)
            if src == concept_id and isinstance(tgt, str):
                seen.add(tgt)
        return sorted(seen)


@dataclass(frozen=True)
class ChapterContext:
    knowledge_source: str
    chapter_root: Path
    display_name: str

    @property
    def concept_graph_path(self) -> Path:
        return self.chapter_root / "concept-graph.json"

    @property
    def wiki_dir(self) -> Path:
        return self.chapter_root / "wiki"

    @property
    def sources_dir(self) -> Path:
        return self.chapter_root / "sources"

    @property
    def question_bank_path(self) -> Path:
        return self.chapter_root / "question-bank.json"


def _humanize_id(concept_id: str) -> str:
    text = concept_id.replace("_", " ").replace("-", " ")
    return text.strip().title() if text else concept_id


def _parse_knowledge_source(source: str) -> tuple[str, str, str | None]:
    """Return (kind, primary, secondary) e.g. fixture, apore-lite, None."""
    if source.startswith("fixture:"):
        return "fixture", source.split(":", 1)[1], None
    if source.startswith("domain:"):
        rest = source.split(":", 1)[1]
        if "/" not in rest:
            raise ValueError(f"domain knowledge source must be domain:{{id}}/{{chapter}}, got {source!r}")
        domain_id, chapter_id = rest.split("/", 1)
        return "domain", domain_id, chapter_id
    if source.startswith("workspace:"):
        rest = source.split(":", 1)[1]
        if "/" not in rest:
            raise ValueError(
                f"workspace knowledge source must be workspace:{{id}}/{{chapter}}, got {source!r}"
            )
        domain_id, chapter_id = rest.split("/", 1)
        return "workspace", domain_id, chapter_id
    raise ValueError(f"Unknown knowledge_source {source!r}; use fixture:name, domain:id/chapter, or workspace:id/chapter")


def find_chapter_with_graph(root: Path) -> Path | None:
    if not root.exists():
        return None
    direct = root / "concept-graph.json"
    if direct.is_file():
        return root
    candidates = sorted(root.glob("**/concept-graph.json"))
    if not candidates:
        return None
    return candidates[0].parent


def resolve_chapter(knowledge_source: str, program_root: Path) -> ChapterContext:
    kind, primary, secondary = _parse_knowledge_source(knowledge_source)

    if kind == "fixture":
        mapped = fixture_to_domain_chapter(primary)
        if mapped is None:
            raise FileNotFoundError(
                f"Unknown fixture {primary!r}. "
                "Run POST /setup/fixtures/{name}/fetch for supported upstream templates."
            )
        domain_id, chapter_id = mapped
        return resolve_chapter(f"domain:{domain_id}/{chapter_id}", program_root)

    if kind == "workspace":
        from apore.domains.store import load_domain, chapters_dir

        assert secondary is not None
        record = load_domain(primary)
        chapter_root = chapters_dir(record) / secondary
        if not chapter_root.is_dir():
            raise FileNotFoundError(f"Chapter not found: {chapter_root}")
        return ChapterContext(
            knowledge_source=knowledge_source,
            chapter_root=chapter_root,
            display_name=f"{primary} / {secondary}",
        )

    assert secondary is not None
    chapter_root = program_root / "domains" / primary / "chapters" / secondary
    if not chapter_root.is_dir():
        raise FileNotFoundError(f"Chapter not found: {chapter_root}")
    return ChapterContext(
        knowledge_source=knowledge_source,
        chapter_root=chapter_root,
        display_name=f"{primary} / {secondary}",
    )


def load_concept_graph(chapter: ChapterContext) -> ConceptGraph:
    path = chapter.concept_graph_path
    if not path.is_file():
        return ConceptGraph()

    raw = json.loads(path.read_text(encoding="utf-8"))
    graph = ConceptGraph(edges=list(raw.get("edges") or []))
    for item in raw.get("nodes") or []:
        node_id = item.get("id")
        if not node_id:
            continue
        graph.nodes[node_id] = ConceptNode(
            id=node_id,
            label=item.get("label") or _humanize_id(node_id),
            depth=int(item.get("depth", 0)),
            source_file=item.get("source_file"),
        )
    return graph


def select_next_concept(
    graph: ConceptGraph,
    *,
    requested_id: str | None = None,
    mastery: dict[str, float] | None = None,
    scalar: float = 0.5,
    weak_only: bool = False,
) -> str:
    """Pick the next concept id for question generation."""
    mastery = mastery or {}
    if requested_id and requested_id in graph.nodes:
        return requested_id

    if not graph.nodes:
        return requested_id or "unknown"

    uncovered = [
        n
        for n in graph.nodes.values()
        if mastery.get(n.id, 0.0) < 0.7
    ]
    if weak_only:
        pool = uncovered
    else:
        pool = uncovered or list(graph.nodes.values())
    if not pool:
        return requested_id or "unknown"
    pool.sort(key=lambda n: (n.depth, n.id))
    return pool[0].id


def get_wiki_paths(chapter: ChapterContext, concept_id: str, graph: ConceptGraph) -> list[Path]:
    """Wiki files for target concept and DAG neighbors."""
    wiki_dir = chapter.wiki_dir
    if not wiki_dir.is_dir():
        return _legacy_fixture_wiki(chapter.chapter_root, concept_id)

    paths: list[Path] = []
    target = wiki_dir / f"{concept_id}.md"
    if target.is_file():
        paths.append(target)
    else:
        for ext in (".html", ".md"):
            alt = wiki_dir / f"{concept_id}{ext}"
            if alt.is_file():
                paths.append(alt)
                break

    for neighbor_id in graph.neighbor_ids(concept_id):
        for ext in (".md", ".html"):
            p = wiki_dir / f"{neighbor_id}{ext}"
            if p.is_file() and p not in paths:
                paths.append(p)
                break

    if paths:
        return paths
    return _legacy_fixture_wiki(chapter.chapter_root, concept_id)


def _legacy_fixture_wiki(chapter_root: Path, concept_id: str) -> list[Path]:
    """Fallback: apore-lite style **/wiki/**/*.html with stem match."""
    wiki_files = list(chapter_root.glob("**/wiki/**/*.html"))
    if not wiki_files:
        wiki_files = list(chapter_root.glob("**/*.html"))
    matched = [p for p in wiki_files if concept_id in p.stem]
    return matched if matched else wiki_files
