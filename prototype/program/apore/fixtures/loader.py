"""Runtime fixture adapter — maps fixture name + concept ID to grounding paths."""

from __future__ import annotations

import json
from pathlib import Path


def load_manifest(manifest_path: Path) -> dict:
    """Load fixtures manifest JSON."""
    raw = manifest_path.read_text(encoding="utf-8")
    return json.loads(raw)


def get_grounding_paths(
    fixture_name: str,
    concept_id: str,
    program_root: Path | None = None,
) -> list[Path]:
    """Return wiki file paths for the concept from a fetched fixture.

    Performs substring match on stem for concept_id. Returns all wiki files if no match.
    Falls back gracefully if .fixtures/ doesn't exist.
    """
    # Falls back to __file__ traversal; pass program_root explicitly when using installed package
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
