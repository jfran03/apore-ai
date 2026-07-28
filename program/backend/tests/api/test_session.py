"""API integration tests using FastAPI TestClient."""

from pathlib import Path

from fastapi.testclient import TestClient

from apore.api.app import app
from apore.runtime import state
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
    assert data["concept_ids"] == ["sets_definition", "set_theory_intro"]
    assert "—" in data["title"] or "Adaptive" in data["title"]


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
    assert "Weak Areas Review" in data["title"] or data["title_pending"] is True

    state = client.get(f"/sessions/{data['session_id']}/state").json()
    # Title may already have been swapped by the background LLM job.
    assert state["title"]
    if not state["title_pending"]:
        assert state["title"]
    else:
        assert state["title"] == data["title"]
    assert state["focus_mode"] == "weak_points"
    assert state["max_questions"] == 5
    assert state["questions_remaining"] == 5
    assert state["concept_ids"]


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

    state = client.get(f"/sessions/{session_id}/state").json()
    assert state["status"] == "completed"
    assert state["ended_at"]


def test_end_session_early_mid_question():
    session_id, _ = _start_session_with_question()

    # Unfinished dialogue — should not become a question-log row.
    client.post(
        f"/sessions/{session_id}/turn",
        json={"learner_message": "I need help understanding this question"},
    )

    end = client.post(f"/sessions/{session_id}/end")
    assert end.status_code == 200
    data = end.json()
    assert data["status"] == "ended_early"
    assert data["ended_at"]
    assert data["question_count"] == 0

    # Idempotent
    end2 = client.post(f"/sessions/{session_id}/end")
    assert end2.status_code == 200
    assert end2.json()["ended_at"] == data["ended_at"]

    blocked_q = client.post(f"/sessions/{session_id}/question", json={})
    assert blocked_q.status_code == 409
    blocked_turn = client.post(
        f"/sessions/{session_id}/turn",
        json={"learner_message": "still going"},
    )
    assert blocked_turn.status_code == 409

    transcript = client.get(f"/sessions/{session_id}/transcript").json()
    assert transcript["status"] == "ended_early"
    assert transcript["ended_at"] == data["ended_at"]
    # No completed question log rows for the abandoned question.
    body_lines = [
        ln for ln in transcript["body"].splitlines() if ln.startswith("| ") and "Q#" not in ln and "---" not in ln
    ]
    assert body_lines == []


def test_end_session_keeps_completed_questions():
    resp = client.post(
        "/sessions",
        json={"knowledge_source": TEST_KNOWLEDGE_SOURCE, "max_questions": 5},
    )
    session_id = resp.json()["session_id"]
    assert client.post(f"/sessions/{session_id}/question", json={}).status_code == 200
    assert _complete_question(session_id).status_code == 200

    assert client.post(f"/sessions/{session_id}/question", json={}).status_code == 200
    end = client.post(f"/sessions/{session_id}/end")
    assert end.status_code == 200
    assert end.json()["question_count"] == 1

    transcript = client.get(f"/sessions/{session_id}/transcript").json()
    assert transcript["status"] == "ended_early"
    assert "| 1 |" in transcript["body"]
    # Only one completed log row.
    data_rows = [
        ln
        for ln in transcript["body"].splitlines()
        if ln.startswith("| ") and "| Q#" not in ln and "|---" not in ln and "---|" not in ln
    ]
    assert len(data_rows) == 1


def test_end_unknown_session_404():
    resp = client.post("/sessions/00000000-0000-0000-0000-000000000000/end")
    assert resp.status_code == 404


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
    assert grade_data["mode"] == "answer"
    assert grade_data["assisted"] is False
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
    assert dialogue_data["mode"] == "tutor"
    assert dialogue_data["tutor_message"].startswith("Tutor mode — let's work through this together.")
    assert dialogue_data["question_closed"] is False


def test_i_dont_know_routes_to_tutor_without_grading():
    session_id, _ = _start_session_with_question()
    dialogue_resp = client.post(
        f"/sessions/{session_id}/turn",
        json={"learner_message": "I don't know"},
    )
    assert dialogue_resp.status_code == 200
    dialogue_data = dialogue_resp.json()
    assert dialogue_data["phase"] == "dialogue"
    assert dialogue_data["mode"] == "tutor"
    assert "Tutor mode" in dialogue_data["tutor_message"]
    assert dialogue_data["question_closed"] is False

    rows = state.parse_question_log(
        Path(__file__).resolve().parents[2] / "sessions" / f"{session_id}.md"
    )
    assert rows == []


def test_grade_answer_help_escape_hatches_to_tutor():
    """Messages the regex misses still escape grade-answer into tutor mode."""
    session_id, _ = _start_session_with_question()
    dialogue_resp = client.post(
        f"/sessions/{session_id}/turn",
        json={"learner_message": "clarification please on the empty set"},
    )
    assert dialogue_resp.status_code == 200
    dialogue_data = dialogue_resp.json()
    assert dialogue_data["phase"] == "dialogue"
    assert dialogue_data["mode"] == "tutor"
    assert dialogue_data["tutor_message"].startswith(
        "Tutor mode — let's work through this together."
    )
    assert dialogue_data["question_closed"] is False


def test_assisted_correct_logs_assisted_yes():
    session_id, _ = _start_session_with_question()
    help_resp = client.post(
        f"/sessions/{session_id}/turn",
        json={"learner_message": "I need help understanding this question"},
    )
    assert help_resp.status_code == 200
    assert help_resp.json()["phase"] == "dialogue"

    grade_resp = client.post(
        f"/sessions/{session_id}/turn",
        json={"learner_message": "the intersection is empty, so they are disjoint"},
    )
    assert grade_resp.status_code == 200
    grade_data = grade_resp.json()
    assert grade_data["phase"] == "graded"
    assert grade_data["assisted"] is True
    assert grade_data["mode"] == "tutor"

    rate_resp = _rate_question(session_id, "ok")
    assert rate_resp.status_code == 200
    assert rate_resp.json()["assisted"] is True

    rows = state.parse_question_log(
        Path(__file__).resolve().parents[2] / "sessions" / f"{session_id}.md"
    )
    assert len(rows) == 1
    assert rows[0]["assisted"] == "yes"

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
    assert isinstance(data["mastery_delta"], dict)
    assert data["mastery_delta"]  # one graded question → at least one concept
    for entry in data["mastery_delta"].values():
        assert entry["band_before"] in ("new", "struggling", "learning", "proficient")
        assert entry["band_after"] in ("struggling", "learning", "proficient", "new")
        assert entry["n_observed_session"] >= 1
        if entry["band_before"] == "new":
            assert entry["pct_before"] is None
        else:
            assert entry["pct_before"] is not None
        assert entry["pct_after"] is not None or entry["band_after"] == "new"
    assert data["knowledge_source"] == TEST_KNOWLEDGE_SOURCE
    assert "title" in data
    assert data["max_questions"] == 10
    assert data["focus_mode"] == "adaptive"
    assert data["questions_remaining"] == 9

def test_session_state_mastery_delta_empty_before_grading():
    session_id, _ = _start_session_with_question()
    data = client.get(f"/sessions/{session_id}/state").json()
    assert data["mastery_delta"] == {}


def test_end_session_includes_mastery_delta():
    session_id, _ = _start_session_with_question()
    client.post(
        f"/sessions/{session_id}/turn",
        json={"learner_message": "a collection of distinct elements with no order"},
    )
    _rate_question(session_id, "ok")
    client.post(f"/sessions/{session_id}/turn", json={"continue": True})

    end = client.post(f"/sessions/{session_id}/end")
    assert end.status_code == 200
    body = end.json()
    assert isinstance(body["mastery_delta"], dict)
    assert body["mastery_delta"]
    for entry in body["mastery_delta"].values():
        assert "band_before" in entry
        assert "band_after" in entry
        assert "pct_before" in entry
        assert "pct_after" in entry
        assert entry["n_observed_session"] >= 1


def test_end_session_mastery_delta_empty_with_no_grades():
    session_id, _ = _start_session_with_question()
    end = client.post(f"/sessions/{session_id}/end")
    assert end.status_code == 200
    assert end.json()["mastery_delta"] == {}


def test_config_get():
    resp = client.get("/config/provider")
    assert resp.status_code == 200
    data = resp.json()
    assert "anthropic_api_key_set" in data
    assert "nim_api_key_set" in data
    assert "model" in data
    assert "active_provider" in data


def test_config_get_testbed_stub_provider(monkeypatch):
    monkeypatch.setenv("APORE_TESTBED", "1")
    monkeypatch.setenv("APORE_TESTBED_PROVIDER", "stub")

    resp = client.get("/config/provider")

    assert resp.status_code == 200
    data = resp.json()
    assert data["active_provider"] == "stub"
    assert data["active_model"] == "stub-model"


def test_require_provider_uses_testbed_stub(monkeypatch):
    import apore.api.app as app_module
    from apore.providers.stub import StubProvider

    monkeypatch.setenv("APORE_TESTBED", "1")
    monkeypatch.setenv("APORE_TESTBED_PROVIDER", "stub")

    provider, model = app_module._require_provider()

    assert isinstance(provider, StubProvider)
    assert model == "stub-model"


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


def test_create_session_with_concept_subset():
    resp = client.post(
        "/sessions",
        json={
            "knowledge_source": TEST_KNOWLEDGE_SOURCE,
            "concept_ids": ["set_theory_intro"],
            "max_questions": 3,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["concept_ids"] == ["set_theory_intro"]
    assert data["title"]

    state = client.get(f"/sessions/{data['session_id']}/state").json()
    assert state["concept_ids"] == ["set_theory_intro"]

    q = client.post(f"/sessions/{data['session_id']}/question", json={})
    assert q.status_code == 200
    assert q.json()["concept_id"] == "set_theory_intro"


def test_create_session_rejects_empty_concept_ids():
    resp = client.post(
        "/sessions",
        json={"knowledge_source": TEST_KNOWLEDGE_SOURCE, "concept_ids": []},
    )
    assert resp.status_code == 400
    assert "at least one" in resp.json()["detail"].lower()


def test_create_session_rejects_unknown_concept_ids():
    resp = client.post(
        "/sessions",
        json={
            "knowledge_source": TEST_KNOWLEDGE_SOURCE,
            "concept_ids": ["sets_definition", "not_a_real_concept"],
        },
    )
    assert resp.status_code == 400
    assert "Unknown concept" in resp.json()["detail"]


def test_create_session_rejects_duplicate_concept_ids():
    resp = client.post(
        "/sessions",
        json={
            "knowledge_source": TEST_KNOWLEDGE_SOURCE,
            "concept_ids": ["sets_definition", "sets_definition"],
        },
    )
    assert resp.status_code == 400
    assert "Duplicate" in resp.json()["detail"]


def test_create_session_title_is_deterministic_without_provider_invoke(monkeypatch):
    """Create + first question stay sync-fast; title LLM runs only in background."""
    import threading
    import time

    import apore.api.app as app_module
    from apore.providers.stub import StubProvider

    gate = threading.Event()
    invoke_started = threading.Event()
    calls: list[object] = []

    class GatedTitleProvider(StubProvider):
        def invoke(self, system, messages, model, config=None):
            protocol = (config or {}).get("protocol")
            if protocol == "generate-session-title":
                calls.append(protocol)
                invoke_started.set()
                assert gate.wait(timeout=2), "title job was not released"
                return "LLM Session Title"
            return super().invoke(system, messages, model, config)

    monkeypatch.setattr(app_module, "get_active_provider", lambda: "stub")
    monkeypatch.setattr(app_module, "get_provider", lambda _name: GatedTitleProvider())

    resp = client.post("/sessions", json={"knowledge_source": TEST_KNOWLEDGE_SOURCE})
    assert resp.status_code == 200
    data = resp.json()
    assert data["title_pending"] is True
    assert "Adaptive Practice" in data["title"]
    # Create response returned before we release the gated LLM call.
    assert invoke_started.wait(timeout=2)
    # First question must still work while title job is in flight.
    q = client.post(f"/sessions/{data['session_id']}/question", json={})
    assert q.status_code == 200

    gate.set()
    deadline = time.time() + 2
    final = None
    while time.time() < deadline:
        state = client.get(f"/sessions/{data['session_id']}/state").json()
        if not state["title_pending"]:
            final = state
            break
        time.sleep(0.05)
    assert final is not None
    assert final["title"] == "LLM Session Title"
    assert final["title_pending"] is False
    assert calls == ["generate-session-title"]


def test_create_session_title_pending_false_without_provider(monkeypatch):
    import apore.api.app as app_module

    monkeypatch.setattr(app_module, "get_active_provider", lambda: None)

    resp = client.post("/sessions", json={"knowledge_source": TEST_KNOWLEDGE_SOURCE})
    assert resp.status_code == 200
    data = resp.json()
    assert data["title_pending"] is False
    assert "Adaptive Practice" in data["title"]
    state = client.get(f"/sessions/{data['session_id']}/state").json()
    assert state["title_pending"] is False
    assert state["title"] == data["title"]


def test_background_title_failure_keeps_fallback(monkeypatch):
    import time

    import apore.api.app as app_module

    class BoomProvider:
        def invoke(self, *args, **kwargs):
            raise RuntimeError("title boom")

    monkeypatch.setattr(app_module, "get_active_provider", lambda: "stub")
    monkeypatch.setattr(app_module, "get_provider", lambda _name: BoomProvider())

    resp = client.post("/sessions", json={"knowledge_source": TEST_KNOWLEDGE_SOURCE})
    assert resp.status_code == 200
    data = resp.json()
    fallback = data["title"]
    assert data["title_pending"] is True

    deadline = time.time() + 2
    final = None
    while time.time() < deadline:
        state = client.get(f"/sessions/{data['session_id']}/state").json()
        if not state["title_pending"]:
            final = state
            break
        time.sleep(0.05)
    assert final is not None
    assert final["title"] == fallback
    assert final["title_pending"] is False


def test_session_persists_concept_ids_in_markdown():
    import apore.api.app as app_module

    resp = client.post(
        "/sessions",
        json={
            "knowledge_source": TEST_KNOWLEDGE_SOURCE,
            "concept_ids": ["sets_definition"],
        },
    )
    assert resp.status_code == 200
    session_id = resp.json()["session_id"]
    path = app_module.SESSIONS_DIR / f"{session_id}.md"
    text = path.read_text(encoding="utf-8")
    assert "concept_ids: sets_definition" in text


def test_write_title_updates_markdown_h1(tmp_path):
    from apore.runtime import state as state_mod

    path = tmp_path / "session.md"
    state_mod.initialize(
        path,
        title="Old Title",
        session_id="abc",
        created_at="2026-01-01T00:00:00Z",
        knowledge_source=TEST_KNOWLEDGE_SOURCE,
        focus_mode="adaptive",
        max_questions=5,
        concept_ids=["sets_definition"],
    )
    state_mod.write_title(path, "New Fancy Title")
    assert state_mod.read_title(path) == "New Fancy Title"
    assert path.read_text(encoding="utf-8").startswith("# New Fancy Title\n")
