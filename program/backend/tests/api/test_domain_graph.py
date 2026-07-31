"""API tests for GET /domains/{domain_id}/graph (knowledge graph page)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import apore.api.app as app_module
from apore.runtime import state
from tests.api.conftest import TEST_KNOWLEDGE_SOURCE

TEST_DOMAIN_ID = "_pytest"


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


def test_domain_graph_shape_all_new(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(app_module, "SESSIONS_DIR", tmp_path)
    client = TestClient(app_module.app)
    res = client.get(f"/domains/{TEST_DOMAIN_ID}/graph")
    assert res.status_code == 200
    body = res.json()
    assert body["domain_id"] == TEST_DOMAIN_ID
    assert len(body["chapters"]) == 1

    chapter = body["chapters"][0]
    assert chapter["id"] == "01-intro"
    assert chapter["knowledge_source"] == TEST_KNOWLEDGE_SOURCE
    assert chapter["has_concept_graph"] is True
    assert chapter["concepts_total"] == 2
    assert chapter["concepts_proficient"] == 0
    assert chapter["mastery_pct"] == 0
    assert len(chapter["edges"]) == 1
    assert chapter["edges"][0] == {
        "source": "sets_definition",
        "target": "set_theory_intro",
        "relation": "prerequisite_of",
    }

    by_id = {c["id"]: c for c in chapter["concepts"]}
    assert by_id["set_theory_intro"]["has_wiki"] is True
    assert by_id["sets_definition"]["has_wiki"] is False
    for concept in chapter["concepts"]:
        assert concept["band"] == "new"
        assert concept["p_mastery"] is None
        assert concept["display_pct"] is None
        assert concept["n_observed"] == 0


def test_domain_graph_reflects_mastery(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(app_module, "SESSIONS_DIR", tmp_path)
    _write_logged_session(tmp_path, correct_sequence=["yes", "yes", "yes"])
    client = TestClient(app_module.app)
    chapter = client.get(f"/domains/{TEST_DOMAIN_ID}/graph").json()["chapters"][0]

    by_id = {c["id"]: c for c in chapter["concepts"]}
    assert by_id["sets_definition"]["band"] == "proficient"
    assert by_id["sets_definition"]["n_observed"] == 3
    assert chapter["concepts_proficient"] == 1
    # One proficient concept (~0.78) and one never-observed (0) => mean ~39%.
    assert 30 <= chapter["mastery_pct"] <= 50


def test_domain_graph_parity_with_learner_mastery(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(app_module, "SESSIONS_DIR", tmp_path)
    _write_logged_session(tmp_path, correct_sequence=["yes", "no", "yes"])
    client = TestClient(app_module.app)

    graph_concepts = {
        c["id"]: c
        for c in client.get(f"/domains/{TEST_DOMAIN_ID}/graph").json()["chapters"][0][
            "concepts"
        ]
    }
    mastery = client.get(
        "/learner/mastery", params={"knowledge_source": TEST_KNOWLEDGE_SOURCE}
    ).json()["concepts"]

    for cid, m in mastery.items():
        g = graph_concepts[cid]
        assert g["p_mastery"] == m["p_mastery"]
        assert g["band"] == m["band"]
        assert g["n_observed"] == m["n_observed"]
        assert g["display_pct"] == m["display_pct"]


def test_domain_graph_unknown_domain_404() -> None:
    client = TestClient(app_module.app)
    assert client.get("/domains/does-not-exist/graph").status_code == 404


def test_domain_graph_invalid_id_400() -> None:
    client = TestClient(app_module.app)
    assert client.get("/domains/Bad%20Id/graph").status_code == 400
