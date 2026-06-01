"""Deterministic stub provider for testing."""

import json

from apore.providers.base import Provider

_QUESTION_BLOCK = """\
CONCEPT: set_theory_intro
TYPE: recall
INTENDED_DIFFICULTY: 0.5

What is the difference between a set and a multiset? [Source: set_theory_intro — Introduction]\
"""

_SIGNALS = {
    "explicit_rating": "ok",
    "correct": "yes",
    "hint_count": 1,
    "turn_count": 3,
    "hedging_count": 0,
}


class StubProvider(Provider):
    """Returns canned responses without making any network calls.

    Detection logic: if the word "extract-signals" appears anywhere in the
    combined system+messages content, return signals JSON; otherwise return a
    question block.

    Optional config key ``seed`` is accepted but currently unused. ``seed`` key in config is currently ignored.
    """

    def invoke(
        self,
        system_prompt: str,
        messages: list[dict],
        model: str,
        config: dict,
    ) -> str:
        combined = system_prompt + " ".join(m.get("content", "") for m in messages)
        if "extract-signals" in combined:
            return json.dumps(_SIGNALS)
        return _QUESTION_BLOCK
