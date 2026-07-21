"""Versioned chapter compile artifacts: contracts, validation, and atomic publish.

A chapter's compiled knowledge lives in three tiers:

1. Immutable sources under ``sources/`` (originals + ``_normalized/`` markdown),
   summarized by ``sources/_manifest.json`` (see ``apore.setup.sources``).
2. A staged compile under ``.compile/staging/`` produced by the LLM compiler,
   never read by the tutor until approved.
3. The published, approved artifact at the chapter root (``wiki/``,
   ``concept-graph.json``, ``_index.md``, ``compile.json``) which Study and
   question generation consume.

Approval (``.approved.json``) records which compile version and source hash the
researcher signed off on. Question generation is gated on an approved,
non-stale artifact.
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

WIKI_DIRNAME = "wiki"
GRAPH_NAME = "concept-graph.json"
INDEX_NAME = "_index.md"
COMPILE_META_NAME = "compile.json"
COMPILE_DIRNAME = ".compile"
STAGING_DIRNAME = "staging"
COMPILE_STATE_NAME = "state.json"
APPROVED_NAME = ".approved.json"

ACTIVE_STAGES = frozenset({"normalizing", "compiling", "validating"})
TERMINAL_STAGES = frozenset({"ready", "failed", "interrupted"})
ALL_STAGES = ACTIVE_STAGES | TERMINAL_STAGES | {"idle"}

_CONCEPT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_]*$")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Compiled artifact contracts
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CompiledWikiPage:
    """A single concept-oriented wiki page produced by the compiler."""

    concept_id: str
    label: str
    body: str
    citations: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CompiledEdge:
    """A trusted prerequisite edge between two concepts."""

    source: str
    target: str
    relation: str = "prerequisite_of"
    provenance: str = "source_explicit"
    confidence: str = "EXTRACTED"


@dataclass
class CompiledArtifact:
    """The full compiler output for a chapter, prior to file materialization."""

    pages: list[CompiledWikiPage]
    edges: list[CompiledEdge] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> CompiledArtifact:
        pages: list[CompiledWikiPage] = []
        for item in data.get("pages") or []:
            if not isinstance(item, dict):
                continue
            citations = item.get("citations") or []
            if not isinstance(citations, list):
                citations = [citations]
            pages.append(
                CompiledWikiPage(
                    concept_id=str(item.get("concept_id", "")).strip(),
                    label=str(item.get("label", "")).strip(),
                    body=str(item.get("body", "")).strip(),
                    citations=[str(c).strip() for c in citations if str(c).strip()],
                )
            )
        edges: list[CompiledEdge] = []
        for item in data.get("edges") or []:
            if not isinstance(item, dict):
                continue
            src = str(item.get("source", "")).strip()
            tgt = str(item.get("target", "")).strip()
            if not src or not tgt:
                continue
            edges.append(
                CompiledEdge(
                    source=src,
                    target=tgt,
                    relation=str(item.get("relation", "prerequisite_of")).strip()
                    or "prerequisite_of",
                    provenance=str(item.get("provenance", "source_explicit")).strip()
                    or "source_explicit",
                    confidence=str(item.get("confidence", "EXTRACTED")).strip()
                    or "EXTRACTED",
                )
            )
        return cls(pages=pages, edges=edges)


class ArtifactValidationError(ValueError):
    """Raised when a compiled artifact fails validation."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


def detect_cycle(node_ids: list[str], edges: list[CompiledEdge]) -> list[str] | None:
    """Return a cycle path if the prerequisite graph is cyclic, else None."""
    adjacency: dict[str, list[str]] = {nid: [] for nid in node_ids}
    for edge in edges:
        if edge.source in adjacency and edge.target in adjacency:
            adjacency[edge.source].append(edge.target)

    WHITE, GRAY, BLACK = 0, 1, 2
    color = {nid: WHITE for nid in node_ids}
    stack: list[str] = []

    def visit(node: str) -> list[str] | None:
        color[node] = GRAY
        stack.append(node)
        for nxt in adjacency[node]:
            if color[nxt] == GRAY:
                idx = stack.index(nxt)
                return stack[idx:] + [nxt]
            if color[nxt] == WHITE:
                found = visit(nxt)
                if found:
                    return found
        stack.pop()
        color[node] = BLACK
        return None

    for nid in node_ids:
        if color[nid] == WHITE:
            found = visit(nid)
            if found:
                return found
    return None


def compute_depths(node_ids: list[str], edges: list[CompiledEdge]) -> dict[str, int]:
    """Longest-path depth per node (roots = 0). Assumes an acyclic graph."""
    adjacency: dict[str, list[str]] = {nid: [] for nid in node_ids}
    indegree: dict[str, int] = {nid: 0 for nid in node_ids}
    for edge in edges:
        if edge.source in adjacency and edge.target in indegree:
            adjacency[edge.source].append(edge.target)
            indegree[edge.target] += 1

    depth = {nid: 0 for nid in node_ids}
    queue = [nid for nid in node_ids if indegree[nid] == 0]
    while queue:
        node = queue.pop(0)
        for nxt in adjacency[node]:
            depth[nxt] = max(depth[nxt], depth[node] + 1)
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)
    return depth


def default_teaching_order(nodes: list[dict]) -> list[str]:
    """Depth-then-id ordering, the implicit teaching order for graphs without one."""

    def _key(node: dict) -> tuple[int, str]:
        return (int(node.get("depth", 0) or 0), str(node.get("id", "")))

    return [str(node.get("id")) for node in sorted(nodes, key=_key) if node.get("id")]


def resolve_teaching_order(graph: dict) -> list[str]:
    """Return the concept ids in teaching order.

    Uses the persisted ``teaching_order`` when it is an exact permutation of the
    graph's node ids; otherwise falls back to the depth-then-id default. Never
    reads or mutates prerequisite ``edges`` or node ``depth``.
    """
    nodes = graph.get("nodes") or []
    node_ids = [str(node.get("id")) for node in nodes if node.get("id")]
    stored = graph.get("teaching_order")
    if (
        isinstance(stored, list)
        and len(stored) == len(node_ids)
        and set(map(str, stored)) == set(node_ids)
    ):
        return [str(cid) for cid in stored]
    return default_teaching_order(nodes)


def write_teaching_order(directory: Path, order: list[str]) -> None:
    """Persist a validated teaching hierarchy into ``concept-graph.json``.

    ``order`` must be an exact permutation of the graph's node ids. The human's
    ordering becomes the learning hierarchy: ``teaching_order`` is stored, the
    prerequisite ``edges`` are replaced by a linear chain along the order, and
    each node's ``depth`` is set to its position in the order (0-based).
    """
    graph_path = directory / GRAPH_NAME
    graph = _read_json(graph_path)
    if not graph:
        raise FileNotFoundError(f"No concept graph at {graph_path}")

    node_ids = [str(node.get("id")) for node in (graph.get("nodes") or []) if node.get("id")]
    requested = [str(cid) for cid in order]
    if len(requested) != len(node_ids) or set(requested) != set(node_ids):
        raise ArtifactValidationError(
            ["teaching order must be an exact permutation of the graph concept ids"]
        )

    depth_by_id = {concept_id: index for index, concept_id in enumerate(requested)}
    for node in graph.get("nodes") or []:
        concept_id = node.get("id")
        if concept_id in depth_by_id:
            node["depth"] = depth_by_id[concept_id]

    graph["edges"] = [
        {
            "source": requested[i],
            "target": requested[i + 1],
            "relation": "prerequisite_of",
            "provenance": "human_reorder",
            "confidence": "DECLARED",
        }
        for i in range(len(requested) - 1)
    ]
    graph["teaching_order"] = requested
    tmp = graph_path.with_suffix(graph_path.suffix + ".tmp")
    tmp.write_text(json.dumps(graph, indent=2) + "\n", encoding="utf-8")
    tmp.replace(graph_path)


def validate_compiled_artifact(
    artifact: CompiledArtifact, valid_source_ids: set[str]
) -> list[str]:
    """Return validation errors; empty list means the artifact is publishable."""
    errors: list[str] = []

    if not artifact.pages:
        errors.append("compiled artifact has no wiki pages")

    seen: set[str] = set()
    concept_ids: list[str] = []
    for page in artifact.pages:
        cid = page.concept_id
        if not cid:
            errors.append("wiki page is missing concept_id")
            continue
        if not _CONCEPT_ID_RE.match(cid):
            errors.append(f"invalid concept_id {cid!r} (use snake_case: a-z0-9_)")
        if cid in seen:
            errors.append(f"duplicate concept_id: {cid!r}")
        seen.add(cid)
        concept_ids.append(cid)
        if not page.label.strip():
            errors.append(f"wiki page {cid!r} is missing a label")
        if not page.body.strip():
            errors.append(f"wiki page {cid!r} has empty body")
        if not page.citations:
            errors.append(f"wiki page {cid!r} has no source citations")
        for citation in page.citations:
            if valid_source_ids and citation not in valid_source_ids:
                errors.append(
                    f"wiki page {cid!r} cites unknown source {citation!r}"
                )

    known = set(concept_ids)
    for edge in artifact.edges:
        if edge.source == edge.target:
            errors.append(f"self-referential edge on concept {edge.source!r}")
        if edge.source not in known:
            errors.append(f"edge references unknown source concept {edge.source!r}")
        if edge.target not in known:
            errors.append(f"edge references unknown target concept {edge.target!r}")

    if not errors:
        cycle = detect_cycle(concept_ids, artifact.edges)
        if cycle:
            errors.append("prerequisite graph is cyclic: " + " -> ".join(cycle))

    return errors


# ---------------------------------------------------------------------------
# Artifact file materialization
# ---------------------------------------------------------------------------


def _render_wiki_page(page: CompiledWikiPage) -> str:
    citations = "\n".join(f"- {c}" for c in page.citations)
    return f"# {page.label}\n\n{page.body}\n\n## Sources\n\n{citations}\n"


def _render_index(pages: list[CompiledWikiPage], depths: dict[str, int]) -> str:
    lines = ["# Chapter index", ""]
    for page in sorted(pages, key=lambda p: (depths.get(p.concept_id, 0), p.concept_id)):
        lines.append(
            f"- [{page.label}]({page.concept_id}.md) "
            f"(depth {depths.get(page.concept_id, 0)})"
        )
    return "\n".join(lines) + "\n"


def write_artifact_files(
    target_dir: Path,
    artifact: CompiledArtifact,
    *,
    source_hash: str,
    version: int,
    generated_at: str | None = None,
) -> None:
    """Materialize a validated artifact into ``target_dir`` (staging or publish).

    Writes ``wiki/*.md``, ``_index.md``, ``concept-graph.json`` and
    ``compile.json``. Any pre-existing ``wiki/`` in the target is replaced.
    """
    generated_at = generated_at or _now_iso()
    concept_ids = [p.concept_id for p in artifact.pages]
    depths = compute_depths(concept_ids, artifact.edges)

    wiki_dir = target_dir / WIKI_DIRNAME
    if wiki_dir.exists():
        shutil.rmtree(wiki_dir)
    wiki_dir.mkdir(parents=True, exist_ok=True)

    for page in artifact.pages:
        (wiki_dir / f"{page.concept_id}.md").write_text(
            _render_wiki_page(page), encoding="utf-8"
        )

    (target_dir / INDEX_NAME).write_text(
        _render_index(artifact.pages, depths), encoding="utf-8"
    )

    graph = {
        "nodes": [
            {
                "id": page.concept_id,
                "label": page.label,
                "source_file": page.citations[0] if page.citations else None,
                "citations": page.citations,
                "depth": depths.get(page.concept_id, 0),
            }
            for page in artifact.pages
        ],
        "edges": [
            {
                "source": edge.source,
                "target": edge.target,
                "relation": edge.relation,
                "provenance": edge.provenance,
                "confidence": edge.confidence,
            }
            for edge in artifact.edges
        ],
    }
    (target_dir / GRAPH_NAME).write_text(
        json.dumps(graph, indent=2) + "\n", encoding="utf-8"
    )

    meta = {
        "version": version,
        "source_hash": source_hash,
        "generated_at": generated_at,
        "concept_count": len(artifact.pages),
        "edge_count": len(artifact.edges),
    }
    (target_dir / COMPILE_META_NAME).write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Directory helpers
# ---------------------------------------------------------------------------


def compile_dir(chapter_root: Path) -> Path:
    return chapter_root / COMPILE_DIRNAME


def staging_dir(chapter_root: Path) -> Path:
    return compile_dir(chapter_root) / STAGING_DIRNAME


def _read_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


# ---------------------------------------------------------------------------
# Compile state persistence
# ---------------------------------------------------------------------------


def idle_compile_state() -> dict:
    return {
        "stage": "idle",
        "version": 0,
        "source_hash": None,
        "progress": {"done": 0, "total": 0},
        "error_code": None,
        "error_message": None,
        "started_at": None,
        "updated_at": None,
        "run_token": None,
    }


def load_compile_state(chapter_root: Path) -> dict:
    data = _read_json(compile_dir(chapter_root) / COMPILE_STATE_NAME)
    if not data:
        return idle_compile_state()
    merged = idle_compile_state()
    merged.update(data)
    if not isinstance(merged.get("progress"), dict):
        merged["progress"] = {"done": 0, "total": 0}
    return merged


def save_compile_state(chapter_root: Path, state: dict) -> None:
    directory = compile_dir(chapter_root)
    directory.mkdir(parents=True, exist_ok=True)
    state = {**state, "updated_at": _now_iso()}
    (directory / COMPILE_STATE_NAME).write_text(
        json.dumps(state, indent=2) + "\n", encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Approval state
# ---------------------------------------------------------------------------


def load_approval(chapter_root: Path) -> dict | None:
    """Return the recorded approval, or a synthesized legacy approval.

    Chapters that predate this pipeline have ``wiki/`` + ``concept-graph.json``
    but no ``.approved.json``. They are treated as an approved legacy version so
    Study and question generation keep working until the chapter is recompiled.
    """
    data = _read_json(chapter_root / APPROVED_NAME)
    if data:
        return data

    graph = _read_json(chapter_root / GRAPH_NAME)
    wiki = chapter_root / WIKI_DIRNAME
    has_wiki = wiki.is_dir() and any(
        p.name != INDEX_NAME for p in wiki.glob("*.md")
    )
    if graph and (graph.get("nodes") or has_wiki):
        return {
            "version": 0,
            "source_hash": None,
            "approved_at": None,
            "legacy": True,
        }
    return None


def save_approval(chapter_root: Path, *, version: int, source_hash: str | None) -> dict:
    approval = {
        "version": version,
        "source_hash": source_hash,
        "approved_at": _now_iso(),
        "legacy": False,
    }
    (chapter_root / APPROVED_NAME).write_text(
        json.dumps(approval, indent=2) + "\n", encoding="utf-8"
    )
    return approval


# ---------------------------------------------------------------------------
# Atomic publish
# ---------------------------------------------------------------------------


def publish_staging(chapter_root: Path) -> None:
    """Copy the staged compile into the chapter root, with rollback on failure.

    The published tree (``wiki/``, ``concept-graph.json``, ``_index.md``,
    ``compile.json``) is replaced only if the whole copy succeeds; on error the
    previous published files are restored.
    """
    staging = staging_dir(chapter_root)
    if not staging.is_dir():
        raise FileNotFoundError(f"No staged compile under {staging}")

    published_names = [WIKI_DIRNAME, GRAPH_NAME, INDEX_NAME, COMPILE_META_NAME]
    backup = compile_dir(chapter_root) / "_publish_backup"
    if backup.exists():
        shutil.rmtree(backup)
    backup.mkdir(parents=True, exist_ok=True)

    moved: list[str] = []
    try:
        for name in published_names:
            current = chapter_root / name
            if current.exists():
                shutil.move(str(current), str(backup / name))
                moved.append(name)
        for name in published_names:
            staged = staging / name
            if not staged.exists():
                continue
            dest = chapter_root / name
            if staged.is_dir():
                shutil.copytree(staged, dest)
            else:
                shutil.copy2(staged, dest)
    except Exception:
        for name in published_names:
            dest = chapter_root / name
            if dest.exists():
                if dest.is_dir():
                    shutil.rmtree(dest)
                else:
                    dest.unlink()
        for name in moved:
            shutil.move(str(backup / name), str(chapter_root / name))
        raise
    finally:
        if backup.exists():
            shutil.rmtree(backup, ignore_errors=True)


# ---------------------------------------------------------------------------
# Aggregate status
# ---------------------------------------------------------------------------


def _reconcile_interrupted(state: dict, live_run_tokens: set[str]) -> dict:
    """Mark a persisted-but-not-live active job as interrupted."""
    stage = state.get("stage")
    token = state.get("run_token")
    if stage in ACTIVE_STAGES and token not in live_run_tokens:
        return {
            **state,
            "stage": "interrupted",
            "error_code": "interrupted",
            "error_message": "Compilation was interrupted (server restarted). Retry.",
        }
    return state


def chapter_artifact_status(
    chapter_root: Path,
    *,
    current_source_hash: str | None,
    live_run_tokens: set[str] | None = None,
) -> dict:
    """Assemble the compile/approval status for one chapter (API + catalog)."""
    live_run_tokens = live_run_tokens or set()
    compile_state = _reconcile_interrupted(
        load_compile_state(chapter_root), live_run_tokens
    )
    approval = load_approval(chapter_root)

    staged_meta = _read_json(staging_dir(chapter_root) / COMPILE_META_NAME)
    staged_ready = (
        compile_state.get("stage") == "ready"
        and staged_meta is not None
    )

    is_approved = approval is not None
    approved_hash = approval.get("source_hash") if approval else None

    is_stale = False
    if (
        approval is not None
        and approved_hash is not None
        and current_source_hash is not None
        and approved_hash != current_source_hash
    ):
        is_stale = True

    unapproved_compile = False
    if staged_ready and staged_meta is not None:
        staged_hash = staged_meta.get("source_hash")
        if approval is None or staged_meta.get("version") != approval.get("version"):
            unapproved_compile = True
        if (
            current_source_hash is not None
            and staged_hash == current_source_hash
            and approved_hash != current_source_hash
        ):
            unapproved_compile = True

    graph = _read_json(chapter_root / GRAPH_NAME)
    concept_count = len(graph.get("nodes") or []) if graph else 0
    wiki = chapter_root / WIKI_DIRNAME
    wiki_count = (
        len([p for p in wiki.glob("*.md") if p.name != INDEX_NAME])
        if wiki.is_dir()
        else 0
    )

    return {
        "source_hash": current_source_hash,
        "compile": {
            "stage": compile_state.get("stage", "idle"),
            "version": compile_state.get("version", 0),
            "source_hash": compile_state.get("source_hash"),
            "progress": compile_state.get("progress", {"done": 0, "total": 0}),
            "error_code": compile_state.get("error_code"),
            "error_message": compile_state.get("error_message"),
            "started_at": compile_state.get("started_at"),
            "updated_at": compile_state.get("updated_at"),
        },
        "approved": approval,
        "is_approved": is_approved,
        "is_stale": is_stale,
        "has_unapproved_compile": unapproved_compile,
        "wiki_count": wiki_count,
        "concept_count": concept_count,
    }
