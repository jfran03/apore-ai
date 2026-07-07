"""Full domain-scoped loop with the stub provider, including restart-resume."""

import shutil

import pytest
from fastapi.testclient import TestClient

import apore.api.app as app_module
from apore.api.app import app
from apore.domains import store

client = TestClient(app)


@pytest.fixture()
def domain_session():
    resp = client.post(
        "/domains",
        json={"name": "Testbed", "objective": "o", "teaching_style": "socratic",
              "teaching_prompt": "p", "model_preference": "auto"},
    )
    record = store.load_domain(resp.json()["id"])
    src = app_module.PROGRAM_ROOT / "domains" / "_pytest" / "chapters" / "01-intro"
    shutil.copytree(src, store.chapters_dir(record) / "01-intro")
    created = client.post(f"/domains/{record.domain_id}/sessions", json={}).json()
    return record, created["session_id"]


def _base(record, session_id):
    return f"/domains/{record.domain_id}/sessions/{session_id}"


def test_full_loop_persists_transcript(domain_session):
    record, sid = domain_session
    q = client.post(f"{_base(record, sid)}/question", json={})
    assert q.status_code == 200

    turn = client.post(f"{_base(record, sid)}/turn", json={"learner_message": "my answer"})
    assert turn.status_code == 200
    assert turn.json()["phase"] == "graded"

    detail = client.get(_base(record, sid)).json()
    assert detail["phase"] == "awaiting_rating"
    types = [e["type"] for e in detail["transcript"]]
    assert "question" in types
    assert "learner_message" in types
    assert "graded" in types

    rate = client.post(f"{_base(record, sid)}/turn", json={"explicit_rating": "ok"})
    assert rate.json()["phase"] == "reflection"
    detail = client.get(_base(record, sid)).json()
    assert detail["phase"] == "reflection"
    assert any(e["type"] == "rating" for e in detail["transcript"])

    cont = client.post(f"{_base(record, sid)}/turn", json={"continue": True})
    assert cont.json()["phase"] == "completed"
    detail = client.get(_base(record, sid)).json()
    assert detail["phase"] == "idle"


def test_resume_after_restart_mid_turn(domain_session):
    record, sid = domain_session
    client.post(f"{_base(record, sid)}/question", json={})
    client.post(f"{_base(record, sid)}/turn", json={"learner_message": "answer one"})

    # Simulate a backend restart: in-memory session map wiped.
    app_module.sessions.clear()

    # Detail still knows we're awaiting a rating…
    detail = client.get(_base(record, sid)).json()
    assert detail["phase"] == "awaiting_rating"

    # …and the loop continues from the rating step after rehydration.
    rate = client.post(f"{_base(record, sid)}/turn", json={"explicit_rating": "hard"})
    assert rate.status_code == 200
    assert rate.json()["phase"] == "reflection"
    cont = client.post(f"{_base(record, sid)}/turn", json={"continue": True})
    assert cont.json()["phase"] == "completed"

    # Next question also works post-restart.
    q2 = client.post(f"{_base(record, sid)}/question", json={})
    assert q2.status_code == 200
    assert q2.json()["question_number"] == 2


def test_corrupt_session_file_409(domain_session):
    record, sid = domain_session
    app_module.sessions.clear()
    from apore.domains import sessionfile

    sessionfile.session_json_path(record, sid).write_text("{broken", encoding="utf-8")
    resp = client.post(f"{_base(record, sid)}/question", json={})
    assert resp.status_code == 409
