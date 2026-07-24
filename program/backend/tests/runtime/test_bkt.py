"""Unit tests for Bayesian Knowledge Tracing (PROGRESSION.md P0)."""

from __future__ import annotations

import pytest

from apore.runtime.bkt import (
    DEFAULT_PARAMS,
    band_for,
    display_pct_for,
    replay,
    update_step,
)


def test_defaults_match_progression():
    assert DEFAULT_PARAMS.p_L0 == 0.0
    assert DEFAULT_PARAMS.p_T == 0.1
    assert DEFAULT_PARAMS.p_G == 0.2
    assert DEFAULT_PARAMS.p_S == 0.1
    assert DEFAULT_PARAMS.p_F == 0.0


def test_empty_replay_is_new():
    m = replay([])
    assert m.p_mastery is None
    assert m.band == "new"
    assert m.n_observed == 0
    assert m.display_pct is None


def test_first_correct_from_cold_start():
    # p=0, correct → posterior 0, then learn → P(T)=0.1
    p = update_step(0.0, 1)
    assert p == pytest.approx(0.1)
    m = replay([1])
    assert m.p_mastery == pytest.approx(0.1)
    assert m.band == "struggling"
    assert m.display_pct == 10


def test_three_correct_reaches_proficient():
    # Hand-checked with defaults: after 3 corrects P(L) ≈ 0.775
    m = replay([1, 1, 1])
    assert m.p_mastery == pytest.approx(0.775)
    assert m.band == "proficient"
    assert m.n_observed == 3
    assert m.display_pct == 78


def test_incorrect_softens_progress():
    after_correct = update_step(0.0, 1)
    after_wrong = update_step(after_correct, 0)
    assert after_wrong < 0.3
    assert band_for(after_wrong, 2) == "struggling"


def test_bands_and_display():
    assert band_for(None, 0) == "new"
    assert band_for(0.0, 0) == "new"
    assert band_for(0.1, 1) == "struggling"
    assert band_for(0.3, 2) == "learning"
    assert band_for(0.69, 5) == "learning"
    assert band_for(0.7, 5) == "proficient"
    assert display_pct_for(0.824, 3) == 82
    assert display_pct_for(None, 0) is None


def test_obs_must_be_binary():
    with pytest.raises(ValueError):
        update_step(0.5, 2)
