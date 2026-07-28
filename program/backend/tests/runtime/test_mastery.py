"""Tests for derive-on-read mastery aggregation (PROGRESSION.md P1)."""

from __future__ import annotations

from pathlib import Path

import pytest

from apore.runtime import state
from apore.runtime.bkt import empty_mastery, replay
from apore.runtime.mastery import (
    collect_observations,
    derive_mastery,
    derive_mastery_delta,
    derive_mastery_floats,
)


def _init_session(
    path: Path,
    *,
    session_id: str,
    knowledge_source: str,
    created_at: str = "2026-01-01T00:00:00+00:00",
) -> None:
    state.initialize(
        path,
        title="Test",
        session_id=session_id,
        created_at=created_at,
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
    assisted: str = "no",
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
            "assisted": assisted,
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
    created_at, qnum, val, session_id, assisted = obs["alpha"][0]
    assert created_at == "2026-01-01T00:00:00+00:00"
    assert qnum == 2
    assert val == 1
    assert session_id == "s"
    assert assisted is False


def test_assisted_correct_yields_smaller_mastery(tmp_path: Path):
    # From P(L)=0 the first correct is always p_T; dampening appears on later steps.
    unaided_dir = tmp_path / "unaided"
    assisted_dir = tmp_path / "assisted"
    unaided_dir.mkdir()
    assisted_dir.mkdir()
    u = unaided_dir / "s.md"
    a = assisted_dir / "s.md"
    _init_session(u, session_id="s", knowledge_source="domain:x/y")
    _init_session(a, session_id="s", knowledge_source="domain:x/y")
    _append(u, q=1, session="s", concept="alpha", correct="yes", assisted="no")
    _append(u, q=2, session="s", concept="alpha", correct="yes", assisted="no")
    _append(a, q=1, session="s", concept="alpha", correct="yes", assisted="no")
    _append(a, q=2, session="s", concept="alpha", correct="yes", assisted="yes")
    u_m = derive_mastery(unaided_dir, "domain:x/y", ["alpha"])["alpha"]
    a_m = derive_mastery(assisted_dir, "domain:x/y", ["alpha"])["alpha"]
    assert u_m.p_mastery is not None and a_m.p_mastery is not None
    assert a_m.p_mastery < u_m.p_mastery
    assert a_m.p_mastery > 0.0


def test_legacy_log_without_assisted_column_scores_unassisted(tmp_path: Path):
    p = tmp_path / "legacy.md"
    p.write_text(
        "# Legacy\n\n"
        "## Session\n"
        "id: legacy\n"
        "created_at: 2026-01-01T00:00:00+00:00\n"
        "knowledge_source: domain:x/y\n"
        "focus_mode: adaptive\n"
        "max_questions: 10\n"
        "concept_ids: alpha\n"
        "status: active\n"
        "ended_at: \n\n"
        "## Scalar\n"
        "0.5\n\n"
        "## Mastery\n\n"
        "## Asked Questions\n\n"
        "## Question Log\n"
        "| Q# | session | date | question_id | concept | question_type | intended_difficulty | explicit_rating | correct | hints | turns | hedging | reward_R | new_difficulty |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
        "| 1 | legacy | 2026-01-01 | q-1 | alpha | recall | 0.5 | ok | yes | 0 | 1 | 0 | 0.0 | 0.5 |\n",
        encoding="utf-8",
    )
    obs = collect_observations(tmp_path, "domain:x/y")
    assert obs["alpha"][0][4] is False
    m = derive_mastery(tmp_path, "domain:x/y", ["alpha"])["alpha"]
    assert m.p_mastery == pytest.approx(replay([1]).p_mastery)

def test_sorts_by_created_at_then_qnum(tmp_path: Path):
    p = tmp_path / "s.md"
    _init_session(
        p,
        session_id="s",
        knowledge_source="domain:x/y",
        created_at="2026-01-01T00:00:00+00:00",
    )
    # Append out of chronological order; derive should sort by Q# within session.
    _append(p, q=2, session="s", concept="alpha", correct="yes", day="2026-01-02")
    _append(p, q=1, session="s", concept="alpha", correct="no", day="2026-01-01")
    m = derive_mastery(tmp_path, "domain:x/y", ["alpha"])["alpha"]
    assert m.p_mastery == pytest.approx(replay([0, 1]).p_mastery)


def test_same_day_sessions_order_by_created_at(tmp_path: Path):
    """Two sessions on the same calendar day must not interleave by Q#."""
    early = tmp_path / "early.md"
    late = tmp_path / "late.md"
    _init_session(
        early,
        session_id="early",
        knowledge_source="domain:x/y",
        created_at="2026-07-24T09:00:00+00:00",
    )
    _init_session(
        late,
        session_id="late",
        knowledge_source="domain:x/y",
        created_at="2026-07-24T15:00:00+00:00",
    )
    # Same log date; late session Q#1 must follow early session Q#2.
    _append(early, q=1, session="early", concept="alpha", correct="no", day="2026-07-24")
    _append(early, q=2, session="early", concept="alpha", correct="yes", day="2026-07-24")
    _append(late, q=1, session="late", concept="alpha", correct="yes", day="2026-07-24")

    expected = replay([0, 1, 1])
    actual = derive_mastery(tmp_path, "domain:x/y", ["alpha"])["alpha"]
    assert actual.p_mastery == pytest.approx(expected.p_mastery)
    assert actual.n_observed == 3

    # If we wrongly sorted by (date, Q#) alone, order would be
    # early Q1, late Q1, early Q2 → [0, 1, 1] same here by coincidence.
    # Force a sequence where wrong order differs: early wrong then late wrong,
    # then early correct vs interleaved.
    wrong_early = tmp_path / "w1.md"
    wrong_late = tmp_path / "w2.md"
    ks = "domain:order/check"
    _init_session(
        wrong_early,
        session_id="w1",
        knowledge_source=ks,
        created_at="2026-07-24T09:00:00+00:00",
    )
    _init_session(
        wrong_late,
        session_id="w2",
        knowledge_source=ks,
        created_at="2026-07-24T15:00:00+00:00",
    )
    _append(wrong_early, q=1, session="w1", concept="beta", correct="yes", day="2026-07-24")
    _append(wrong_early, q=2, session="w1", concept="beta", correct="no", day="2026-07-24")
    _append(wrong_late, q=1, session="w2", concept="beta", correct="yes", day="2026-07-24")
    # Correct chronological: yes, no, yes
    # Wrong date+Q# interleave: yes (w1 Q1), yes (w2 Q1), no (w1 Q2)
    chronological = replay([1, 0, 1])
    interleaved_wrong = replay([1, 1, 0])
    assert chronological.p_mastery != pytest.approx(interleaved_wrong.p_mastery)
    got = derive_mastery(tmp_path, ks, ["beta"])["beta"]
    assert got.p_mastery == pytest.approx(chronological.p_mastery)


def test_derive_mastery_delta_before_after(tmp_path: Path):
    prior = tmp_path / "prior.md"
    current = tmp_path / "current.md"
    ks = "domain:delta/ch"
    _init_session(
        prior,
        session_id="prior",
        knowledge_source=ks,
        created_at="2026-01-01T00:00:00+00:00",
    )
    _init_session(
        current,
        session_id="current",
        knowledge_source=ks,
        created_at="2026-01-02T00:00:00+00:00",
    )
    _append(prior, q=1, session="prior", concept="alpha", correct="yes")
    _append(prior, q=2, session="prior", concept="alpha", correct="yes")
    _append(current, q=1, session="current", concept="alpha", correct="yes")
    _append(current, q=2, session="current", concept="beta", correct="no")

    delta = derive_mastery_delta(tmp_path, ks, "current")
    assert set(delta.keys()) == {"alpha", "beta"}

    assert delta["alpha"].n_observed_session == 1
    assert delta["alpha"].before.p_mastery == pytest.approx(replay([1, 1]).p_mastery)
    assert delta["alpha"].after.p_mastery == pytest.approx(replay([1, 1, 1]).p_mastery)

    assert delta["beta"].n_observed_session == 1
    assert delta["beta"].before == empty_mastery()
    assert delta["beta"].after.p_mastery == pytest.approx(replay([0]).p_mastery)
    assert delta["beta"].before.band == "new"
    assert delta["beta"].after.band == "struggling"


def test_derive_mastery_delta_untouched_absent(tmp_path: Path):
    p = tmp_path / "s.md"
    _init_session(p, session_id="s", knowledge_source="domain:z/z")
    _append(p, q=1, session="s", concept="alpha", correct="yes")
    delta = derive_mastery_delta(
        tmp_path,
        "domain:z/z",
        "s",
        concept_ids=["alpha", "beta"],
    )
    assert "alpha" in delta
    assert "beta" not in delta


def test_derive_mastery_delta_empty_session(tmp_path: Path):
    p = tmp_path / "s.md"
    _init_session(p, session_id="s", knowledge_source="domain:z/z")
    delta = derive_mastery_delta(tmp_path, "domain:z/z", "s")
    assert delta == {}
