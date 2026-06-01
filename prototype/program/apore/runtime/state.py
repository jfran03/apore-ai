"""Learner-state I/O for `learner-state.md` (PRD §11)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Default template
# ---------------------------------------------------------------------------

_TEMPLATE = """\
# Learner State

## Scalar
0.5

## Mastery

## Question Log
| Q# | session | date | concept | question_type | intended_difficulty | explicit_rating | correct | hints | turns | hedging | reward_R | new_difficulty |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def initialize(path: Path) -> None:
    """Create a fresh learner-state.md with default values."""
    _write_text(path, _TEMPLATE)


def read_scalar(path: Path) -> float:
    """Return the float stored under `## Scalar`."""
    text = _read_text(path)
    m = re.search(r"## Scalar\s*\n\s*([0-9.eE+\-]+)", text)
    if not m:
        raise ValueError("Scalar section not found in learner-state.md")
    return float(m.group(1))


def write_scalar(path: Path, value: float) -> None:
    """Replace the float under `## Scalar` in-place, clamped to [0.1, 0.9]."""
    value = max(0.1, min(0.9, value))
    text = _read_text(path)
    updated = re.sub(
        r"(## Scalar\s*\n)\s*[0-9.eE+\-]+",
        lambda m: m.group(1) + str(value),
        text,
        count=1,
    )
    _write_text(path, updated)


def read_mastery(path: Path) -> dict[str, float]:
    """Return `{concept: float}` from the `## Mastery` section."""
    text = _read_text(path)
    m = re.search(r"## Mastery\s*\n(.*?)(?=\n##|\Z)", text, re.DOTALL)
    if not m:
        return {}
    block = m.group(1)
    result: dict[str, float] = {}
    for line in block.splitlines():
        line = line.strip()
        if ":" in line:
            concept, _, val = line.partition(":")
            try:
                result[concept.strip()] = float(val.strip())
            except ValueError:
                pass
    return result


def write_mastery(path: Path, mastery: dict[str, float]) -> None:
    """Replace the `## Mastery` block in-place."""
    text = _read_text(path)
    block_lines = "\n".join(f"{k}: {v}" for k, v in mastery.items())
    new_block = block_lines + "\n" if block_lines else ""

    # Split on section boundaries so we don't consume adjacent sections.
    # Replace only the content between "## Mastery\n" and the next "## " heading.
    updated = re.sub(
        r"(?m)^(## Mastery\n)([^#]|\#(?!\#))*",
        lambda m: m.group(1) + new_block + "\n",
        text,
        count=1,
    )
    _write_text(path, updated)


def append_log_row(path: Path, row: dict[str, Any]) -> None:
    """Append one row to the `## Question Log` table.

    The `row` dict must supply values for every column header found in the
    table. Missing keys default to empty string.
    """
    text = _read_text(path)

    # Find the header row to determine column order
    header_match = re.search(
        r"\| Q# \|.*?\|.*?\n\|[-| ]+\|",
        text,
    )
    if not header_match:
        raise ValueError("Question Log table header not found in learner-state.md")

    header_line = header_match.group(0).split("\n")[0]
    columns = [c.strip() for c in header_line.strip("|").split("|")]

    values = [str(row.get(col, "")) for col in columns]
    new_row = "| " + " | ".join(values) + " |"

    # Append after the last table row (or after the separator if no data rows)
    _write_text(path, text.rstrip("\n") + "\n" + new_row + "\n")
