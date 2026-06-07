"""Tests for parallel question bank generation."""

from __future__ import annotations

import shutil
from pathlib import Path

from apore.providers.stub import StubProvider
from apore.setup.question_bank import generate_question_bank

_PROGRAM = Path(__file__).resolve().parents[2]
_CHAPTER = _PROGRAM / "domains" / "_pytest" / "chapters" / "01-intro"


def test_parallel_generation_produces_full_bank(tmp_path: Path):
    chapter_root = tmp_path / "chapter"
    chapter_root.mkdir()
    for name in ("concept-graph.json", "question-bank.json"):
        src = _CHAPTER / name
        if src.is_file():
            (chapter_root / name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    wiki_src = _CHAPTER / "wiki"
    if wiki_src.is_dir():
        shutil.copytree(wiki_src, chapter_root / "wiki")

    summary = generate_question_bank(
        chapter_root,
        provider=StubProvider(),
        model="stub-model",
        program_root=_PROGRAM,
        knowledge_source="domain:_pytest/01-intro",
        max_workers=2,
        provider_factory=lambda: StubProvider(),
    )
    assert summary["concepts"] == 2
    assert summary["questions"] == 12
