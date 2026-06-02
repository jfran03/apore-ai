"""API integration tests using FastAPI TestClient."""

from fastapi.testclient import TestClient

from apore.api.app import app
from tests.api.conftest import TEST_KNOWLEDGE_SOURCE

client = TestClient(app)


def test_create_session():
    resp = client.post("/sessions", json={"knowledge_source": TEST_KNOWLEDGE_SOURCE})
    assert resp.status_code == 200
    data = resp.json()
    assert "session_id" in data
    assert "scalar" in data
    assert "created_at" in data
    assert data["knowledge_source"] == TEST_KNOWLEDGE_SOURCE
    assert isinstance(data["scalar"], float)


def test_create_session_legacy_fixture_field():
    resp = client.post("/sessions", json={"fixture": "apore-lite", "knowledge_source": "fixture:apore-lite"})
    assert resp.status_code in (200, 400)


def test_session_question_then_two_phase_turn():
    resp = client.post("/sessions", json={"knowledge_source": TEST_KNOWLEDGE_SOURCE})
    assert resp.status_code == 200
    session_id = resp.json()["session_id"]

    q_resp = client.post(f"/sessions/{session_id}/question", json={})
    assert q_resp.status_code == 200
    q_data = q_resp.json()
    assert q_data["question_number"] == 1
    assert "question_text" in q_data
    assert q_data["concept_id"] == "sets_definition"
    assert q_data["concept_label"] == "Definition of a Set"
    assert q_data["concept"] == "Definition of a Set"

    grade_resp = client.post(
        f"/sessions/{session_id}/turn",
        json={
            "learner_response": "A set has unique elements.",
            "concept_id": "sets_definition",
        },
    )
    assert grade_resp.status_code == 200
    grade_data = grade_resp.json()
    assert grade_data["phase"] == "graded"
    assert grade_data["question_number"] == 1
    assert grade_data["correct"] in ("yes", "no")
    assert "hint_count" in grade_data
    assert "turn_count" in grade_data
    assert grade_data.get("reward") is None
    assert grade_data.get("new_difficulty") is None

    rate_resp = client.post(
        f"/sessions/{session_id}/turn",
        json={"explicit_rating": "ok"},
    )
    assert rate_resp.status_code == 200
    data = rate_resp.json()
    assert data["phase"] == "completed"
    assert data["question_number"] == 1
    assert data["explicit_rating"] == "ok"
    assert data["correct"] in ("yes", "no")
    assert "hint_count" in data
    assert "turn_count" in data
    assert "reward" in data
    assert "new_difficulty" in data
    assert "inconsistency_flag" in data


def test_pending_question_409():
    resp = client.post("/sessions", json={"knowledge_source": TEST_KNOWLEDGE_SOURCE})
    session_id = resp.json()["session_id"]
    assert client.post(f"/sessions/{session_id}/question", json={}).status_code == 200
    conflict = client.post(f"/sessions/{session_id}/question", json={})
    assert conflict.status_code == 409


def test_turn_grade_without_pending_409():
    resp = client.post("/sessions", json={"knowledge_source": TEST_KNOWLEDGE_SOURCE})
    session_id = resp.json()["session_id"]
    turn_resp = client.post(
        f"/sessions/{session_id}/turn",
        json={"learner_response": "answer", "concept_id": "sets_definition"},
    )
    assert turn_resp.status_code == 409


def test_turn_rate_without_pending_grading_409():
    resp = client.post("/sessions", json={"knowledge_source": TEST_KNOWLEDGE_SOURCE})
    session_id = resp.json()["session_id"]
    rate_resp = client.post(
        f"/sessions/{session_id}/turn",
        json={"explicit_rating": "easy"},
    )
    assert rate_resp.status_code == 409


def test_turn_both_fields_400():
    resp = client.post("/sessions", json={"knowledge_source": TEST_KNOWLEDGE_SOURCE})
    session_id = resp.json()["session_id"]
    client.post(f"/sessions/{session_id}/question", json={})
    bad = client.post(
        f"/sessions/{session_id}/turn",
        json={"learner_response": "answer", "explicit_rating": "ok"},
    )
    assert bad.status_code == 400


def test_question_blocked_while_pending_grading():
    resp = client.post("/sessions", json={"knowledge_source": TEST_KNOWLEDGE_SOURCE})
    session_id = resp.json()["session_id"]
    client.post(f"/sessions/{session_id}/question", json={})
    client.post(
        f"/sessions/{session_id}/turn",
        json={"learner_response": "A set has unique elements."},
    )
    q_conflict = client.post(f"/sessions/{session_id}/question", json={})
    assert q_conflict.status_code == 409


def test_get_session_state():
    resp = client.post("/sessions", json={"knowledge_source": TEST_KNOWLEDGE_SOURCE})
    session_id = resp.json()["session_id"]
    client.post(f"/sessions/{session_id}/question", json={})
    client.post(
        f"/sessions/{session_id}/turn",
        json={"learner_response": "my answer", "concept_id": "sets_definition"},
    )
    client.post(f"/sessions/{session_id}/turn", json={"explicit_rating": "hard"})

    resp = client.get(f"/sessions/{session_id}/state")
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == session_id
    assert "scalar" in data
    assert data["question_count"] == 1
    assert isinstance(data["mastery"], dict)
    assert data["knowledge_source"] == TEST_KNOWLEDGE_SOURCE


def test_config_get():
    resp = client.get("/config/provider")
    assert resp.status_code == 200
    data = resp.json()
    assert "anthropic_api_key_set" in data
    assert "nim_api_key_set" in data
    assert "model" in data
    assert "active_provider" in data


def test_config_put():
    resp = client.put(
        "/config/provider",
        json={"anthropic_api_key": "sk-ant-example", "model": "claude-sonnet-4-5"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["anthropic_api_key_set"] is True
    assert data["active_provider"] == "anthropic"
    assert data["model"] == "claude-sonnet-4-5"


def test_batch_run_queued():
    resp = client.post(
        "/runs/batch",
        json={"sessions": 3, "profile": {"ability": 0.6, "misconceptions": [], "seed": 42}},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "run_id" in data
    assert data["status"] == "completed"


def test_unknown_session_returns_404():
    resp = client.get("/sessions/nonexistent-session-id/state")
    assert resp.status_code == 404
