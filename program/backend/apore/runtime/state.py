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


SESSION_STATUSES = ("active", "completed", "ended_early")


def _session_template(
    *,
    title: str,
    session_id: str,
    created_at: str,
    knowledge_source: str,
    focus_mode: str,
    max_questions: int,
    concept_ids: list[str] | None = None,
    status: str = "active",
    ended_at: str = "",
) -> str:
    concepts_line = ",".join(concept_ids or [])
    return (
        f"# {title}\n\n"
        f"## Session\n"
        f"id: {session_id}\n"
        f"created_at: {created_at}\n"
        f"knowledge_source: {knowledge_source}\n"
        f"focus_mode: {focus_mode}\n"
        f"max_questions: {max_questions}\n"
        f"concept_ids: {concepts_line}\n"
        f"status: {status}\n"
        f"ended_at: {ended_at}\n\n"
        f"## Scalar\n"
        f"0.5\n\n"
        f"## Mastery\n\n"
        f"## Asked Questions\n\n"
        f"## Question Log\n"
        f"| Q# | session | date | question_id | concept | question_type | intended_difficulty | explicit_rating | correct | assisted | hints | turns | hedging | reward_R | new_difficulty |\n"
        f"|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
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
    concept_ids: list[str] | None = None,
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
                concept_ids=concept_ids,
            ),
        )
        return
    _write_text(path, _LEGACY_TEMPLATE)


def parse_concept_ids(raw: str | None) -> list[str]:
    """Parse comma-separated concept ids from session metadata."""
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def read_title(path: Path) -> str:
    """Return the H1 title from the session markdown file."""
    text = _read_text(path)
    first = text.splitlines()[0].strip() if text else ""
    if first.startswith("# "):
        return first[2:].strip()
    return "Study Session"


def write_title(path: Path, title: str) -> None:
    """Replace the leading H1 title in-place."""
    cleaned = (title or "").strip() or "Study Session"
    if "\n" in cleaned:
        cleaned = cleaned.splitlines()[0].strip() or "Study Session"
    text = _read_text(path)
    lines = text.splitlines(keepends=True)
    if lines and lines[0].lstrip().startswith("# "):
        newline = "\n" if lines[0].endswith("\n") else ""
        lines[0] = f"# {cleaned}{newline}"
        _write_text(path, "".join(lines))
        return
    _write_text(path, f"# {cleaned}\n\n{text}")


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
    # Legacy files created before lifecycle fields: treat as still active.
    if "status" not in result or result["status"] not in SESSION_STATUSES:
        result["status"] = "active"
    if "ended_at" not in result:
        result["ended_at"] = ""
    return result


def write_session_status(
    path: Path,
    *,
    status: str,
    ended_at: str | None = None,
) -> None:
    """Set `status` (and optional `ended_at`) under `## Session`.

    Creates missing keys for legacy session files that lack lifecycle fields.
    """
    if status not in SESSION_STATUSES:
        raise ValueError(f"status must be one of {SESSION_STATUSES}, got {status!r}")
    text = _read_text(path)
    m = re.search(r"## Session\s*\n(.*?)(?=\n## [^\n]+\n|\Z)", text, re.DOTALL)
    if not m:
        raise ValueError("Session section not found in learner-state.md")
    block = m.group(1)

    def _set_key(src: str, key: str, value: str) -> str:
        # Use [ \t]* (not \s*) so we do not consume the line ending.
        pattern = re.compile(rf"(?m)^({re.escape(key)}:[ \t]*)(.*)$")
        if pattern.search(src):
            return pattern.sub(lambda mm: mm.group(1) + value, src, count=1)
        trimmed = src.rstrip("\n")
        suffix = "\n" if src.endswith("\n") else ""
        return f"{trimmed}\n{key}: {value}\n{suffix}"

    updated_block = _set_key(block, "status", status)
    if ended_at is not None:
        updated_block = _set_key(updated_block, "ended_at", ended_at)
    updated = text[: m.start(1)] + updated_block + text[m.end(1) :]
    _write_text(path, updated)


def rewrite_knowledge_source(path: Path, old: str, new: str) -> bool:
    """Replace `knowledge_source` under `## Session` when it exactly matches `old`.

    Returns True when the file was updated.
    """
    if old == new:
        return False
    text = _read_text(path)
    m = re.search(r"## Session\s*\n(.*?)(?=\n## [^\n]+\n|\Z)", text, re.DOTALL)
    if not m:
        return False
    block = m.group(1)
    pattern = re.compile(r"(?m)^(knowledge_source:\s*)(.*)$")
    match = pattern.search(block)
    if not match or match.group(2).strip() != old:
        return False
    updated_block = pattern.sub(
        lambda mm: mm.group(1) + new if mm.group(2).strip() == old else mm.group(0),
        block,
        count=1,
    )
    updated = text[: m.start(1)] + updated_block + text[m.end(1) :]
    _write_text(path, updated)
    return True


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


def _question_log_header(text: str) -> tuple[re.Match[str], list[str]]:
    """Locate the Question Log header/separator and return (match, columns)."""
    header_match = re.search(
        r"\| Q# \|.*?\|.*?\n\|[-| ]+\|",
        text,
    )
    if not header_match:
        raise ValueError("Question Log table header not found in learner-state.md")
    header_line = header_match.group(0).split("\n")[0]
    columns = [c.strip() for c in header_line.strip("|").split("|")]
    return header_match, columns


def parse_question_log(path: Path) -> list[dict[str, str]]:
    """Parse data rows from the `## Question Log` table.

    Returns one dict per data row keyed by header column name. Skips the
    separator and any malformed lines whose cell count does not match the
    header. Empty logs (header only) return ``[]``.
    """
    text = _read_text(path)
    try:
        header_match, columns = _question_log_header(text)
    except ValueError:
        return []

    rows: list[dict[str, str]] = []
    for line in text[header_match.end() :].splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("## "):
            break
        if not stripped.startswith("|"):
            continue
        if re.match(r"^\|[-| :]+\|$", stripped):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) != len(columns):
            continue
        rows.append(dict(zip(columns, cells)))
    return rows


def append_log_row(path: Path, row: dict[str, Any]) -> None:
    """Append one row to the `## Question Log` table.

    The `row` dict must supply values for every column header found in the
    table. Missing keys default to empty string.
    """
    text = _read_text(path)
    _, columns = _question_log_header(text)

    values = [str(row.get(col, "")) for col in columns]
    new_row = "| " + " | ".join(values) + " |"

    # Append after the last table row (or after the separator if no data rows)
    _write_text(path, text.rstrip("\n") + "\n" + new_row + "\n")
