import json
import shutil

import pytest
from fastapi.testclient import TestClient

import apore.api.app as app_module
import apore.api.domain_routes as domain_routes
from apore.api.app import app
from apore.domains import store

client = TestClient(app)


CREATE_BODY = {
    "name": "Discrete Math",
    "objective": "Proof-based CS foundations",
    "teaching_style": "socratic",
    "teaching_prompt": "Ask before answering.",
    "model_preference": "auto",
}


def test_create_domain_and_list():
    resp = client.post("/domains", json=CREATE_BODY)
    assert resp.status_code == 201
    created = resp.json()
    assert created["name"] == "Discrete Math"
    assert created["status"] == "empty"
    assert created["chapters"] == []

    listing = client.get("/domains")
    assert listing.status_code == 200
    ids = [d["id"] for d in listing.json()["domains"]]
    assert created["id"] in ids


def test_create_domain_requires_name():
    resp = client.post("/domains", json={**CREATE_BODY, "name": ""})
    assert resp.status_code == 422


def test_get_domain_detail_and_404():
    created = client.post("/domains", json=CREATE_BODY).json()
    detail = client.get(f"/domains/{created['id']}")
    assert detail.status_code == 200
    assert detail.json()["teaching_prompt"] == "Ask before answering."
    assert client.get("/domains/nope-0000").status_code == 404


def test_ready_status_when_chapter_has_graph():
    created = client.post("/domains", json=CREATE_BODY).json()
    record = store.load_domain(created["id"])
    chapter = store.chapters_dir(record) / "01-intro"
    (chapter / "wiki").mkdir(parents=True)
    (chapter / "wiki" / "sets.md").write_text("# Sets", encoding="utf-8")
    (chapter / "concept-graph.json").write_text(
        json.dumps({"nodes": [{"id": "sets"}], "edges": []}), encoding="utf-8"
    )
    detail = client.get(f"/domains/{created['id']}").json()
    assert detail["status"] == "ready"
    assert detail["chapters"] == [
        {"id": "01-intro", "has_concept_graph": True, "wiki_count": 1,
         "has_question_bank": False}
    ]


def test_invalid_folder_listed_with_reason(data_root):
    bad = data_root / "pasted-junk"
    bad.mkdir()
    listing = client.get("/domains").json()["domains"]
    entry = next(d for d in listing if d["id"] == "pasted-junk")
    assert entry["status"] == "invalid"
    assert entry["reason"]


def test_health_reports_testbed(monkeypatch):
    monkeypatch.delenv("APORE_TESTBED", raising=False)
    assert client.get("/health").json()["testbed"] is False
    monkeypatch.setenv("APORE_TESTBED", "1")
    assert client.get("/health").json()["testbed"] is True


def test_domain_session_title_uses_testbed_stub_provider(monkeypatch):
    from apore.providers.stub import StubProvider

    monkeypatch.setenv("APORE_TESTBED", "1")
    monkeypatch.setenv("APORE_TESTBED_PROVIDER", "stub")
    seen: dict[str, str] = {}

    def fail_if_direct_provider_lookup(provider_name: str):
        raise AssertionError(f"direct provider lookup bypassed app helper: {provider_name}")

    def app_provider_lookup(provider_name: str):
        seen["provider_name"] = provider_name
        return StubProvider()

    monkeypatch.setattr(domain_routes, "get_provider", fail_if_direct_provider_lookup, raising=False)
    monkeypatch.setattr(app_module, "get_provider", app_provider_lookup)

    created = client.post("/domains", json=CREATE_BODY).json()
    record = store.load_domain(created["id"])
    src = app_module.PROGRAM_ROOT / "domains" / "_pytest" / "chapters" / "01-intro"
    shutil.copytree(src, store.chapters_dir(record) / "01-intro")

    resp = client.post(f"/domains/{record.domain_id}/sessions", json={})

    assert resp.status_code == 200
    assert resp.json()["title"]
    assert seen["provider_name"] == "stub"
