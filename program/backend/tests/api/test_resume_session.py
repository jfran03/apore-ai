"""Tests for POST /sessions/{id}/resume and disk-backed dialogue persistence."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

import apore.api.app as app_module
from apore.api.app import app
from apore.runtime import state
from tests.api.conftest import TEST_KNOWLEDGE_SOURCE

client = TestClient(app)


@pytest.fixture()
def sessions_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "SESSIONS_DIR", tmp_path)
    return tmp_path


def test_resume_hydrates_mid_dialogue_after_memory_clear(sessions_dir):
    create = client.post("/sessions", json={"knowledge_source": TEST_KNOWLEDGE_SOURCE})
    assert create.status_code == 200
    session_id = create.json()["session_id"]

    q = client.post(f"/sessions/{session_id}/question", json={})
    assert q.status_code == 200
    question = q.json()

    help_turn = client.post(
        f"/sessions/{session_id}/turn",
        json={"learner_message": "I need help understanding this question"},
    )
    assert help_turn.status_code == 200
    assert help_turn.json()["phase"] == "dialogue"

    path = sessions_dir / f"{session_id}.md"
    runtime = state.read_runtime(path)
    assert runtime is not None
    assert runtime["pending_question"]["question_id"] == question["question_id"]
    assert any(m.get("role") == "user" for m in runtime["active_transcript"])
    items = state.read_conversation_items(path)
    assert len(items) == 1
    assert items[0]["status"] == "in_progress"
    assert items[0]["question_id"] == question["question_id"]
    assert any(m.get("role") == "user" for m in items[0]["messages"])

    # Simulate process restart: drop in-memory sessions only.
    app_module.sessions.clear()
    assert session_id not in app_module.sessions

    resume = client.post(f"/sessions/{session_id}/resume")
    assert resume.status_code == 200
    data = resume.json()
    assert data["session_id"] == session_id
    assert data["status"] == "active"
    assert data["phase"] == "dialogue"
    assert data["pending_question"]["question_id"] == question["question_id"]
    assert data["pending_question"]["question_text"] == question["question_text"]
    assert any(m["role"] == "user" for m in data["dialogue_messages"])
    assert data["tutor_mode"] is True

    # Live endpoints work again after hydrate.
    follow = client.post(
        f"/sessions/{session_id}/turn",
        json={"learner_message": "still stuck"},
    )
    assert follow.status_code == 200


def test_resume_idempotent_when_already_live(sessions_dir):
    create = client.post("/sessions", json={"knowledge_source": TEST_KNOWLEDGE_SOURCE})
    session_id = create.json()["session_id"]
    client.post(f"/sessions/{session_id}/question", json={})

    first = client.post(f"/sessions/{session_id}/resume")
    second = client.post(f"/sessions/{session_id}/resume")
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["session_id"] == second.json()["session_id"]
    assert first.json()["phase"] == "dialogue"


def test_resume_reactivates_ended_early_session(sessions_dir):
    create = client.post(
        "/sessions",
        json={"knowledge_source": TEST_KNOWLEDGE_SOURCE, "max_questions": 5},
    )
    session_id = create.json()["session_id"]
    client.post(f"/sessions/{session_id}/question", json={})
    end = client.post(f"/sessions/{session_id}/end")
    assert end.status_code == 200
    assert end.json()["status"] == "ended_early"

    path = sessions_dir / f"{session_id}.md"
    meta = state.read_session_meta(path)
    assert meta["status"] == "ended_early"

    app_module.sessions.clear()
    resume = client.post(f"/sessions/{session_id}/resume")
    assert resume.status_code == 200
    data = resume.json()
    assert data["status"] == "active"
    assert data["phase"] == "idle"
    assert data["pending_question"] is None

    meta_after = state.read_session_meta(path)
    assert meta_after["status"] == "active"
    assert meta_after.get("ended_at", "") == ""

    nxt = client.post(f"/sessions/{session_id}/question", json={})
    assert nxt.status_code == 200
    assert nxt.json()["question_number"] == 1


def test_resume_rejects_completed_session(sessions_dir):
    create = client.post(
        "/sessions",
        json={"knowledge_source": TEST_KNOWLEDGE_SOURCE, "max_questions": 1},
    )
    session_id = create.json()["session_id"]
    assert client.post(f"/sessions/{session_id}/question", json={}).status_code == 200
    client.post(f"/sessions/{session_id}/turn", json={"skip": True})
    client.post(f"/sessions/{session_id}/turn", json={"skip_reason": "not sure"})
    rate = client.post(f"/sessions/{session_id}/turn", json={"explicit_rating": "ok"})
    assert rate.status_code == 200
    assert rate.json()["phase"] == "reflection"
    cont = client.post(f"/sessions/{session_id}/turn", json={"continue": True})
    assert cont.status_code == 200
    assert cont.json()["phase"] == "session_complete"

    # Still in memory as completed.
    assert client.post(f"/sessions/{session_id}/resume").status_code == 409

    app_module.sessions.clear()
    assert client.post(f"/sessions/{session_id}/resume").status_code == 409


def test_resume_unknown_and_invalid_ids(sessions_dir):
    assert client.post(f"/sessions/{uuid.uuid4()}/resume").status_code == 404
    assert client.post("/sessions/not-a-uuid/resume").status_code == 404


def test_transcript_questions_mid_dialogue_and_completed(sessions_dir):
    create = client.post(
        "/sessions",
        json={"knowledge_source": TEST_KNOWLEDGE_SOURCE, "max_questions": 3},
    )
    session_id = create.json()["session_id"]
    q = client.post(f"/sessions/{session_id}/question", json={}).json()
    client.post(
        f"/sessions/{session_id}/turn",
        json={"learner_message": "I need help understanding this question"},
    )

    mid = client.get(f"/sessions/{session_id}/transcript").json()
    assert len(mid["questions"]) == 1
    assert mid["questions"][0]["status"] == "in_progress"
    assert mid["questions"][0]["question_id"] == q["question_id"]
    assert mid["questions"][0]["question_text"] == q["question_text"]
    assert any(m["role"] == "user" for m in mid["questions"][0]["messages"])

    client.post(f"/sessions/{session_id}/turn", json={"skip": True})
    client.post(f"/sessions/{session_id}/turn", json={"skip_reason": "skip"})
    rate = client.post(f"/sessions/{session_id}/turn", json={"explicit_rating": "ok"})
    assert rate.json()["phase"] == "reflection"
    cont = client.post(f"/sessions/{session_id}/turn", json={"continue": True})
    assert cont.json()["phase"] == "completed"

    done = client.get(f"/sessions/{session_id}/transcript").json()
    assert len(done["questions"]) == 1
    assert done["questions"][0]["status"] == "completed"
    assert done["questions"][0]["correct"] in ("yes", "no")
    assert done["questions"][0]["explicit_rating"] == "ok"


def test_resume_between_questions(sessions_dir):
    create = client.post(
        "/sessions",
        json={"knowledge_source": TEST_KNOWLEDGE_SOURCE, "max_questions": 3},
    )
    session_id = create.json()["session_id"]
    q = client.post(f"/sessions/{session_id}/question", json={})
    assert q.status_code == 200
    question_text = q.json()["question_text"]
    client.post(f"/sessions/{session_id}/turn", json={"skip": True})
    client.post(f"/sessions/{session_id}/turn", json={"skip_reason": "skip"})
    rate = client.post(f"/sessions/{session_id}/turn", json={"explicit_rating": "ok"})
    assert rate.json()["phase"] == "reflection"
    cont = client.post(f"/sessions/{session_id}/turn", json={"continue": True})
    assert cont.json()["phase"] == "completed"

    app_module.sessions.clear()
    resume = client.post(f"/sessions/{session_id}/resume")
    assert resume.status_code == 200
    data = resume.json()
    assert data["phase"] == "idle"
    assert data["pending_question"] is None
    assert data["question_count"] == 1
    assert len(data["history"]) == 1
    assert data["history"][0]["question_number"] == 1
    assert data["history"][0]["question_text"] == question_text
    assert data["history"][0]["explicit_rating"] == "ok"
    assert data["history"][0]["correct"] in ("yes", "no")
    assert data["history"][0]["reward"] is not None

    nxt = client.post(f"/sessions/{session_id}/question", json={})
    assert nxt.status_code == 200
    assert nxt.json()["question_number"] == 2
