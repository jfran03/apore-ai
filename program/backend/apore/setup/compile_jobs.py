"""Durable, file-backed lifecycle for chapter compilation jobs.

Compile progress is persisted to ``.compile/state.json`` so it survives across
requests. A small in-memory registry tracks which run tokens are actually
executing in this process; if the server restarts while a compile was running,
the persisted "compiling" stage is reconciled to "interrupted" (retryable)
rather than appearing to run forever.
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from apore.providers.base import Provider
from apore.setup.artifacts import (
    ArtifactValidationError,
    chapter_artifact_status,
    idle_compile_state,
    load_approval,
    load_compile_state,
    publish_staging,
    resolve_teaching_order,
    save_approval,
    save_compile_state,
    staging_dir,
)
from apore.setup.artifacts import (
    COMPILE_META_NAME,
    GRAPH_NAME,
    INDEX_NAME,
    WIKI_DIRNAME,
)
from apore.setup.compile import CompileError, compile_to_staging
from apore.setup import sources as sources_module
from apore.knowledge.chapter import resolve_wiki_page

import json

_registry_lock = threading.Lock()
_active: dict[str, str] = {}  # chapter key -> run token


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _key(chapter_root: Path) -> str:
    return str(chapter_root.resolve())


def live_run_tokens() -> set[str]:
    with _registry_lock:
        return set(_active.values())


def reset_jobs_for_testing() -> None:
    with _registry_lock:
        _active.clear()


def _next_version(chapter_root: Path) -> int:
    state = load_compile_state(chapter_root)
    approval = load_approval(chapter_root)
    approved_version = approval.get("version", 0) if approval else 0
    return max(int(state.get("version", 0)), int(approved_version)) + 1


def get_compile_status(chapter_root: Path) -> dict:
    """Compile-only status, with interrupted reconciliation."""
    full = chapter_artifact_status(
        chapter_root,
        current_source_hash=sources_module.source_hash(chapter_root),
        live_run_tokens=live_run_tokens(),
    )
    return full["compile"]


def _run_compile_job(
    chapter_root: Path,
    *,
    provider: Provider,
    model: str,
    program_root: Path,
    version: int,
    source_hash: str,
    run_token: str,
) -> None:
    base = {
        "version": version,
        "source_hash": source_hash,
        "run_token": run_token,
        "started_at": _now_iso(),
        "progress": {"done": 0, "total": 1},
        "error_code": None,
        "error_message": None,
    }
    try:
        save_compile_state(chapter_root, {**base, "stage": "compiling"})
        save_compile_state(chapter_root, {**base, "stage": "validating"})
        compile_to_staging(
            chapter_root,
            provider=provider,
            model=model,
            program_root=program_root,
            version=version,
            source_hash=source_hash,
        )
        save_compile_state(
            chapter_root,
            {**base, "stage": "ready", "progress": {"done": 1, "total": 1}},
        )
    except ArtifactValidationError as exc:
        save_compile_state(
            chapter_root,
            {
                **base,
                "stage": "failed",
                "error_code": "validation_failed",
                "error_message": str(exc),
            },
        )
    except CompileError as exc:
        save_compile_state(
            chapter_root,
            {
                **base,
                "stage": "failed",
                "error_code": "compile_failed",
                "error_message": str(exc),
            },
        )
    except Exception as exc:  # noqa: BLE001 - surface any provider error to the UI
        save_compile_state(
            chapter_root,
            {
                **base,
                "stage": "failed",
                "error_code": "internal_error",
                "error_message": str(exc),
            },
        )
    finally:
        with _registry_lock:
            if _active.get(_key(chapter_root)) == run_token:
                _active.pop(_key(chapter_root), None)


def start_compile(
    chapter_root: Path,
    *,
    provider: Provider,
    model: str,
    program_root: Path,
    thread_runner: Callable[..., None] | None = None,
) -> dict:
    """Start (or return the already-running) compile job for a chapter."""
    key = _key(chapter_root)
    with _registry_lock:
        if key in _active:
            return get_compile_status(chapter_root)

    source_hash = sources_module.source_hash(chapter_root)
    if source_hash is None:
        raise ValueError("Add at least one source before compiling.")
    if not sources_module.normalized_texts(chapter_root):
        raise ValueError(
            "No sources normalized successfully. Fix or remove failed sources first."
        )

    version = _next_version(chapter_root)
    run_token = str(uuid.uuid4())

    with _registry_lock:
        _active[key] = run_token

    save_compile_state(
        chapter_root,
        {
            **idle_compile_state(),
            "stage": "normalizing",
            "version": version,
            "source_hash": source_hash,
            "run_token": run_token,
            "started_at": _now_iso(),
            "progress": {"done": 0, "total": 1},
        },
    )

    kwargs = {
        "chapter_root": chapter_root,
        "provider": provider,
        "model": model,
        "program_root": program_root,
        "version": version,
        "source_hash": source_hash,
        "run_token": run_token,
    }
    runner = thread_runner or _spawn_thread
    runner(**kwargs)
    return get_compile_status(chapter_root)


def _spawn_thread(**kwargs) -> None:
    thread = threading.Thread(target=_run_compile_job, kwargs=kwargs, daemon=True)
    thread.start()


def approve_compile(chapter_root: Path) -> dict:
    """Publish the staged compile and record approval. Returns full status."""
    state = load_compile_state(chapter_root)
    if state.get("stage") != "ready":
        raise ValueError("No compiled version is ready to approve.")

    staging = staging_dir(chapter_root)
    meta_path = staging / COMPILE_META_NAME
    if not meta_path.is_file():
        raise ValueError("Staged compile is missing; recompile before approving.")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    publish_staging(chapter_root)
    save_approval(
        chapter_root,
        version=int(meta.get("version", state.get("version", 1))),
        source_hash=meta.get("source_hash"),
    )
    return chapter_artifact_status(
        chapter_root,
        current_source_hash=sources_module.source_hash(chapter_root),
        live_run_tokens=live_run_tokens(),
    )


def _read_graph(directory: Path) -> dict:
    path = directory / GRAPH_NAME
    if not path.is_file():
        return {"nodes": [], "edges": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"nodes": [], "edges": []}


def load_wiki_preview(chapter_root: Path, source: str) -> dict:
    """Return wiki pages + edges from the staged or published artifact."""
    if source == "staging":
        directory = staging_dir(chapter_root)
        if not directory.is_dir():
            raise FileNotFoundError("No staged compile to preview.")
        version = int(load_compile_state(chapter_root).get("version", 0))
    elif source == "published":
        directory = chapter_root
        approval = load_approval(chapter_root)
        version = int(approval.get("version", 0)) if approval else 0
    else:
        raise ValueError("source must be 'staging' or 'published'")

    graph = _read_graph(directory)
    wiki_dir = directory / WIKI_DIRNAME
    order = resolve_teaching_order(graph)
    order_index = {concept_id: index for index, concept_id in enumerate(order)}
    pages = []
    for node in graph.get("nodes", []):
        concept_id = node.get("id")
        if not concept_id:
            continue
        page_path = resolve_wiki_page(wiki_dir, concept_id, node.get("source_file"))
        body = page_path.read_text(encoding="utf-8") if page_path else ""
        pages.append(
            {
                "concept_id": concept_id,
                "label": node.get("label", concept_id),
                "depth": int(node.get("depth", 0)),
                "body": body,
            }
        )
    pages.sort(key=lambda p: order_index.get(p["concept_id"], len(order_index)))
    for index, page in enumerate(pages):
        page["order"] = index
    return {
        "source": source,
        "version": version,
        "pages": pages,
        "edges": graph.get("edges", []),
    }
