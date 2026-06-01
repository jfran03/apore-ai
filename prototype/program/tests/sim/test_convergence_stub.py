"""Tests for apore.sim modules using StubProvider."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apore.sim.convergence import (
    compute_session_error,
    compute_trend,
    write_artifacts,
)
from apore.sim.runner import run_sessions
from apore.sim.student import StudentProfile


# ---------------------------------------------------------------------------
# 1. run_sessions produces the right number of trajectory dicts
# ---------------------------------------------------------------------------

def test_run_sessions_produces_trajectories():
    profile = StudentProfile(ability=0.7)
    sessions = run_sessions(
        num_sessions=3,
        questions_per_session=3,
        profile=profile,
    )
    assert len(sessions) == 3


# ---------------------------------------------------------------------------
# 2. Each trajectory has session_id and difficulties list of correct length
# ---------------------------------------------------------------------------

def test_trajectory_has_correct_shape():
    profile = StudentProfile(ability=0.7)
    sessions = run_sessions(
        num_sessions=3,
        questions_per_session=3,
        profile=profile,
    )
    for session in sessions:
        assert "session_id" in session
        assert "difficulties" in session
        assert len(session["difficulties"]) == 3
        for d in session["difficulties"]:
            assert isinstance(d, float)
            assert 0.1 <= d <= 0.9


# ---------------------------------------------------------------------------
# 3. compute_session_error — unit math
# ---------------------------------------------------------------------------

def test_compute_session_error():
    trajectory = [0.5, 0.6, 0.7]
    target = 0.7
    # errors: 0.2, 0.1, 0.0  → mean = 0.1
    error = compute_session_error(trajectory, target)
    assert error == pytest.approx(0.1)


def test_compute_session_error_exact_match():
    trajectory = [0.5, 0.5, 0.5]
    error = compute_session_error(trajectory, 0.5)
    assert error == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# 4. compute_trend — negative on converging (decreasing) errors
# ---------------------------------------------------------------------------

def test_compute_trend_negative_on_converging():
    # Strictly decreasing errors → slope must be negative
    errors = [0.5, 0.4, 0.3, 0.2, 0.1]
    slope = compute_trend(errors)
    assert slope < 0


def test_compute_trend_positive_on_diverging():
    errors = [0.1, 0.2, 0.3, 0.4, 0.5]
    slope = compute_trend(errors)
    assert slope > 0


def test_compute_trend_flat():
    errors = [0.3, 0.3, 0.3, 0.3]
    slope = compute_trend(errors)
    assert slope == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# 5. write_artifacts creates all three files
# ---------------------------------------------------------------------------

def test_write_artifacts_creates_files(tmp_path: Path):
    profile = StudentProfile(ability=0.7)
    sessions = [
        {"session_id": "sim-1", "session_number": 1, "difficulties": [0.5, 0.55, 0.6]},
        {"session_id": "sim-2", "session_number": 2, "difficulties": [0.55, 0.6, 0.65]},
    ]
    write_artifacts(
        sessions=sessions,
        profile=profile,
        output_dir=tmp_path / "artifacts",
        fixture_commit="abc1234",
        provider="stub",
        model="stub",
    )
    assert (tmp_path / "artifacts" / "trajectories.csv").exists()
    assert (tmp_path / "artifacts" / "run_summary.json").exists()
    assert (tmp_path / "artifacts" / "run_summary.md").exists()


def test_write_artifacts_csv_rows(tmp_path: Path):
    profile = StudentProfile(ability=0.7)
    sessions = [
        {"session_id": "sim-1", "session_number": 1, "difficulties": [0.5, 0.6]},
    ]
    out = tmp_path / "out"
    write_artifacts(
        sessions=sessions,
        profile=profile,
        output_dir=out,
        fixture_commit="abc1234",
        provider="stub",
        model="stub",
    )
    csv_text = (out / "trajectories.csv").read_text(encoding="utf-8")
    lines = [l for l in csv_text.splitlines() if l.strip()]
    # 1 header + 2 data rows
    assert len(lines) == 3


def test_write_artifacts_json_keys(tmp_path: Path):
    profile = StudentProfile(ability=0.7)
    sessions = [
        {"session_id": "sim-1", "session_number": 1, "difficulties": [0.5, 0.6, 0.65]},
    ]
    out = tmp_path / "out"
    write_artifacts(
        sessions=sessions,
        profile=profile,
        output_dir=out,
        fixture_commit="abc1234",
        provider="stub",
        model="stub",
    )
    summary = json.loads((out / "run_summary.json").read_text(encoding="utf-8"))
    assert "profile" in summary
    assert "num_sessions" in summary
    assert "mean_final_error" in summary
    assert "trend_slope" in summary
    assert "fixture_commit" in summary
    assert summary["fixture_commit"] == "abc1234"


# ---------------------------------------------------------------------------
# 6. Convergence criterion — actual 10 sessions × 5 questions with StubProvider
# ---------------------------------------------------------------------------

def test_convergence_criterion():
    """Run 10 sessions of 5 questions with StubProvider; assert trend_slope < 0.

    StubProvider always returns reward ≈ +0.17 (ok/yes/1-hint/3-turns/0-hedging),
    so difficulty monotonically climbs toward the 0.9 ceiling.  Setting
    ability=0.9 means the error from target strictly decreases every session
    as difficulty rises from 0.5 → 0.9, giving a guaranteed negative slope.
    """
    profile = StudentProfile(ability=0.9, seed=42)
    sessions = run_sessions(
        num_sessions=10,
        questions_per_session=5,
        profile=profile,
        provider_name="stub",
        model="stub",
    )
    assert len(sessions) == 10

    session_errors = [
        compute_session_error(s["difficulties"], profile.ability)
        for s in sessions
    ]
    trend_slope = compute_trend(session_errors)

    # With StubProvider and ability=0.9 the error monotonically shrinks across
    # sessions as difficulty saturates near 0.9.
    assert trend_slope < 0, (
        f"Expected negative trend_slope (convergence), got {trend_slope}. "
        f"Session errors: {session_errors}"
    )
