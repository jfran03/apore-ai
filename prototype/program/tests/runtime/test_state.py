"""Round-trip tests for apore.runtime.state and apore.runtime.paths."""

from __future__ import annotations

import pytest
from pathlib import Path

from apore.runtime.paths import get_program_root
from apore.runtime.state import (
    append_log_row,
    initialize,
    read_mastery,
    read_scalar,
    write_mastery,
    write_scalar,
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
        "concept": "concept-a",
        "question_type": "recall",
        "intended_difficulty": 0.5,
        "explicit_rating": "easy",
        "correct": "yes",
        "hints": 0,
        "turns": 2,
        "hedging": 0,
        "reward_R": 0.61,
        "new_difficulty": 0.56,
    }


def test_append_single_row(tmp_path: Path):
    p = tmp_path / "learner-state.md"
    initialize(p)
    append_log_row(p, _sample_row(1))
    text = p.read_text(encoding="utf-8")
    assert "| 1 |" in text
    assert "concept-a" in text


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
