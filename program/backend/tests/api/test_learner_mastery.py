"""API tests for GET /learner/mastery (PROGRESSION.md P2)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import apore.api.app as app_module
from apore.runtime import state
from tests.api.conftest import TEST_KNOWLEDGE_SOURCE


def _write_logged_session(sessions_dir: Path, *, correct_sequence: list[str]) -> None:
    path = sessions_dir / "logged.md"
    state.initialize(
        path,
        title="Logged",
        session_id="logged",
        created_at="2026-01-01T00:00:00+00:00",
        knowledge_source=TEST_KNOWLEDGE_SOURCE,
        focus_mode="adaptive",
        max_questions=10,
        concept_ids=["sets_definition"],
    )
    for i, correct in enumerate(correct_sequence, start=1):
        state.append_log_row(
            path,
            {
                "Q#": i,
                "session": "logged",
                "date": "2026-01-01",
                "question_id": f"q-{i}",
                "concept": "sets_definition",
                "question_type": "recall",
                "intended_difficulty": 0.5,
                "explicit_rating": "ok",
                "correct": correct,
                "hints": 0,
                "turns": 1,
                "hedging": 0,
                "reward_R": 0.0,
                "new_difficulty": 0.5,
            },
        )


def test_learner_mastery_empty_chapter_all_new(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(app_module, "SESSIONS_DIR", tmp_path)
    client = TestClient(app_module.app)
    res = client.get("/learner/mastery", params={"knowledge_source": TEST_KNOWLEDGE_SOURCE})
    assert res.status_code == 200
    body = res.json()
    assert body["knowledge_source"] == TEST_KNOWLEDGE_SOURCE
    assert body["params"]["p_F"] == 0.0
    assert body["concepts"]
    for concept in body["concepts"].values():
        assert concept["band"] == "new"
        assert concept["n_observed"] == 0
        assert concept["p_mastery"] is None
        assert concept["display_pct"] is None


def test_learner_mastery_replays_logs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(app_module, "SESSIONS_DIR", tmp_path)
    _write_logged_session(tmp_path, correct_sequence=["yes", "yes", "yes"])
    client = TestClient(app_module.app)
    res = client.get("/learner/mastery", params={"knowledge_source": TEST_KNOWLEDGE_SOURCE})
    assert res.status_code == 200
    concept = res.json()["concepts"]["sets_definition"]
    assert concept["n_observed"] == 3
    assert concept["band"] == "proficient"
    assert concept["display_pct"] == 78


def test_learner_mastery_missing_source_422() -> None:
    client = TestClient(app_module.app)
    res = client.get("/learner/mastery")
    assert res.status_code == 422


def test_learner_mastery_unknown_chapter_404() -> None:
    client = TestClient(app_module.app)
    res = client.get(
        "/learner/mastery",
        params={"knowledge_source": "domain:does-not-exist/nope"},
    )
    assert res.status_code == 404


def test_learner_mastery_malformed_400() -> None:
    client = TestClient(app_module.app)
    res = client.get(
        "/learner/mastery",
        params={"knowledge_source": "not-a-valid-source"},
    )
    assert res.status_code == 400
