import shutil

import pytest
from fastapi.testclient import TestClient

import apore.api.app as app_module
from apore.api.app import app
from apore.domains import store

client = TestClient(app)


@pytest.fixture()
def seeded_domain():
    resp = client.post(
        "/domains",
        json={"name": "Testbed", "objective": "o", "teaching_style": "socratic",
              "teaching_prompt": "p", "model_preference": "auto"},
    )
    record = store.load_domain(resp.json()["id"])
    src = app_module.PROGRAM_ROOT / "domains" / "_pytest" / "chapters" / "01-intro"
    dest = store.chapters_dir(record) / "01-intro"
    shutil.copytree(src, dest)
    return record


def test_create_session_defaults_to_first_ready_chapter(seeded_domain):
    resp = client.post(f"/domains/{seeded_domain.domain_id}/sessions", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert data["knowledge_source"] == f"workspace:{seeded_domain.domain_id}/01-intro"
    assert data["title"]
    # Files landed inside the domain
    session_dir = store.sessions_dir(seeded_domain) / data["session_id"]
    assert (session_dir / "session.json").is_file()
    assert (session_dir / "learner-state.md").is_file()


def test_create_session_empty_domain_409():
    resp = client.post(
        "/domains",
        json={"name": "Empty", "objective": "", "teaching_style": "socratic",
              "teaching_prompt": "", "model_preference": "auto"},
    )
    domain_id = resp.json()["id"]
    resp = client.post(f"/domains/{domain_id}/sessions", json={})
    assert resp.status_code == 409


def test_list_and_detail(seeded_domain):
    created = client.post(
        f"/domains/{seeded_domain.domain_id}/sessions", json={"max_questions": 5}
    ).json()
    listing = client.get(f"/domains/{seeded_domain.domain_id}/sessions").json()
    assert [s["session_id"] for s in listing["sessions"]] == [created["session_id"]]
    assert listing["sessions"][0]["status"] == "active"

    detail = client.get(
        f"/domains/{seeded_domain.domain_id}/sessions/{created['session_id']}"
    ).json()
    assert detail["phase"] == "idle"
    assert detail["transcript"] == []
    assert detail["max_questions"] == 5
    assert detail["scalar"] == 0.5


def test_detail_unknown_404(seeded_domain):
    resp = client.get(f"/domains/{seeded_domain.domain_id}/sessions/nope")
    assert resp.status_code == 404
