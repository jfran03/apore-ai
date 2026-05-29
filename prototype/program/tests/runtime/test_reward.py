import pytest

from apore.runtime.reward import QuestionSignals, compute_reward, update_difficulty


def test_reward_easy_correct_no_hints():
    s = QuestionSignals("easy", "yes", 0, 0, 2)
    r = compute_reward(s)
    assert r == pytest.approx(0.61, abs=1e-6)


def test_reward_hard_incorrect_many_hints():
    s = QuestionSignals("hard", "no", 4, 4, 8)
    r = compute_reward(s)
    assert -1.0 <= r <= 1.0
    assert r < 0


def test_reward_clamped_upper():
    s = QuestionSignals("easy", "yes", 0, 0, 1)
    assert compute_reward(s) <= 1.0


def test_update_difficulty_moves_toward_reward():
    assert update_difficulty(0.5, 1.0) == pytest.approx(0.6)
    assert update_difficulty(0.5, -1.0) == pytest.approx(0.4)


def test_update_difficulty_clamped():
    assert update_difficulty(0.89, 1.0) == 0.9
    assert update_difficulty(0.11, -1.0) == 0.1
