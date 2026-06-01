"""Tests for apore.fixtures.loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from apore.fixtures.loader import get_grounding_paths


def test_get_grounding_paths_missing_fixture_returns_empty(tmp_path: Path) -> None:
    """When .fixtures/ doesn't exist, returns [] gracefully."""
    result = get_grounding_paths("apore-lite", "set_theory_intro", program_root=tmp_path)
    assert result == []


def test_get_grounding_paths_with_wiki_files(tmp_path: Path) -> None:
    """Returns wiki HTML paths when fixture directory contains wiki files."""
    wiki_dir = tmp_path / ".fixtures" / "apore-lite" / "wiki"
    wiki_dir.mkdir(parents=True)
    (wiki_dir / "set_theory_intro.html").write_text("<html>sets</html>")
    (wiki_dir / "logic_basics.html").write_text("<html>logic</html>")

    result = get_grounding_paths("apore-lite", "set_theory_intro", program_root=tmp_path)

    assert len(result) == 1
    assert result[0].name == "set_theory_intro.html"


def test_get_grounding_paths_fallback_returns_all_wiki_files(tmp_path: Path) -> None:
    """When concept_id matches nothing, returns all wiki files as fallback."""
    wiki_dir = tmp_path / ".fixtures" / "apore-lite" / "wiki"
    wiki_dir.mkdir(parents=True)
    (wiki_dir / "set_theory_intro.html").write_text("<html>sets</html>")
    (wiki_dir / "logic_basics.html").write_text("<html>logic</html>")

    result = get_grounding_paths("apore-lite", "no_match_concept", program_root=tmp_path)

    assert len(result) == 2
