"""Tests for extract-signals JSON parsing."""

from __future__ import annotations

import json

import pytest

from apore.runtime.core import _parse_signals


def test_parse_signals_plain_json():
    raw = json.dumps(
        {
            "explicit_rating": "ok",
            "correct": "yes",
            "hint_count": 2,
            "turn_count": 1,
            "hedging_count": 0,
        }
    )
    signals = _parse_signals(raw)
    assert signals["correct"] == "yes"
    assert signals["hint_count"] == 2


def test_parse_signals_json_in_fenced_block():
    inner = json.dumps({"explicit_rating": "hard", "correct": "no", "hint_count": 0, "turn_count": 1, "hedging_count": 1})
    raw = f"```json\n{inner}\n```"
    signals = _parse_signals(raw)
    assert signals["explicit_rating"] == "hard"
    assert signals["correct"] == "no"


def test_parse_signals_json_embedded_in_prose():
    payload = (
        '{"explicit_rating": "ok", "correct": "yes", "hint_count": 1, '
        '"turn_count": 2, "hedging_count": 0}'
    )
    raw = f"Yes, exactly — good answer.\n\n{payload}"
    signals = _parse_signals(raw)
    assert signals["correct"] == "yes"
    assert signals["turn_count"] == 2


def test_parse_signals_teacher_prose_returns_defaults():
    raw = (
        "Consider set operations. Think about how sets can be combined. "
        "[Source: set_operations — Introduction]"
    )
    signals = _parse_signals(raw)
    assert signals == {
        "explicit_rating": "ok",
        "correct": "no",
        "hint_count": 0,
        "turn_count": 0,
        "hedging_count": 0,
    }


def test_parse_signals_empty_returns_defaults():
    assert _parse_signals("") == {
        "explicit_rating": "ok",
        "correct": "no",
        "hint_count": 0,
        "turn_count": 0,
        "hedging_count": 0,
    }
