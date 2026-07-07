import json

import pytest

from apore.domains import sessionfile, store
from apore.runtime.core import AssessmentResult, GeneratedQuestion, GradingResult


@pytest.fixture(autouse=True)
def data_root(tmp_path, monkeypatch):
    monkeypatch.setenv("APORE_DATA_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture()
def domain():
    return store.create_domain(
        name="T", objective="o", teaching_style="socratic",
        teaching_prompt="p", model_preference="auto",
    )


def _create(domain, session_id="sid-1"):
    return sessionfile.create_session_file(
        domain,
        session_id=session_id,
        title="Set Theory — Adaptive Practice",
        knowledge_source=f"workspace:{domain.domain_id}/01-set-theory",
        chapter_id="01-set-theory",
        focus_mode="adaptive",
        max_questions=10,
        created_at="2026-07-06T00:00:00+00:00",
    )


def test_create_and_load_roundtrip(domain):
    _create(domain)
    data = sessionfile.load_session_file(domain, "sid-1")
    assert data["session_id"] == "sid-1"
    assert data["title"].startswith("Set Theory")
    assert data["transcript"] == []
    assert data["resume"] is None
    assert sessionfile.session_dir(domain, "sid-1").is_dir()


def test_append_events_adds_ts_and_persists(domain):
    _create(domain)
    sessionfile.append_events(
        domain, "sid-1",
        [{"type": "question", "question_number": 1, "question_id": "q1",
          "concept_id": "sets", "concept_label": "Sets", "question_text": "?"}],
    )
    sessionfile.append_events(domain, "sid-1", [{"type": "learner_message", "text": "hi"}])
    data = sessionfile.load_session_file(domain, "sid-1")
    assert [e["type"] for e in data["transcript"]] == ["question", "learner_message"]
    assert all(e["ts"] for e in data["transcript"])


def test_resume_snapshot_roundtrip(domain):
    _create(domain)
    question = GeneratedQuestion(
        question_number=1, question_id="q1", concept_id="sets",
        concept_label="Sets", question_type="recall",
        intended_difficulty=0.5, question_text="?", gen_response="raw",
    )
    assessment = AssessmentResult(correct="yes", hint_count=0, turn_count=1, hedging_count=0)
    grading = GradingResult(
        question_number=1, explicit_rating="ok", correct="yes", hint_count=0,
        turn_count=1, hedging_count=0, reward=0.4, new_difficulty=0.55,
    )
    resume = {
        "question_count": 1,
        "active_concept_id": "sets",
        "tutor_mode": False,
        "awaiting_skip_reason": False,
        "active_transcript": [],
        "pending_question": None,
        "pending_grading": None,
        "reflection": {
            "question": sessionfile.question_to_dict(question),
            "assessment": sessionfile.assessment_to_dict(assessment),
            "grading": sessionfile.grading_to_dict(grading),
            "transcript": [],
        },
    }
    sessionfile.write_resume(domain, "sid-1", question_count=1, resume=resume)
    data = sessionfile.load_session_file(domain, "sid-1")
    restored = data["resume"]["reflection"]
    assert sessionfile.question_from_dict(restored["question"]) == question
    assert sessionfile.assessment_from_dict(restored["assessment"]) == assessment
    assert sessionfile.grading_from_dict(restored["grading"]) == grading
    assert data["question_count"] == 1


def test_list_sessions_sorted_and_status(domain):
    _create(domain, "sid-1")
    _create(domain, "sid-2")
    sessionfile.write_resume(domain, "sid-2", question_count=10, resume=None)
    summaries = sessionfile.list_sessions(domain)
    assert [s["session_id"] for s in summaries] == ["sid-2", "sid-1"]
    by_id = {s["session_id"]: s for s in summaries}
    assert by_id["sid-2"]["status"] == "complete"
    assert by_id["sid-1"]["status"] == "active"


def test_corrupt_session_json_raises(domain):
    _create(domain)
    sessionfile.session_json_path(domain, "sid-1").write_text("{broken", encoding="utf-8")
    with pytest.raises(sessionfile.SessionFileError):
        sessionfile.load_session_file(domain, "sid-1")


def test_corrupt_session_listed_as_invalid(domain):
    _create(domain, "sid-1")
    sessionfile.session_json_path(domain, "sid-1").write_text("{broken", encoding="utf-8")
    summaries = sessionfile.list_sessions(domain)
    assert summaries[0]["status"] == "invalid"
