"""API tests for the source -> compile -> approve -> generate pipeline."""

from __future__ import annotations

import io
import shutil
import time
import uuid

import pytest
from fastapi.testclient import TestClient

import apore.api.app as app_module
import apore.setup.compile_jobs as compile_jobs
import apore.setup.question_bank_jobs as qb_jobs
from apore.api.app import app

client = TestClient(app)

_created_domains: list[str] = []


@pytest.fixture(autouse=True)
def clear_jobs():
    compile_jobs.reset_jobs_for_testing()
    qb_jobs.reset_jobs_for_testing()
    yield
    compile_jobs.reset_jobs_for_testing()
    qb_jobs.reset_jobs_for_testing()
    while _created_domains:
        domain_id = _created_domains.pop()
        shutil.rmtree(
            app_module.PROGRAM_ROOT / "domains" / domain_id, ignore_errors=True
        )


def _new_chapter() -> tuple[str, str]:
    domain_id = f"ctest_{uuid.uuid4().hex[:8]}"
    chapter_id = "ch01"
    assert client.post("/setup/domains", json={"domain_id": domain_id}).status_code == 200
    _created_domains.append(domain_id)
    assert (
        client.post(
            f"/setup/domains/{domain_id}/chapters", json={"chapter_id": chapter_id}
        ).status_code
        == 200
    )
    return domain_id, chapter_id


def _base(domain_id: str, chapter_id: str) -> str:
    return f"/setup/domains/{domain_id}/chapters/{chapter_id}"


def _poll_compile(base: str, timeout_s: float = 5.0) -> dict:
    deadline = time.time() + timeout_s
    last: dict = {}
    while time.time() < deadline:
        resp = client.get(f"{base}/compile/status")
        assert resp.status_code == 200
        last = resp.json()
        if last["stage"] in {"ready", "failed", "interrupted"}:
            return last
        time.sleep(0.05)
    raise AssertionError(f"compile did not finish: {last!r}")


def test_source_lifecycle():
    domain_id, chapter_id = _new_chapter()
    base = _base(domain_id, chapter_id)

    upload = client.post(
        f"{base}/sources",
        files=[("files", ("notes.md", io.BytesIO(b"# Notes\n\nSets."), "text/markdown"))],
    )
    assert upload.status_code == 200

    listed = client.get(f"{base}/sources")
    assert listed.status_code == 200
    sources = listed.json()["sources"]
    assert len(sources) == 1
    assert sources[0]["normalize_status"] == "ok"
    source_id = sources[0]["id"]

    deleted = client.delete(f"{base}/sources/{source_id}")
    assert deleted.status_code == 200
    assert deleted.json()["sources"] == []


def test_unsupported_source_rejected():
    domain_id, chapter_id = _new_chapter()
    base = _base(domain_id, chapter_id)
    resp = client.post(
        f"{base}/sources",
        files=[("files", ("clip.mp4", io.BytesIO(b"x"), "video/mp4"))],
    )
    assert resp.status_code == 400


def test_full_compile_approve_generate_flow():
    domain_id, chapter_id = _new_chapter()
    base = _base(domain_id, chapter_id)

    client.post(
        f"{base}/sources",
        files=[
            ("files", ("notes.md", io.BytesIO(b"# Notes\n\nSets and operations."), "text/markdown"))
        ],
    )

    started = client.post(f"{base}/compile")
    assert started.status_code == 202
    final = _poll_compile(base)
    assert final["stage"] == "ready"

    artifact = client.get(f"{base}/artifact").json()
    assert artifact["is_approved"] is False
    assert artifact["has_unapproved_compile"] is True

    wiki = client.get(f"{base}/wiki", params={"source": "staging"})
    assert wiki.status_code == 200
    assert wiki.json()["pages"]

    approved = client.post(f"{base}/compile/approve")
    assert approved.status_code == 200
    assert approved.json()["is_approved"] is True

    gen = client.post(f"{base}/question-bank/generate")
    assert gen.status_code == 202


def _write_published_graph(base: str, domain_id: str, chapter_id: str) -> None:
    """Materialize a multi-concept published artifact directly on disk."""
    import json

    root = app_module.PROGRAM_ROOT / "domains" / domain_id / "chapters" / chapter_id
    wiki = root / "wiki"
    wiki.mkdir(parents=True, exist_ok=True)
    graph = {
        "nodes": [
            {"id": "beta", "label": "Beta", "depth": 1},
            {"id": "alpha", "label": "Alpha", "depth": 0},
            {"id": "gamma", "label": "Gamma", "depth": 2},
        ],
        "edges": [
            {"source": "alpha", "target": "beta", "relation": "prerequisite_of"},
            {"source": "beta", "target": "gamma", "relation": "prerequisite_of"},
        ],
    }
    (root / "concept-graph.json").write_text(json.dumps(graph), encoding="utf-8")
    for node in graph["nodes"]:
        (wiki / f"{node['id']}.md").write_text(
            f"# {node['label']}\n\nBody for {node['id']}.\n", encoding="utf-8"
        )


def test_concept_order_reorders_published_wiki():
    domain_id, chapter_id = _new_chapter()
    base = _base(domain_id, chapter_id)
    _write_published_graph(base, domain_id, chapter_id)

    published = client.get(f"{base}/wiki", params={"source": "published"}).json()
    assert [p["concept_id"] for p in published["pages"]] == ["alpha", "beta", "gamma"]
    assert [p["order"] for p in published["pages"]] == [0, 1, 2]

    reordered = ["gamma", "alpha", "beta"]
    put = client.put(
        f"{base}/concept-order",
        params={"source": "published"},
        json={"order": reordered},
    )
    assert put.status_code == 200
    body = put.json()
    assert [p["concept_id"] for p in body["pages"]] == reordered
    assert [p["order"] for p in body["pages"]] == [0, 1, 2]
    assert body["edges"] == published["edges"]
    depth_before = {p["concept_id"]: p["depth"] for p in published["pages"]}
    depth_after = {p["concept_id"]: p["depth"] for p in body["pages"]}
    assert depth_before == depth_after

    persisted = client.get(f"{base}/wiki", params={"source": "published"}).json()
    assert [p["concept_id"] for p in persisted["pages"]] == reordered


def test_concept_order_rejects_non_permutation():
    domain_id, chapter_id = _new_chapter()
    base = _base(domain_id, chapter_id)
    _write_published_graph(base, domain_id, chapter_id)

    resp = client.put(
        f"{base}/concept-order",
        params={"source": "published"},
        json={"order": ["alpha", "beta"]},
    )
    assert resp.status_code == 400


def test_generate_blocked_without_approval():
    domain_id, chapter_id = _new_chapter()
    base = _base(domain_id, chapter_id)
    client.post(
        f"{base}/sources",
        files=[("files", ("notes.md", io.BytesIO(b"# Notes\n\nSets."), "text/markdown"))],
    )
    started = client.post(f"{base}/compile")
    assert started.status_code == 202
    _poll_compile(base)

    gen = client.post(f"{base}/question-bank/generate")
    assert gen.status_code == 409


def test_generate_blocked_when_stale():
    domain_id, chapter_id = _new_chapter()
    base = _base(domain_id, chapter_id)
    client.post(
        f"{base}/sources",
        files=[("files", ("notes.md", io.BytesIO(b"# Notes\n\nSets."), "text/markdown"))],
    )
    client.post(f"{base}/compile")
    _poll_compile(base)
    client.post(f"{base}/compile/approve")

    client.post(
        f"{base}/sources",
        files=[("files", ("more.md", io.BytesIO(b"# More\n\nRelations."), "text/markdown"))],
    )
    artifact = client.get(f"{base}/artifact").json()
    assert artifact["is_stale"] is True

    gen = client.post(f"{base}/question-bank/generate")
    assert gen.status_code == 409


def test_compile_without_sources_returns_400():
    domain_id, chapter_id = _new_chapter()
    base = _base(domain_id, chapter_id)
    resp = client.post(f"{base}/compile")
    assert resp.status_code == 400


def _poll_generate(base: str, timeout_s: float = 5.0) -> dict:
    deadline = time.time() + timeout_s
    last: dict = {}
    while time.time() < deadline:
        resp = client.get(f"{base}/question-bank/generate/status")
        assert resp.status_code == 200
        last = resp.json()
        if last["status"] in {"completed", "failed"}:
            return last
        time.sleep(0.05)
    raise AssertionError(f"generation did not finish: {last!r}")


def test_end_to_end_setup_then_study():
    domain_id, chapter_id = _new_chapter()
    base = _base(domain_id, chapter_id)

    client.post(
        f"{base}/sources",
        files=[
            ("files", ("notes.md", io.BytesIO(b"# Notes\n\nSets and operations."), "text/markdown"))
        ],
    )
    client.post(f"{base}/compile")
    _poll_compile(base)
    client.post(f"{base}/compile/approve")

    gen = client.post(f"{base}/question-bank/generate")
    assert gen.status_code == 202
    final = _poll_generate(base)
    assert final["status"] == "completed"
    assert (final["questions"] or 0) >= 6

    knowledge_source = f"domain:{domain_id}/{chapter_id}"
    session = client.post("/sessions", json={"knowledge_source": knowledge_source})
    assert session.status_code == 200
    session_id = session.json()["session_id"]

    question = client.post(f"/sessions/{session_id}/question", json={})
    assert question.status_code == 200
    assert question.json()["concept_id"] == "chapter_overview"
