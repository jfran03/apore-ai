"""Tests for parallel question bank generation."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from apore.providers.stub import StubProvider
from apore.runtime.question_bank import load_question_bank
from apore.knowledge.chapter import ChapterContext
from apore.setup.question_bank import generate_question_bank

_PROGRAM = Path(__file__).resolve().parents[2]
_CHAPTER = _PROGRAM / "domains" / "_pytest" / "chapters" / "01-intro"


def _seed_chapter(chapter_root: Path) -> None:
    chapter_root.mkdir()
    for name in ("concept-graph.json", "question-bank.json"):
        src = _CHAPTER / name
        if src.is_file():
            (chapter_root / name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    wiki_src = _CHAPTER / "wiki"
    if wiki_src.is_dir():
        shutil.copytree(wiki_src, chapter_root / "wiki")


def _generate(chapter_root: Path) -> dict:
    return generate_question_bank(
        chapter_root,
        provider=StubProvider(),
        model="stub-model",
        program_root=_PROGRAM,
        knowledge_source="domain:_pytest/01-intro",
        max_workers=2,
        provider_factory=lambda: StubProvider(),
    )


def test_parallel_generation_produces_full_bank(tmp_path: Path):
    chapter_root = tmp_path / "chapter"
    _seed_chapter(chapter_root)

    summary = _generate(chapter_root)
    assert summary["concepts"] == 2
    assert summary["questions"] == 12


def _bank_concept_sequence(chapter_root: Path) -> list[str]:
    bank = load_question_bank(
        ChapterContext(
            knowledge_source="",
            chapter_root=chapter_root,
            display_name="",
        )
    )
    assert bank is not None
    seen: list[str] = []
    for q in bank.questions:
        if q.concept_id not in seen:
            seen.append(q.concept_id)
    return seen


def test_generation_follows_default_depth_order(tmp_path: Path):
    chapter_root = tmp_path / "chapter"
    _seed_chapter(chapter_root)
    _generate(chapter_root)
    # sets_definition has depth 0, set_theory_intro depth 1.
    assert _bank_concept_sequence(chapter_root) == ["sets_definition", "set_theory_intro"]


def test_generation_follows_manual_teaching_order(tmp_path: Path):
    chapter_root = tmp_path / "chapter"
    _seed_chapter(chapter_root)
    graph_path = chapter_root / "concept-graph.json"
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    graph["teaching_order"] = ["set_theory_intro", "sets_definition"]
    graph_path.write_text(json.dumps(graph), encoding="utf-8")

    _generate(chapter_root)
    assert _bank_concept_sequence(chapter_root) == ["set_theory_intro", "sets_definition"]
