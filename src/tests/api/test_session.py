"""API integration tests using FastAPI TestClient."""

from fastapi.testclient import TestClient

from apore.api.app import app
from tests.api.conftest import TEST_KNOWLEDGE_SOURCE

client = TestClient(app)


def _start_session_with_question():
    resp = client.post("/sessions", json={"knowledge_source": TEST_KNOWLEDGE_SOURCE})
    assert resp.status_code == 200
    session_id = resp.json()["session_id"]
    q_resp = client.post(f"/sessions/{session_id}/question", json={})
    assert q_resp.status_code == 200
    return session_id, q_resp.json()


def test_create_session():
    resp = client.post("/sessions", json={"knowledge_source": TEST_KNOWLEDGE_SOURCE})
    assert resp.status_code == 200
    data = resp.json()
    assert "session_id" in data
    assert "title" in data
    assert data["title"]
    assert "scalar" in data
    assert "created_at" in data
    assert data["knowledge_source"] == TEST_KNOWLEDGE_SOURCE
    assert data["focus_mode"] == "adaptive"
    assert data["max_questions"] == 10
    assert isinstance(data["scalar"], float)


def test_create_session_with_config():
    resp = client.post(
        "/sessions",
        json={
            "knowledge_source": TEST_KNOWLEDGE_SOURCE,
            "focus_mode": "weak_points",
            "max_questions": 5,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["focus_mode"] == "weak_points"
    assert data["max_questions"] == 5
    assert data["title"]

    state = client.get(f"/sessions/{data['session_id']}/state").json()
    assert state["title"] == data["title"]
    assert state["focus_mode"] == "weak_points"
    assert state["max_questions"] == 5
    assert state["questions_remaining"] == 5


def _rate_question(session_id: str, rating: str = "ok"):
    return client.post(
        f"/sessions/{session_id}/turn",
        json={"explicit_rating": rating},
    )


def _complete_question(session_id: str, rating: str = "ok"):
    client.post(f"/sessions/{session_id}/turn", json={"skip": True})
    client.post(
        f"/sessions/{session_id}/turn",
        json={"skip_reason": "not sure"},
    )
    rate = _rate_question(session_id, rating)
    assert rate.status_code == 200
    assert rate.json()["phase"] == "reflection"
    return client.post(f"/sessions/{session_id}/turn", json={"continue": True})


def test_max_questions_session_complete_and_guard():
    resp = client.post(
        "/sessions",
        json={"knowledge_source": TEST_KNOWLEDGE_SOURCE, "max_questions": 2},
    )
    assert resp.status_code == 200
    session_id = resp.json()["session_id"]

    q1 = client.post(f"/sessions/{session_id}/question", json={})
    assert q1.status_code == 200
    rate1 = _complete_question(session_id)
    assert rate1.status_code == 200
    assert rate1.json()["phase"] == "completed"

    q2 = client.post(f"/sessions/{session_id}/question", json={})
    assert q2.status_code == 200
    rate2 = _complete_question(session_id)
    assert rate2.status_code == 200
    assert rate2.json()["phase"] == "session_complete"

    blocked = client.post(f"/sessions/{session_id}/question", json={})
    assert blocked.status_code == 409


def test_create_session_legacy_fixture_field():
    resp = client.post("/sessions", json={"fixture": "apore-lite", "knowledge_source": "fixture:apore-lite"})
    assert resp.status_code in (200, 400)


def test_wrong_declarative_answer_grades_immediately():
    session_id, _ = _start_session_with_question()
    grade_resp = client.post(
        f"/sessions/{session_id}/turn",
        json={"learner_message": "a set is a list of unordered elements"},
    )
    assert grade_resp.status_code == 200
    grade_data = grade_resp.json()
    assert grade_data["phase"] == "graded"
    assert grade_data["correct"] == "no"
    assert grade_data["tutor_message"].startswith("Not quite")
    assert grade_data["hint_count"] == 0
    assert grade_data["turn_count"] == 1


def test_explicit_help_stays_in_tutor_dialogue():
    session_id, _ = _start_session_with_question()
    dialogue_resp = client.post(
        f"/sessions/{session_id}/turn",
        json={"learner_message": "I need help understanding this question"},
    )
    assert dialogue_resp.status_code == 200
    dialogue_data = dialogue_resp.json()
    assert dialogue_data["phase"] == "dialogue"
    assert dialogue_data["tutor_message"]
    assert dialogue_data["question_closed"] is False


def test_session_question_then_two_phase_turn():
    session_id, q_data = _start_session_with_question()
    assert q_data["question_number"] == 1
    assert "question_text" in q_data
    assert q_data["concept_id"] == "sets_definition"
    assert q_data["concept_label"] == "Definition of a Set"
    assert q_data["concept"] == "Definition of a Set"

    dialogue_resp = client.post(
        f"/sessions/{session_id}/turn",
        json={"learner_message": "not sure about this, can you explain disjoint?"},
    )
    assert dialogue_resp.status_code == 200
    dialogue_data = dialogue_resp.json()
    assert dialogue_data["phase"] == "dialogue"
    assert dialogue_data["tutor_message"]
    assert dialogue_data["question_closed"] is False

    grade_resp = client.post(
        f"/sessions/{session_id}/turn",
        json={"learner_message": "the intersection is empty, so they are disjoint"},
    )
    assert grade_resp.status_code == 200
    grade_data = grade_resp.json()
    assert grade_data["phase"] == "graded"
    assert grade_data["question_number"] == 1
    assert grade_data["correct"] in ("yes", "no")
    assert grade_data["hint_count"] >= 1
    assert grade_data["turn_count"] >= 2
    assert grade_data.get("reward") is None
    assert grade_data.get("new_difficulty") is None

    rate_resp = _rate_question(session_id, "ok")
    assert rate_resp.status_code == 200
    data = rate_resp.json()
    assert data["phase"] == "reflection"
    cont_resp = client.post(f"/sessions/{session_id}/turn", json={"continue": True})
    assert cont_resp.status_code == 200
    data = cont_resp.json()
    assert data["phase"] == "completed"
    assert data["question_number"] == 1
    assert data["explicit_rating"] == "ok"
    assert data["correct"] in ("yes", "no")
    assert "hint_count" in data
    assert "turn_count" in data
    assert "reward" in data
    assert "new_difficulty" in data
    assert "inconsistency_flag" in data


def test_skip_flow():
    session_id, _ = _start_session_with_question()

    skip_resp = client.post(f"/sessions/{session_id}/turn", json={"skip": True})
    assert skip_resp.status_code == 200
    skip_data = skip_resp.json()
    assert skip_data["phase"] == "skip_prompt"
    assert skip_data["tutor_message"]

    grade_resp = client.post(
        f"/sessions/{session_id}/turn",
        json={"skip_reason": "I have not seen this notation before."},
    )
    assert grade_resp.status_code == 200
    assert grade_resp.json()["phase"] == "graded"

    rate_resp = _rate_question(session_id, "hard")
    assert rate_resp.status_code == 200
    assert rate_resp.json()["phase"] == "reflection"
    cont_resp = client.post(f"/sessions/{session_id}/turn", json={"continue": True})
    assert cont_resp.status_code == 200
    assert cont_resp.json()["phase"] == "completed"


def test_pending_question_409():
    session_id, _ = _start_session_with_question()
    conflict = client.post(f"/sessions/{session_id}/question", json={})
    assert conflict.status_code == 409


def test_turn_grade_without_pending_409():
    resp = client.post("/sessions", json={"knowledge_source": TEST_KNOWLEDGE_SOURCE})
    session_id = resp.json()["session_id"]
    turn_resp = client.post(
        f"/sessions/{session_id}/turn",
        json={"learner_message": "answer"},
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


def test_turn_multiple_fields_400():
    session_id, _ = _start_session_with_question()
    bad = client.post(
        f"/sessions/{session_id}/turn",
        json={"learner_message": "answer", "explicit_rating": "ok"},
    )
    assert bad.status_code == 400


def test_question_blocked_while_pending_grading():
    session_id, _ = _start_session_with_question()
    client.post(
        f"/sessions/{session_id}/turn",
        json={"learner_message": "what does disjoint mean?"},
    )
    client.post(
        f"/sessions/{session_id}/turn",
        json={"learner_message": "they share no elements"},
    )
    q_conflict = client.post(f"/sessions/{session_id}/question", json={})
    assert q_conflict.status_code == 409


def test_get_session_state():
    session_id, _ = _start_session_with_question()
    client.post(
        f"/sessions/{session_id}/turn",
        json={"learner_message": "a collection of distinct elements with no order"},
    )
    _rate_question(session_id, "hard")
    client.post(f"/sessions/{session_id}/turn", json={"continue": True})

    resp = client.get(f"/sessions/{session_id}/state")
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == session_id
    assert "scalar" in data
    assert data["question_count"] == 1
    assert isinstance(data["mastery"], dict)
    assert data["knowledge_source"] == TEST_KNOWLEDGE_SOURCE
    assert "title" in data
    assert data["max_questions"] == 10
    assert data["focus_mode"] == "adaptive"
    assert data["questions_remaining"] == 9


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


def test_wrong_answer_rating_enters_reflection():
    session_id, _ = _start_session_with_question()
    grade_resp = client.post(
        f"/sessions/{session_id}/turn",
        json={"learner_message": "a set is a list of unordered elements"},
    )
    assert grade_resp.json()["phase"] == "graded"
    rate_resp = _rate_question(session_id, "hard")
    assert rate_resp.status_code == 200
    assert rate_resp.json()["phase"] == "reflection"
    assert rate_resp.json()["correct"] == "no"


def test_reflection_chat_then_continue():
    session_id, _ = _start_session_with_question()
    client.post(
        f"/sessions/{session_id}/turn",
        json={"learner_message": "a set is a list of unordered elements"},
    )
    _rate_question(session_id, "ok")
    chat_resp = client.post(
        f"/sessions/{session_id}/turn",
        json={"learner_message": "why is order not part of the definition?"},
    )
    assert chat_resp.status_code == 200
    assert chat_resp.json()["phase"] == "reflection"
    assert chat_resp.json()["tutor_message"]

    blocked = client.post(f"/sessions/{session_id}/question", json={})
    assert blocked.status_code == 409

    cont_resp = client.post(f"/sessions/{session_id}/turn", json={"continue": True})
    assert cont_resp.status_code == 200
    assert cont_resp.json()["phase"] == "completed"

    q2 = client.post(f"/sessions/{session_id}/question", json={})
    assert q2.status_code == 200


def test_continue_without_reflection_409():
    session_id, _ = _start_session_with_question()
    cont = client.post(f"/sessions/{session_id}/turn", json={"continue": True})
    assert cont.status_code == 409


def test_turn_continue_and_message_exclusive_400():
    session_id, _ = _start_session_with_question()
    bad = client.post(
        f"/sessions/{session_id}/turn",
        json={"learner_message": "help", "continue": True},
    )
    assert bad.status_code == 400


def test_unknown_session_returns_404():
    resp = client.get("/sessions/nonexistent-session-id/state")
    assert resp.status_code == 404
