"""Runtime fixture adapter — maps fixture name + concept ID to grounding paths."""

from __future__ import annotations

from pathlib import Path


def get_grounding_paths(
    fixture_name: str,
    concept_id: str,
    program_root: Path | None = None,
) -> list[Path]:
    """Return wiki file paths for the concept from a fetched fixture.

    If no wiki file matches concept_id exactly, returns all wiki files (fallback).
    Falls back gracefully if .fixtures/ doesn't exist.
    """
    root = program_root if program_root is not None else Path(__file__).parent.parent.parent
    fixture_dir = root / ".fixtures" / fixture_name

    if not fixture_dir.exists():
        return []

    wiki_files = list(fixture_dir.glob("**/wiki/**/*.html"))
    if not wiki_files:
        wiki_files = list(fixture_dir.glob("**/*.html"))

    # Try to find files that match the concept_id
    matched = [p for p in wiki_files if concept_id in p.stem]
    return matched if matched else wiki_files
