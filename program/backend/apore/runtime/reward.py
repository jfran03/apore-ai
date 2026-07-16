"""Deterministic reward and difficulty update (PRD §7). Runtime-owned only."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Rating = Literal["easy", "ok", "hard"]
Correct = Literal["yes", "no"]


@dataclass(frozen=True)
class QuestionSignals:
    explicit_rating: Rating
    correct: Correct
    hint_count: int
    hedging_count: int
    turn_count: int


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def explicit_rating_score(rating: Rating) -> float:
    return {"easy": 1.0, "ok": 0.0, "hard": -1.0}[rating]


def correct_score(correct: Correct) -> float:
    return {"yes": 0.5, "no": -0.5}[correct]


def hint_score(hint_count: int) -> float:
    if hint_count == 0:
        return 0.2
    if hint_count <= 2:
        return 0.0
    return -0.2


def hedging_score(hedging_count: int) -> float:
    if hedging_count == 0:
        return 0.1
    if hedging_count <= 2:
        return 0.0
    return -0.1


def turn_score(turn_count: int) -> float:
    if turn_count <= 3:
        return 0.1
    if turn_count <= 6:
        return 0.0
    return -0.1


def implicit_score(signals: QuestionSignals) -> float:
    return hedging_score(signals.hedging_count) + turn_score(signals.turn_count)


def compute_reward(signals: QuestionSignals) -> float:
    """R = 0.4·rating + 0.3·correct + 0.2·hint + 0.1·implicit, clamped [-1, 1]."""
    r = (
        0.4 * explicit_rating_score(signals.explicit_rating)
        + 0.3 * correct_score(signals.correct)
        + 0.2 * hint_score(signals.hint_count)
        + 0.1 * implicit_score(signals)
    )
    return _clamp(r, -1.0, 1.0)


def update_difficulty(
    current: float,
    reward: float,
    *,
    alpha: float = 0.1,
    low: float = 0.1,
    high: float = 0.9,
) -> float:
    return _clamp(current + alpha * reward, low, high)
