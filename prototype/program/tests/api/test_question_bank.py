"""Question bank setup API tests."""

import pytest
from fastapi.testclient import TestClient

from apore.api.app import app
from tests.api.conftest import TEST_KNOWLEDGE_SOURCE

client = TestClient(app)

DOMAIN = "_pytest"
CHAPTER = "01-intro"


def test_get_domain_question_bank():
    resp = client.get(f"/setup/domains/{DOMAIN}/chapters/{CHAPTER}/question-bank")
    assert resp.status_code == 200
    data = resp.json()
    assert data["version"] == 1
    assert len(data["questions"]) >= 6
    first = data["questions"][0]
    assert "id" in first
    assert "depth" in first
    assert "concept_id" in first


def test_crud_roundtrip():
    get_resp = client.get(f"/setup/domains/{DOMAIN}/chapters/{CHAPTER}/question-bank")
    assert get_resp.status_code == 200
    original = get_resp.json()

    new_id = "test-crud-recall-99"
    add_resp = client.post(
        f"/setup/domains/{DOMAIN}/chapters/{CHAPTER}/question-bank/questions",
        json={
            "id": new_id,
            "concept_id": "sets_definition",
            "type": "recall",
            "intended_difficulty": 0.2,
            "text": "CRUD test question?",
        },
    )
    assert add_resp.status_code == 200
    assert any(q["id"] == new_id for q in add_resp.json()["questions"])

    patch_resp = client.patch(
        f"/setup/domains/{DOMAIN}/chapters/{CHAPTER}/question-bank/questions/{new_id}",
        json={
            "id": new_id,
            "concept_id": "sets_definition",
            "type": "recall",
            "intended_difficulty": 0.22,
            "text": "CRUD test question updated?",
        },
    )
    assert patch_resp.status_code == 200
    updated = next(q for q in patch_resp.json()["questions"] if q["id"] == new_id)
    assert updated["intended_difficulty"] == pytest.approx(0.22)

    del_resp = client.delete(
        f"/setup/domains/{DOMAIN}/chapters/{CHAPTER}/question-bank/questions/{new_id}"
    )
    assert del_resp.status_code == 200
    assert not any(q["id"] == new_id for q in del_resp.json()["questions"])

    # Restore original bank so other tests are unaffected
    client.put(
        f"/setup/domains/{DOMAIN}/chapters/{CHAPTER}/question-bank",
        json={"version": original["version"], "questions": original["questions"]},
    )


def test_session_questions_have_distinct_ids():
    resp = client.post("/sessions", json={"knowledge_source": TEST_KNOWLEDGE_SOURCE})
    assert resp.status_code == 200
    session_id = resp.json()["session_id"]

    q1 = client.post(f"/sessions/{session_id}/question", json={})
    assert q1.status_code == 200
    id1 = q1.json()["question_id"]
    assert id1
    assert not id1.startswith("ephemeral:")

    client.post(
        f"/sessions/{session_id}/turn",
        json={"learner_message": "A set is a collection of distinct elements."},
    )
    client.post(
        f"/sessions/{session_id}/turn",
        json={"learner_message": "They are disjoint when intersection is empty."},
    )
    rate = client.post(f"/sessions/{session_id}/turn", json={"explicit_rating": "ok"})
    assert rate.status_code == 200
    assert rate.json()["phase"] == "reflection"
    cont = client.post(f"/sessions/{session_id}/turn", json={"continue": True})
    assert cont.status_code == 200

    q2 = client.post(f"/sessions/{session_id}/question", json={})
    assert q2.status_code == 200
    id2 = q2.json()["question_id"]
    assert id2 != id1
