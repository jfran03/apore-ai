import json

import pytest
from fastapi.testclient import TestClient

from apore.api.app import app
from apore.domains import store

client = TestClient(app)


@pytest.fixture(autouse=True)
def data_root(tmp_path, monkeypatch):
    monkeypatch.setenv("APORE_DATA_DIR", str(tmp_path))
    return tmp_path


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
