"""Learner-state I/O for `learner-state.md` (PRD §11)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Default template
# ---------------------------------------------------------------------------

_LEGACY_TEMPLATE = """\
# Learner State

## Scalar
0.5

## Mastery

## Asked Questions

## Question Log
| Q# | session | date | question_id | concept | question_type | intended_difficulty | explicit_rating | correct | hints | turns | hedging | reward_R | new_difficulty |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
"""


def _session_template(
    *,
    title: str,
    session_id: str,
    created_at: str,
    knowledge_source: str,
    focus_mode: str,
    max_questions: int,
) -> str:
    return (
        f"# {title}\n\n"
        f"## Session\n"
        f"id: {session_id}\n"
        f"created_at: {created_at}\n"
        f"knowledge_source: {knowledge_source}\n"
        f"focus_mode: {focus_mode}\n"
        f"max_questions: {max_questions}\n\n"
        f"## Scalar\n"
        f"0.5\n\n"
        f"## Mastery\n\n"
        f"## Asked Questions\n\n"
        f"## Question Log\n"
        f"| Q# | session | date | question_id | concept | question_type | intended_difficulty | explicit_rating | correct | hints | turns | hedging | reward_R | new_difficulty |\n"
        f"|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
    )


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

def initialize(
    path: Path,
    *,
    title: str | None = None,
    session_id: str | None = None,
    created_at: str | None = None,
    knowledge_source: str | None = None,
    focus_mode: str | None = None,
    max_questions: int | None = None,
) -> None:
    """Create a fresh learner-state.md with default values."""
    if session_id and created_at and knowledge_source and focus_mode is not None and max_questions is not None:
        _write_text(
            path,
            _session_template(
                title=title or "Study Session",
                session_id=session_id,
                created_at=created_at,
                knowledge_source=knowledge_source,
                focus_mode=focus_mode,
                max_questions=max_questions,
            ),
        )
        return
    _write_text(path, _LEGACY_TEMPLATE)


def read_title(path: Path) -> str:
    """Return the H1 title from the session markdown file."""
    text = _read_text(path)
    first = text.splitlines()[0].strip() if text else ""
    if first.startswith("# "):
        return first[2:].strip()
    return "Study Session"


def read_session_meta(path: Path) -> dict[str, str]:
    """Parse key-value lines under `## Session`."""
    text = _read_text(path)
    m = re.search(r"## Session\s*\n(.*?)(?=\n## [^\n]+\n|\Z)", text, re.DOTALL)
    if not m:
        return {}
    result: dict[str, str] = {}
    for line in m.group(1).splitlines():
        line = line.strip()
        if ":" in line:
            key, _, val = line.partition(":")
            result[key.strip()] = val.strip()
    return result


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
    m = re.search(r"## Mastery\s*\n(.*?)(?=\n## [^\n]+\n|\Z)", text, re.DOTALL)
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


def read_asked_ids(path: Path) -> set[str]:
    """Return question bank ids already served in this session."""
    text = _read_text(path)
    result: set[str] = set()
    in_section = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "## Asked Questions":
            in_section = True
            continue
        if in_section and stripped.startswith("## "):
            break
        if in_section and stripped and not stripped.startswith("|"):
            result.add(stripped)
    return result


def append_asked_id(path: Path, question_id: str) -> None:
    """Append one served question bank id under ## Asked Questions."""
    text = _read_text(path)
    if "## Asked Questions" not in text:
        raise ValueError("Asked Questions section not found in learner-state.md")
    block_match = re.search(r"(## Asked Questions\s*\n)(.*?)(?=\n## )", text, re.DOTALL)
    if not block_match:
        block_match = re.search(r"(## Asked Questions\s*\n)(.*)", text, re.DOTALL)
    if not block_match:
        raise ValueError("Asked Questions section not found in learner-state.md")
    prefix, block = block_match.group(1), block_match.group(2)
    existing = {ln.strip() for ln in block.splitlines() if ln.strip()}
    if question_id in existing:
        return
    new_block = (block.rstrip() + "\n" + question_id + "\n") if block.strip() else (question_id + "\n")
    updated = text[: block_match.start()] + prefix + new_block + text[block_match.end() :]
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
