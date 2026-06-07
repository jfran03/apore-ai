"""Simulated student for headless session runs."""

from __future__ import annotations

import random
from dataclasses import dataclass, field


@dataclass
class StudentProfile:
    ability: float  # 0.1–0.9, the "true" target the system should converge to
    misconceptions: list[str] = field(default_factory=list)
    seed: int = 42


_HIGH_ABILITY_RESPONSES = [
    "I understand this concept well. The answer is straightforward.",
    "Based on my knowledge, the correct answer is clearly derived from the definition.",
    "I'm confident the answer follows directly from first principles.",
    "This is a fundamental result. The explanation is precise and complete.",
]

_LOW_ABILITY_RESPONSES = [
    "I'm not entirely sure, but I think the answer might be related to this topic.",
    "I'm confused about this. Could you provide a hint?",
    "I believe it has something to do with the concept, but I'm uncertain.",
    "I'm struggling with this one. My guess is it's connected to the basics.",
]


class SimulatedStudent:
    def __init__(self, profile: StudentProfile) -> None:
        self.profile = profile
        self._rng = random.Random(profile.seed)

    def respond(self, question_text: str) -> str:
        """Return a simulated learner response text.

        High ability (>= 0.6) → confident answer; low ability → uncertain answer.
        """
        if self.profile.ability >= 0.6:
            base = self._rng.choice(_HIGH_ABILITY_RESPONSES)
        else:
            base = self._rng.choice(_LOW_ABILITY_RESPONSES)

        if self.profile.misconceptions:
            misconception = self._rng.choice(self.profile.misconceptions)
            return f"{base} (Note: {misconception})"
        return base
