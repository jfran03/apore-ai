"""Tests for question bank load, validate, and selection."""

from __future__ import annotations

from pathlib import Path

import pytest

from apore.knowledge.chapter import ChapterContext, load_concept_graph
from apore.runtime.question_bank import (
    QuestionBank,
    QuestionBankExhaustedError,
    BankQuestion,
    load_question_bank,
    select_question,
    type_for_scalar,
    validate_question_bank,
)

_PROGRAM = Path(__file__).resolve().parents[2]
_CHAPTER = _PROGRAM / "domains" / "_pytest" / "chapters" / "01-intro"
_DM_CHAPTER = _PROGRAM / "domains" / "discrete-math" / "chapters" / "01-set-theory"


def _chapter() -> ChapterContext:
    return ChapterContext(
        knowledge_source="domain:_pytest/01-intro",
        chapter_root=_CHAPTER,
        display_name="pytest",
    )


def _discrete_math_chapter() -> ChapterContext:
    return ChapterContext(
        knowledge_source="domain:discrete-math/01-set-theory",
        chapter_root=_DM_CHAPTER,
        display_name="discrete-math",
    )


def test_type_for_scalar_bands():
    assert type_for_scalar(0.2) == "recall"
    assert type_for_scalar(0.5) == "apply"
    assert type_for_scalar(0.8) == "synthesis"


def test_load_pytest_bank():
    bank = load_question_bank(_chapter())
    assert bank is not None
    assert len(bank.questions) >= 6


def test_validate_bank_ok():
    chapter = _chapter()
    bank = load_question_bank(chapter)
    graph = load_concept_graph(chapter)
    assert bank is not None
    assert validate_question_bank(bank, graph) == []


def test_select_no_consecutive_same_concept():
    chapter = _chapter()
    bank = load_question_bank(chapter)
    assert bank is not None
    graph = load_concept_graph(chapter)

    first = select_question(
        bank=bank,
        graph=graph,
        concept_id=None,
        scalar=0.5,
        asked_ids=set(),
        question_number=4,
    )
    assert first.type == "apply"

    second = select_question(
        bank=bank,
        graph=graph,
        concept_id=None,
        scalar=0.5,
        asked_ids={first.id},
        question_number=5,
        last_concept_id=first.concept_id,
    )
    assert second.concept_id != first.concept_id


def test_select_exhausted_when_no_matching_weak_concept_questions():
    chapter = _chapter()
    graph = load_concept_graph(chapter)
    concept_ids = sorted(graph.nodes.keys())
    weak_id = concept_ids[0]
    strong_id = concept_ids[1]
    bank = QuestionBank(
        version=1,
        questions=[
            BankQuestion(
                id="only-recall-01",
                concept_id=strong_id,
                type="recall",
                intended_difficulty=0.25,
                text="Only on strong concept.",
            )
        ],
    )
    mastery = {weak_id: 0.2, strong_id: 0.9}

    with pytest.raises(QuestionBankExhaustedError):
        select_question(
            bank=bank,
            graph=graph,
            concept_id=None,
            scalar=0.5,
            asked_ids=set(),
            question_number=1,
            mastery=mastery,
            focus_mode="weak_points",
        )


def test_select_allows_question_reuse():
    chapter = _chapter()
    bank = load_question_bank(chapter)
    assert bank is not None
    graph = load_concept_graph(chapter)

    asked: set[str] = set()
    last_concept: str | None = None
    assert len(bank.questions) < 14
    for n in range(1, 15):
        picked = select_question(
            bank=bank,
            graph=graph,
            concept_id=None,
            scalar=0.5,
            asked_ids=asked,
            question_number=n,
            last_concept_id=last_concept,
        )
        asked.add(picked.id)
        last_concept = picked.concept_id

    # Completed more picks than unique bank entries without exhausting.


def test_select_skips_last_concept():
    chapter = _chapter()
    bank = load_question_bank(chapter)
    assert bank is not None
    graph = load_concept_graph(chapter)

    picked = select_question(
        bank=bank,
        graph=graph,
        concept_id=None,
        scalar=0.5,
        asked_ids=set(),
        question_number=4,
        last_concept_id="sets_definition",
    )
    assert picked.concept_id != "sets_definition"


def test_discrete_math_bank_selects_q1():
    chapter = _discrete_math_chapter()
    bank = load_question_bank(chapter)
    graph = load_concept_graph(chapter)
    assert bank is not None
    assert validate_question_bank(bank, graph) == []

    picked = select_question(
        bank=bank,
        graph=graph,
        concept_id=None,
        scalar=0.5,
        asked_ids=set(),
        question_number=1,
        last_concept_id=None,
    )
    assert picked.concept_id in graph.nodes


def test_scalar_still_drives_type():
    chapter = _chapter()
    bank = load_question_bank(chapter)
    assert bank is not None
    graph = load_concept_graph(chapter)

    picked = select_question(
        bank=bank,
        graph=graph,
        concept_id="sets_definition",
        scalar=0.5,
        asked_ids=set(),
        question_number=4,
        last_concept_id=None,
    )
    assert picked.type == "apply"


def test_burst_type_unchanged_with_cooldown():
    chapter = _chapter()
    bank = load_question_bank(chapter)
    assert bank is not None
    graph = load_concept_graph(chapter)

    first = select_question(
        bank=bank,
        graph=graph,
        concept_id=None,
        scalar=0.5,
        asked_ids=set(),
        question_number=1,
        last_concept_id=None,
    )
    second = select_question(
        bank=bank,
        graph=graph,
        concept_id=None,
        scalar=0.5,
        asked_ids={first.id},
        question_number=2,
        last_concept_id=first.concept_id,
    )
    assert second.type == "apply"


def test_weak_points_selects_from_low_mastery_pool():
    chapter = _chapter()
    bank = load_question_bank(chapter)
    assert bank is not None
    graph = load_concept_graph(chapter)
    concept_ids = sorted(graph.nodes.keys())
    mastery = {cid: 0.9 for cid in concept_ids}
    weak_id = concept_ids[0]
    mastery[weak_id] = 0.2

    picked = select_question(
        bank=bank,
        graph=graph,
        concept_id=None,
        scalar=0.5,
        asked_ids=set(),
        question_number=1,
        mastery=mastery,
        focus_mode="weak_points",
    )
    assert picked.concept_id == weak_id


def test_weak_points_exhausted_when_no_weak_concepts():
    chapter = _chapter()
    bank = load_question_bank(chapter)
    assert bank is not None
    graph = load_concept_graph(chapter)
    mastery = {cid: 0.9 for cid in graph.nodes.keys()}

    with pytest.raises(QuestionBankExhaustedError, match="No weak concepts"):
        select_question(
            bank=bank,
            graph=graph,
            concept_id=None,
            scalar=0.5,
            asked_ids=set(),
            question_number=1,
            mastery=mastery,
            focus_mode="weak_points",
        )


def test_select_respects_allowed_concept_subset():
    chapter = _chapter()
    bank = load_question_bank(chapter)
    assert bank is not None
    graph = load_concept_graph(chapter)
    allowed = {"set_theory_intro"}

    for n in range(1, 6):
        picked = select_question(
            bank=bank,
            graph=graph,
            concept_id=None,
            scalar=0.5,
            asked_ids=set(),
            question_number=n,
            allowed_concept_ids=allowed,
        )
        assert picked.concept_id == "set_theory_intro"


def test_select_single_concept_allows_reuse_across_questions():
    chapter = _chapter()
    bank = load_question_bank(chapter)
    assert bank is not None
    graph = load_concept_graph(chapter)
    allowed = {"sets_definition"}
    asked: set[str] = set()
    last: str | None = None

    for n in range(1, 10):
        picked = select_question(
            bank=bank,
            graph=graph,
            concept_id=None,
            scalar=0.5,
            asked_ids=asked,
            question_number=n,
            last_concept_id=last,
            allowed_concept_ids=allowed,
        )
        assert picked.concept_id == "sets_definition"
        asked.add(picked.id)
        last = picked.concept_id


def test_select_empty_allowed_set_exhausted():
    chapter = _chapter()
    bank = load_question_bank(chapter)
    assert bank is not None
    graph = load_concept_graph(chapter)

    with pytest.raises(QuestionBankExhaustedError, match="No concepts selected"):
        select_question(
            bank=bank,
            graph=graph,
            concept_id=None,
            scalar=0.5,
            asked_ids=set(),
            question_number=1,
            allowed_concept_ids=set(),
        )


def test_weak_points_respects_allowed_subset():
    chapter = _chapter()
    bank = load_question_bank(chapter)
    assert bank is not None
    graph = load_concept_graph(chapter)
    mastery = {"sets_definition": 0.2, "set_theory_intro": 0.2}

    picked = select_question(
        bank=bank,
        graph=graph,
        concept_id=None,
        scalar=0.5,
        asked_ids=set(),
        question_number=1,
        mastery=mastery,
        focus_mode="weak_points",
        allowed_concept_ids={"set_theory_intro"},
    )
    assert picked.concept_id == "set_theory_intro"


def test_validate_rejects_unknown_concept():
    chapter = _chapter()
    graph = load_concept_graph(chapter)
    bank = QuestionBank(
        version=1,
        questions=[
            BankQuestion(
                id="bad-recall-01",
                concept_id="nonexistent",
                type="recall",
                intended_difficulty=0.25,
                text="?",
            )
        ],
    )
    errors = validate_question_bank(bank, graph)
    assert any("unknown concept" in e for e in errors)


def test_scratchpad_selects_only_eligible_questions():
    chapter = _chapter()
    bank = load_question_bank(chapter)
    assert bank is not None
    graph = load_concept_graph(chapter)
    assert any(q.scratchpad_eligible for q in bank.questions)
    assert any(not q.scratchpad_eligible for q in bank.questions)

    asked: set[str] = set()
    last: str | None = None
    for n in range(1, 8):
        picked = select_question(
            bank=bank,
            graph=graph,
            concept_id=None,
            scalar=0.5,
            asked_ids=asked,
            question_number=n,
            last_concept_id=last,
            study_mode="scratchpad",
        )
        assert picked.scratchpad_eligible is True
        asked.add(picked.id)
        last = picked.concept_id


def test_scratchpad_exhausted_when_no_eligible_questions():
    chapter = _chapter()
    graph = load_concept_graph(chapter)
    bank = QuestionBank(
        version=1,
        questions=[
            BankQuestion(
                id="conceptual-only-01",
                concept_id="sets_definition",
                type="recall",
                intended_difficulty=0.25,
                text="Explain what a set is.",
                scratchpad_eligible=False,
            )
        ],
    )
    with pytest.raises(QuestionBankExhaustedError, match="scratchpad-eligible"):
        select_question(
            bank=bank,
            graph=graph,
            concept_id=None,
            scalar=0.5,
            asked_ids=set(),
            question_number=1,
            study_mode="scratchpad",
        )


def test_chat_mode_can_select_ineligible_questions():
    chapter = _chapter()
    bank = load_question_bank(chapter)
    assert bank is not None
    graph = load_concept_graph(chapter)
    picked = select_question(
        bank=bank,
        graph=graph,
        concept_id="sets_definition",
        scalar=0.2,
        asked_ids=set(),
        question_number=4,
        study_mode="chat",
    )
    assert picked.type == "recall"
    assert picked.scratchpad_eligible is False
