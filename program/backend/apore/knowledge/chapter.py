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
    teaching_order: list[str] = field(default_factory=list)

    def get(self, concept_id: str) -> ConceptNode | None:
        return self.nodes.get(concept_id)

    def ordered_ids(self) -> list[str]:
        """Concept ids in manual teaching order, falling back to depth-then-id.

        Independent of prerequisite edges and Study selection; used only for
        setup-facing ordering (wiki list, question bank grouping/generation).
        """
        ids = list(self.nodes.keys())
        if self.teaching_order and set(self.teaching_order) == set(ids):
            return [cid for cid in self.teaching_order if cid in self.nodes]
        return sorted(ids, key=lambda cid: (self.nodes[cid].depth, cid))

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
    raise ValueError(f"Unknown knowledge_source {source!r}; use fixture:name or domain:id/chapter")


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
    stored_order = raw.get("teaching_order")
    teaching_order = (
        [str(cid) for cid in stored_order] if isinstance(stored_order, list) else []
    )
    graph = ConceptGraph(edges=list(raw.get("edges") or []), teaching_order=teaching_order)
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
    allowed_concept_ids: set[str] | None = None,
) -> str:
    """Pick the next concept id for question generation.

    ``mastery`` is BKT-derived P(L) (PROGRESSION.md). Missing keys are treated
    as never observed (New). Covered threshold remains 0.7.

    Weak-points mode prefers observed-but-not-proficient concepts, then falls
    back to never-seen / uncovered as before.
    """
    mastery = mastery or {}
    if (
        requested_id
        and requested_id in graph.nodes
        and (allowed_concept_ids is None or requested_id in allowed_concept_ids)
    ):
        return requested_id

    if not graph.nodes:
        return requested_id or "unknown"

    nodes = [
        n
        for n in graph.nodes.values()
        if allowed_concept_ids is None or n.id in allowed_concept_ids
    ]
    if not nodes:
        return requested_id or "unknown"

    def _p(cid: str) -> float:
        return mastery.get(cid, 0.0)

    uncovered = [n for n in nodes if _p(n.id) < 0.7]
    if weak_only:
        observed_weak = [n for n in uncovered if n.id in mastery]
        pool = observed_weak or uncovered
    else:
        pool = uncovered or list(nodes)
    if not pool:
        return requested_id or "unknown"
    pool.sort(key=lambda n: (_p(n.id), n.depth, n.id))
    return pool[0].id


def resolve_wiki_page(
    wiki_dir: Path, concept_id: str, source_file: str | None = None
) -> Path | None:
    """Locate the wiki page file for a concept within ``wiki_dir``.

    Handles the common mismatch where concept ids are snake_case
    (``set_operations``) while bootstrapped wiki files stay kebab-case
    (``set-operations.md``). Tries, in order: ``{concept_id}.md`` / ``.html``,
    the node's declared ``source_file``, then the kebab-cased id.
    """
    candidates = [f"{concept_id}.md", f"{concept_id}.html"]
    if source_file:
        candidates.append(source_file)
    kebab = concept_id.replace("_", "-")
    if kebab != concept_id:
        candidates.extend([f"{kebab}.md", f"{kebab}.html"])
    for name in candidates:
        candidate = wiki_dir / name
        if candidate.is_file():
            return candidate
    return None


def get_wiki_paths(chapter: ChapterContext, concept_id: str, graph: ConceptGraph) -> list[Path]:
    """Wiki files for target concept and DAG neighbors."""
    wiki_dir = chapter.wiki_dir
    if not wiki_dir.is_dir():
        return _legacy_fixture_wiki(chapter.chapter_root, concept_id)

    paths: list[Path] = []
    target_node = graph.get(concept_id)
    target = resolve_wiki_page(
        wiki_dir, concept_id, target_node.source_file if target_node else None
    )
    if target is not None:
        paths.append(target)

    for neighbor_id in graph.neighbor_ids(concept_id):
        neighbor_node = graph.get(neighbor_id)
        p = resolve_wiki_page(
            wiki_dir, neighbor_id, neighbor_node.source_file if neighbor_node else None
        )
        if p is not None and p not in paths:
            paths.append(p)

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
