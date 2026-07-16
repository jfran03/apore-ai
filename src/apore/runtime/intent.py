"""Classify learner chat intent for turn routing."""

from __future__ import annotations

import re

# Explicit help phrases — default is answer attempt when none match.
_HELP_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bneed help\b", re.IGNORECASE),
    re.compile(r"\bhelp me\b", re.IGNORECASE),
    re.compile(r"\bgive me a hint\b", re.IGNORECASE),
    re.compile(r"\bcan you explain\b", re.IGNORECASE),
    re.compile(r"\bcould you explain\b", re.IGNORECASE),
    re.compile(r"\bwhat does .+ mean\b", re.IGNORECASE),
    re.compile(r"\bi['']m stuck\b", re.IGNORECASE),
    re.compile(r"\bi am stuck\b", re.IGNORECASE),
    re.compile(r"\bnot sure\b.+\?", re.IGNORECASE | re.DOTALL),
    re.compile(r"\bnot sure\b.+\bexplain\b", re.IGNORECASE | re.DOTALL),
)


def is_help_request(message: str) -> bool:
    """Return True when the learner explicitly asks for help or explanation."""
    text = (message or "").strip()
    if not text:
        return False
    return any(pattern.search(text) for pattern in _HELP_PATTERNS)
