"""API integration tests using FastAPI TestClient."""

from fastapi.testclient import TestClient

from apore.api.app import app

client = TestClient(app)


def test_create_session():
    resp = client.post("/sessions", json={"provider": "stub", "model": "stub", "fixture": "apore-lite"})
    assert resp.status_code == 200
    data = resp.json()
    assert "session_id" in data
    assert "scalar" in data
    assert "created_at" in data
    assert isinstance(data["scalar"], float)


def test_session_turn():
    # Create a session first
    resp = client.post("/sessions", json={"provider": "stub", "model": "stub", "fixture": "apore-lite"})
    assert resp.status_code == 200
    session_id = resp.json()["session_id"]

    # Post a turn
    resp = client.post(
        f"/sessions/{session_id}/turn",
        json={"learner_response": "A set has unique elements.", "concept_id": "set_theory_intro"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["question_number"] == 1
    assert "question_text" in data
    assert "explicit_rating" in data
    assert "correct" in data
    assert "hint_count" in data
    assert "turn_count" in data
    assert "reward" in data
    assert "new_difficulty" in data
    assert "inconsistency_flag" in data


def test_get_session_state():
    # Create session and do a turn
    resp = client.post("/sessions", json={"provider": "stub", "model": "stub", "fixture": "apore-lite"})
    session_id = resp.json()["session_id"]
    client.post(
        f"/sessions/{session_id}/turn",
        json={"learner_response": "my answer", "concept_id": "set_theory_intro"},
    )

    # Check state
    resp = client.get(f"/sessions/{session_id}/state")
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == session_id
    assert "scalar" in data
    assert data["question_count"] == 1
    assert isinstance(data["mastery"], dict)


def test_config_get():
    resp = client.get("/config/provider")
    assert resp.status_code == 200
    data = resp.json()
    assert "provider" in data
    assert "model" in data


def test_config_put():
    resp = client.put("/config/provider", json={"provider": "anthropic", "model": "claude-haiku-4-5-20251001"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["provider"] == "anthropic"
    assert data["model"] == "claude-haiku-4-5-20251001"

    # Restore to stub so other tests aren't affected
    client.put("/config/provider", json={"provider": "stub", "model": "stub"})


def test_batch_run_queued():
    resp = client.post(
        "/runs/batch",
        json={"sessions": 3, "profile": {"ability": 0.6, "misconceptions": [], "seed": 42}},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "run_id" in data
    assert data["status"] == "queued"


def test_unknown_session_returns_404():
    resp = client.get("/sessions/nonexistent-session-id/state")
    assert resp.status_code == 404
