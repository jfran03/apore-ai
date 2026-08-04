"""Regression checks for scratchpad protocol silent-visual guidance."""

from __future__ import annotations

from pathlib import Path

import pytest

PROGRAM_ROOT = Path(__file__).resolve().parents[2]
PROTOCOLS = PROGRAM_ROOT / "shared" / "protocols"

SCRATCHPAD_PROTOCOLS = ("scratchpad-ask.md", "scratchpad-grade.md")

# Phrases the model must be told not to surface to the learner.
SILENT_TRANSPORT_MARKERS = (
    "Never announce, mention, or acknowledge an image, attachment, selection, crop, or screenshot",
    "do not acknowledge the attachment itself in your reply",
)

# Natural references that remain allowed.
NATURAL_WORK_MARKERS = (
    "your second line",
    "the circled term",
)


@pytest.mark.parametrize("filename", SCRATCHPAD_PROTOCOLS)
def test_scratchpad_protocols_require_silent_visual_context(filename: str) -> None:
    text = (PROTOCOLS / filename).read_text(encoding="utf-8")
    for marker in SILENT_TRANSPORT_MARKERS:
        assert marker in text, f"{filename} missing silent-visual rule: {marker!r}"
    for marker in NATURAL_WORK_MARKERS:
        assert marker in text, f"{filename} missing natural-work example: {marker!r}"
    assert "Use the work silently." in text
