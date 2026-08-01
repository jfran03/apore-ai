"""Round-trip tests for apore.runtime.state and apore.runtime.paths."""

from __future__ import annotations

import pytest
from pathlib import Path

from apore.runtime.paths import get_program_root
from apore.runtime.state import (
    append_asked_id,
    append_log_row,
    initialize,
    parse_question_log,
    read_asked_ids,
    read_conversation_items,
    read_mastery,
    read_runtime,
    read_scalar,
    read_session_meta,
    read_title,
    write_conversation_items,
    write_mastery,
    write_runtime,
    write_scalar,
    write_session_status,
)


# ---------------------------------------------------------------------------
# paths
# ---------------------------------------------------------------------------

def test_get_program_root_contains_apore():
    root = get_program_root()
    assert (root / "apore").is_dir(), f"Expected apore/ under {root}"


def test_get_program_root_is_absolute():
    assert get_program_root().is_absolute()


# ---------------------------------------------------------------------------
# initialize
# ---------------------------------------------------------------------------

def test_initialize_creates_file(tmp_path: Path):
    p = tmp_path / "learner-state.md"
    initialize(p)
    assert p.exists()


def test_initialize_default_scalar(tmp_path: Path):
    p = tmp_path / "learner-state.md"
    initialize(p)
    assert read_scalar(p) == pytest.approx(0.5)


def test_initialize_empty_mastery(tmp_path: Path):
    p = tmp_path / "learner-state.md"
    initialize(p)
    assert read_mastery(p) == {}


def test_initialize_with_session_metadata(tmp_path: Path):
    p = tmp_path / "learner-state.md"
    initialize(
        p,
        title="Set Theory Basics",
        session_id="abc-123",
        created_at="2026-06-03T12:00:00+00:00",
        knowledge_source="domain:discrete-math/01-set-theory",
        focus_mode="weak_points",
        max_questions=5,
    )
    assert read_title(p) == "Set Theory Basics"
    meta = read_session_meta(p)
    assert meta["id"] == "abc-123"
    assert meta["knowledge_source"] == "domain:discrete-math/01-set-theory"
    assert meta["focus_mode"] == "weak_points"
    assert meta["max_questions"] == "5"
    assert meta["status"] == "active"
    assert meta["ended_at"] == ""
    assert read_scalar(p) == pytest.approx(0.5)


def test_write_session_status_roundtrip(tmp_path: Path):
    p = tmp_path / "learner-state.md"
    initialize(
        p,
        title="Drill",
        session_id="abc-123",
        created_at="2026-06-03T12:00:00+00:00",
        knowledge_source="domain:discrete-math/01-set-theory",
        focus_mode="adaptive",
        max_questions=10,
    )
    write_session_status(
        p,
        status="ended_early",
        ended_at="2026-06-03T13:00:00+00:00",
    )
    meta = read_session_meta(p)
    assert meta["status"] == "ended_early"
    assert meta["ended_at"] == "2026-06-03T13:00:00+00:00"


def test_legacy_session_meta_defaults_to_active(tmp_path: Path):
    p = tmp_path / "learner-state.md"
    p.write_text(
        "# Old Session\n\n"
        "## Session\n"
        "id: legacy-1\n"
        "created_at: 2026-01-01T00:00:00+00:00\n"
        "knowledge_source: domain:_pytest/01-intro\n"
        "focus_mode: adaptive\n"
        "max_questions: 10\n\n"
        "## Scalar\n"
        "0.5\n\n"
        "## Mastery\n\n"
        "## Asked Questions\n\n"
        "## Question Log\n"
        "| Q# |\n"
        "|---|\n",
        encoding="utf-8",
    )
    meta = read_session_meta(p)
    assert meta["status"] == "active"
    assert meta["ended_at"] == ""
    write_session_status(p, status="completed", ended_at="2026-01-02T00:00:00+00:00")
    meta2 = read_session_meta(p)
    assert meta2["status"] == "completed"
    assert meta2["ended_at"] == "2026-01-02T00:00:00+00:00"


# ---------------------------------------------------------------------------
# scalar round-trip
# ---------------------------------------------------------------------------

def test_write_then_read_scalar(tmp_path: Path):
    p = tmp_path / "learner-state.md"
    initialize(p)
    write_scalar(p, 0.75)
    assert read_scalar(p) == pytest.approx(0.75)


def test_write_scalar_multiple_times(tmp_path: Path):
    p = tmp_path / "learner-state.md"
    initialize(p)
    write_scalar(p, 0.3)
    write_scalar(p, 0.8)
    assert read_scalar(p) == pytest.approx(0.8)


def test_write_scalar_clamps_low(tmp_path: Path):
    p = tmp_path / "learner-state.md"
    initialize(p)
    write_scalar(p, 0.0)
    assert read_scalar(p) == pytest.approx(0.1)


def test_write_scalar_clamps_high(tmp_path: Path):
    p = tmp_path / "learner-state.md"
    initialize(p)
    write_scalar(p, 1.0)
    assert read_scalar(p) == pytest.approx(0.9)


# ---------------------------------------------------------------------------
# mastery round-trip
# ---------------------------------------------------------------------------

def test_write_then_read_mastery(tmp_path: Path):
    p = tmp_path / "learner-state.md"
    initialize(p)
    mastery = {"concept-a": 0.6, "concept-b": 0.4}
    write_mastery(p, mastery)
    result = read_mastery(p)
    assert result == pytest.approx(mastery)


def test_write_mastery_overwrites_previous(tmp_path: Path):
    p = tmp_path / "learner-state.md"
    initialize(p)
    write_mastery(p, {"concept-a": 0.6})
    write_mastery(p, {"concept-b": 0.9})
    result = read_mastery(p)
    assert "concept-a" not in result
    assert result["concept-b"] == pytest.approx(0.9)


def test_write_mastery_does_not_corrupt_scalar(tmp_path: Path):
    p = tmp_path / "learner-state.md"
    initialize(p)
    write_scalar(p, 0.42)
    write_mastery(p, {"concept-x": 0.7})
    assert read_scalar(p) == pytest.approx(0.42)


# ---------------------------------------------------------------------------
# log row append
# ---------------------------------------------------------------------------

def _sample_row(q_num: int = 1) -> dict:
    return {
        "Q#": q_num,
        "session": "s1",
        "date": "2026-01-01",
        "question_id": f"q-{q_num}",
        "concept": "concept-a",
        "question_type": "recall",
        "intended_difficulty": 0.5,
        "explicit_rating": "easy",
        "correct": "yes",
        "assisted": "no",
        "hints": 0,
        "turns": 2,
        "hedging": 0,
        "reward_R": 0.61,
        "new_difficulty": 0.56,
    }


def test_append_single_row(tmp_path: Path):
    p = tmp_path / "learner-state.md"
    initialize(
        p,
        title="Test",
        session_id="s1",
        created_at="2026-01-01T00:00:00+00:00",
        knowledge_source="domain:x/y",
        focus_mode="adaptive",
        max_questions=10,
    )
    append_log_row(p, _sample_row(1))
    text = p.read_text(encoding="utf-8")
    assert "| 1 |" in text
    assert "concept-a" in text
    rows = parse_question_log(p)
    assert rows[0]["assisted"] == "no"


def test_assisted_column_roundtrip(tmp_path: Path):
    p = tmp_path / "learner-state.md"
    initialize(
        p,
        title="Test",
        session_id="s1",
        created_at="2026-01-01T00:00:00+00:00",
        knowledge_source="domain:x/y",
        focus_mode="adaptive",
        max_questions=10,
    )
    header = p.read_text(encoding="utf-8")
    assert "| assisted |" in header
    row = _sample_row(1)
    row["assisted"] = "yes"
    append_log_row(p, row)
    rows = parse_question_log(p)
    assert rows[0]["assisted"] == "yes"


def test_append_multiple_rows(tmp_path: Path):
    p = tmp_path / "learner-state.md"
    initialize(p)
    append_log_row(p, _sample_row(1))
    append_log_row(p, _sample_row(2))
    append_log_row(p, _sample_row(3))
    text = p.read_text(encoding="utf-8")
    assert text.count("| concept-a |") == 3


def test_append_does_not_delete_previous_rows(tmp_path: Path):
    p = tmp_path / "learner-state.md"
    initialize(p)
    append_log_row(p, _sample_row(1))
    append_log_row(p, _sample_row(2))
    text = p.read_text(encoding="utf-8")
    assert "| 1 |" in text
    assert "| 2 |" in text


def test_append_preserves_scalar_and_mastery(tmp_path: Path):
    p = tmp_path / "learner-state.md"
    initialize(p)
    write_scalar(p, 0.55)
    write_mastery(p, {"concept-a": 0.7})
    append_log_row(p, _sample_row(1))
    assert read_scalar(p) == pytest.approx(0.55)
    assert read_mastery(p)["concept-a"] == pytest.approx(0.7)


def test_asked_ids_roundtrip(tmp_path: Path):
    p = tmp_path / "learner-state.md"
    initialize(p)
    assert read_asked_ids(p) == set()
    append_asked_id(p, "sets_definition-recall-01")
    append_asked_id(p, "sets_definition-apply-01")
    assert read_asked_ids(p) == {"sets_definition-recall-01", "sets_definition-apply-01"}
    append_asked_id(p, "sets_definition-recall-01")
    assert read_asked_ids(p) == {"sets_definition-recall-01", "sets_definition-apply-01"}


def test_conversation_and_runtime_roundtrip(tmp_path: Path):
    p = tmp_path / "learner-state.md"
    initialize(
        p,
        title="Chat",
        session_id="abc-123",
        created_at="2026-06-03T12:00:00+00:00",
        knowledge_source="domain:discrete-math/01-set-theory",
        focus_mode="adaptive",
        max_questions=10,
    )
    assert "## Conversation" in p.read_text(encoding="utf-8")
    assert "## Runtime" in p.read_text(encoding="utf-8")
    assert read_conversation_items(p) == []
    assert read_runtime(p) is None

    write_conversation_items(
        p,
        [
            {
                "question_number": 1,
                "question_id": "q1",
                "question_text": "What is a set?",
                "concept_id": "sets",
                "concept_label": "Sets",
                "correct": "yes",
                "explicit_rating": "ok",
                "assisted": False,
                "status": "completed",
                "messages": [
                    {"role": "assistant", "content": "What is a set?"},
                    {"role": "user", "content": "A collection of objects."},
                ],
            }
        ],
    )
    items = read_conversation_items(p)
    assert len(items) == 1
    assert items[0]["question_text"] == "What is a set?"
    assert items[0]["messages"][1]["content"] == "A collection of objects."
    assert "```json" in p.read_text(encoding="utf-8")

    write_runtime(p, {"question_count": 1, "tutor_mode": True})
    runtime = read_runtime(p)
    assert runtime == {"question_count": 1, "tutor_mode": True}

    append_log_row(p, _sample_row(1))
    # Log rows stay in Question Log; runtime section remains parseable.
    assert read_runtime(p) == {"question_count": 1, "tutor_mode": True}
    assert len(parse_question_log(p)) == 1
    assert len(read_conversation_items(p)) == 1

    write_runtime(p, None)
    assert read_runtime(p) is None


def test_initialize_session_includes_conversation_runtime(tmp_path: Path):
    p = tmp_path / "learner-state.md"
    initialize(
        p,
        title="Set Theory Basics",
        session_id="abc-123",
        created_at="2026-06-03T12:00:00+00:00",
        knowledge_source="domain:discrete-math/01-set-theory",
        focus_mode="weak_points",
        max_questions=5,
    )
    text = p.read_text(encoding="utf-8")
    assert text.index("## Conversation") < text.index("## Runtime")
    assert text.index("## Runtime") < text.index("## Question Log")
