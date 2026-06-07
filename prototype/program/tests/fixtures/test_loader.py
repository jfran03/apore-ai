"""Tests for apore.fixtures.loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from apore.fixtures.loader import get_grounding_paths


def test_get_grounding_paths_missing_domain_returns_empty(tmp_path: Path) -> None:
    """When discrete-math domain is not synced, returns [] gracefully."""
    result = get_grounding_paths("apore-lite", "set_theory_intro", program_root=tmp_path)
    assert result == []


def test_get_grounding_paths_with_wiki_files(tmp_path: Path) -> None:
    """Returns wiki paths when synced domain chapter contains wiki files."""
    wiki_dir = (
        tmp_path
        / "domains"
        / "discrete-math"
        / "chapters"
        / "01-set-theory"
        / "wiki"
    )
    wiki_dir.mkdir(parents=True)
    (wiki_dir / "set_theory_intro.md").write_text("# Sets\n", encoding="utf-8")
    (wiki_dir / "logic_basics.md").write_text("# Logic\n", encoding="utf-8")
    (wiki_dir.parent / "concept-graph.json").write_text(
        '{"nodes":[{"id":"set_theory_intro","label":"Sets","depth":0},'
        '{"id":"logic_basics","label":"Logic","depth":0}],"edges":[]}\n',
        encoding="utf-8",
    )

    result = get_grounding_paths("apore-lite", "set_theory_intro", program_root=tmp_path)

    assert len(result) == 1
    assert result[0].name == "set_theory_intro.md"


def test_get_grounding_paths_unknown_concept_returns_empty(tmp_path: Path) -> None:
    """Unknown concept with no graph neighbors yields no wiki paths."""
    wiki_dir = (
        tmp_path
        / "domains"
        / "discrete-math"
        / "chapters"
        / "01-set-theory"
        / "wiki"
    )
    wiki_dir.mkdir(parents=True)
    (wiki_dir / "set_theory_intro.md").write_text("# Sets\n", encoding="utf-8")
    (wiki_dir / "logic_basics.md").write_text("# Logic\n", encoding="utf-8")
    (wiki_dir.parent / "concept-graph.json").write_text(
        '{"nodes":[{"id":"set_theory_intro","label":"Sets","depth":0},'
        '{"id":"logic_basics","label":"Logic","depth":0}],'
        '"edges":[{"source":"set_theory_intro","target":"logic_basics",'
        '"relation":"prerequisite_of"}]}\n',
        encoding="utf-8",
    )

    result = get_grounding_paths("apore-lite", "no_match_concept", program_root=tmp_path)

    assert result == []
