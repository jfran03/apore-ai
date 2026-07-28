import pytest

from apore.runtime.reward import QuestionSignals, compute_reward, update_difficulty


def test_reward_easy_correct_no_hints():
    s = QuestionSignals("easy", "yes", 0, 0, 2)
    r = compute_reward(s)
    assert r == pytest.approx(0.61, abs=1e-6)


def test_reward_withholds_zero_hint_bonus_when_assisted():
    unaided = QuestionSignals("easy", "yes", 0, 0, 2, assisted=False)
    assisted = QuestionSignals("easy", "yes", 0, 0, 2, assisted=True)
    assert compute_reward(assisted) < compute_reward(unaided)
    # Same as dropping the 0.2 * 0.2 = 0.04 hint bonus.
    assert compute_reward(assisted) == pytest.approx(0.57, abs=1e-6)


def test_reward_assisted_does_not_change_hint_penalties():
    mid = QuestionSignals("ok", "yes", 1, 0, 2, assisted=True)
    high = QuestionSignals("ok", "yes", 4, 0, 2, assisted=True)
    assert compute_reward(mid) == pytest.approx(
        compute_reward(QuestionSignals("ok", "yes", 1, 0, 2)), abs=1e-6
    )
    assert compute_reward(high) == pytest.approx(
        compute_reward(QuestionSignals("ok", "yes", 4, 0, 2)), abs=1e-6
    )

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
