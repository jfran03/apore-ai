"""Tests for derive-on-read mastery aggregation (PROGRESSION.md P1)."""

from __future__ import annotations

from pathlib import Path

import pytest

from apore.runtime import state
from apore.runtime.mastery import collect_observations, derive_mastery, derive_mastery_floats


def _init_session(
    path: Path,
    *,
    session_id: str,
    knowledge_source: str,
) -> None:
    state.initialize(
        path,
        title="Test",
        session_id=session_id,
        created_at="2026-01-01T00:00:00+00:00",
        knowledge_source=knowledge_source,
        focus_mode="adaptive",
        max_questions=10,
        concept_ids=["alpha", "beta"],
    )


def _append(
    path: Path,
    *,
    q: int,
    session: str,
    concept: str,
    correct: str,
    day: str = "2026-01-01",
) -> None:
    state.append_log_row(
        path,
        {
            "Q#": q,
            "session": session,
            "date": day,
            "question_id": f"q-{q}",
            "concept": concept,
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


def test_parse_question_log_roundtrip(tmp_path: Path):
    p = tmp_path / "s.md"
    _init_session(p, session_id="s1", knowledge_source="domain:a/01")
    assert state.parse_question_log(p) == []
    _append(p, q=1, session="s1", concept="alpha", correct="yes")
    rows = state.parse_question_log(p)
    assert len(rows) == 1
    assert rows[0]["concept"] == "alpha"
    assert rows[0]["correct"] == "yes"


def test_aggregate_filters_knowledge_source(tmp_path: Path):
    keep = tmp_path / "keep.md"
    other = tmp_path / "other.md"
    skip = tmp_path / "_bank_gen.md"
    _init_session(keep, session_id="k", knowledge_source="domain:_pytest/01-intro")
    _init_session(other, session_id="o", knowledge_source="domain:discrete-math/01-set-theory")
    _init_session(skip, session_id="b", knowledge_source="domain:_pytest/01-intro")
    _append(keep, q=1, session="k", concept="alpha", correct="yes")
    _append(keep, q=2, session="k", concept="alpha", correct="yes")
    _append(other, q=1, session="o", concept="alpha", correct="no")
    _append(skip, q=1, session="b", concept="alpha", correct="no")

    derived = derive_mastery(
        tmp_path,
        "domain:_pytest/01-intro",
        ["alpha", "beta"],
    )
    assert derived["beta"].band == "new"
    assert derived["beta"].n_observed == 0
    assert derived["alpha"].n_observed == 2
    assert derived["alpha"].p_mastery == pytest.approx(0.4)
    assert derived["alpha"].band == "learning"

    floats = derive_mastery_floats(tmp_path, "domain:_pytest/01-intro", ["alpha", "beta"])
    assert "beta" not in floats
    assert floats["alpha"] == pytest.approx(0.4)


def test_skips_non_binary_correct(tmp_path: Path):
    p = tmp_path / "s.md"
    _init_session(p, session_id="s", knowledge_source="domain:x/y")
    _append(p, q=1, session="s", concept="alpha", correct="")
    _append(p, q=2, session="s", concept="alpha", correct="yes")
    obs = collect_observations(tmp_path, "domain:x/y")
    assert len(obs["alpha"]) == 1


def test_sorts_by_date_then_qnum(tmp_path: Path):
    from apore.runtime.bkt import replay

    p = tmp_path / "s.md"
    _init_session(p, session_id="s", knowledge_source="domain:x/y")
    # Append out of chronological order; derive should sort.
    _append(p, q=2, session="s", concept="alpha", correct="yes", day="2026-01-02")
    _append(p, q=1, session="s", concept="alpha", correct="no", day="2026-01-01")
    m = derive_mastery(tmp_path, "domain:x/y", ["alpha"])["alpha"]
    assert m.p_mastery == pytest.approx(replay([0, 1]).p_mastery)