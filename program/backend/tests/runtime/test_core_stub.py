"""Tests for apore.runtime.core.run_question_cycle using StubProvider."""

from __future__ import annotations

import pytest
from pathlib import Path

from apore.knowledge.chapter import resolve_chapter
from apore.providers.stub import StubProvider
from apore.runtime import state
from apore.runtime.core import (
    AssessmentResult,
    GeneratedQuestion,
    QuestionResult,
    finalize_turn,
    generate_question,
    parse_feedback_regions,
    parse_grade_answer_response,
    run_question_cycle,
    _parse_question_block,
)

_PROGRAM_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Unit tests for parsing functions
# ---------------------------------------------------------------------------

def test_parse_question_block_direct():
    """Test _parse_question_block with a hardcoded string input."""
    raw = "CONCEPT: my_concept\nTYPE: apply\nINTENDED_DIFFICULTY: 0.7\n\nExplain X. [Source: foo]"
    concept, qtype, difficulty, text = _parse_question_block(raw)
    assert concept == "my_concept"
    assert qtype == "apply"
    assert difficulty == pytest.approx(0.7)
    assert "Explain X" in text


def test_parse_feedback_regions_clamps_and_limits():
    regions = parse_feedback_regions(
        [
            {"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2, "label": "A"},
            {"x": 0.9, "y": 0.9, "w": 0.2, "h": 0.2},  # overflows
            {"x": 0.0, "y": 0.0, "w": 0.1, "h": 0.1, "label": "B"},
            {"x": 0.2, "y": 0.2, "w": 0.1, "h": 0.1, "label": "C"},
            {"x": 0.3, "y": 0.3, "w": 0.1, "h": 0.1, "label": "D"},
        ]
    )
    assert len(regions) == 3
    assert regions[0].label == "A"
    assert regions[1].label == "B"


def test_parse_grade_answer_correct():
    text, correct, help_request, regions = parse_grade_answer_response(
        'Correct. Sets have no duplicates.\n{"question_closed": true, "correct": "yes"}'
    )
    assert correct is True
    assert help_request is False
    assert text.startswith("Correct.")
    assert regions == []
    assert "question_closed" not in text


def test_parse_grade_answer_ignores_empty_set_braces():
    """Empty-set notation `{}` must not prevent stripping the protocol trailer."""
    raw = (
        'Correct. The empty set is written ∅ or {}.\n\n'
        '```json\n'
        '{"question_closed": true, "correct": "yes", "feedback_regions": []}\n'
        '```'
    )
    text, correct, help_request, regions = parse_grade_answer_response(raw)
    assert correct is True
    assert help_request is False
    assert "empty set" in text.lower()
    assert "question_closed" not in text
    assert "```" not in text
    assert regions == []


def test_parse_grade_answer_incorrect():
    text, correct, help_request, regions = parse_grade_answer_response(
        'Not quite. Order does not matter.\n{"question_closed": true, "correct": "no"}'
    )
    assert correct is False
    assert help_request is False
    assert text.startswith("Not quite.")
    assert regions == []


def test_parse_grade_answer_help_request():
    text, correct, help_request, regions = parse_grade_answer_response(
        'Help request.\n{"help_request": true}'
    )
    assert help_request is True
    assert correct is False
    assert "Help request" not in text
    assert regions == []


def test_parse_grade_answer_no_verdict_is_help():
    text, correct, help_request, regions = parse_grade_answer_response(
        "Let's think about what a set is first. [Source: sets_definition — Definition]"
    )
    assert help_request is True
    assert correct is False
    assert "set" in text.lower()
    assert regions == []


def test_finalize_turn_writes_assisted_flag(tmp_path: Path):
    state_path = tmp_path / "learner-state.md"
    state.initialize(
        state_path,
        title="Test",
        session_id="sess-1",
        created_at="2026-01-01T00:00:00+00:00",
        knowledge_source="domain:x/y",
        focus_mode="adaptive",
        max_questions=10,
    )
    question = GeneratedQuestion(
        question_number=1,
        question_id="q-1",
        concept_id="sets_definition",
        concept_label="Definition of a Set",
        question_type="recall",
        intended_difficulty=0.5,
        question_text="What is a set?",
        gen_response="",
    )
    assessment = AssessmentResult(
        correct="yes",
        hint_count=0,
        turn_count=1,
        hedging_count=0,
    )
    finalize_turn(
        session_id="sess-1",
        question=question,
        assessment=assessment,
        explicit_rating="ok",
        state_path=state_path,
        assisted=True,
    )
    rows = state.parse_question_log(state_path)
    assert rows[0]["assisted"] == "yes"


def test_parse_question_block_protocol_format():
    """Test _parse_question_block with protocol QUESTION block format."""
    raw = """QUESTION
concept: set_theory_intro
type: apply
intended_difficulty: 0.65
depth: 2
---
What distinguishes a set from a multiset? [Source: set_theory_intro — Intro]"""
    concept, qtype, difficulty, text = _parse_question_block(raw)
    assert concept == "set_theory_intro"
    assert qtype == "apply"
    assert difficulty == pytest.approx(0.65)
    assert "multiset" in text


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_program_root(tmp_path: Path) -> Path:
    """Create a minimal program_root directory with AGENTS.md and protocols."""
    root = tmp_path / "program"
    (root / "shared" / "protocols").mkdir(parents=True)

    (root / "AGENTS.md").write_text("# Tutor Harness\nSystem content.", encoding="utf-8")
    (root / "shared" / "protocols" / "generate-question.md").write_text(
        "# Protocol: generate-question\nInstructions.", encoding="utf-8"
    )
    (root / "shared" / "protocols" / "extract-signals.md").write_text(
        "# Protocol: extract-signals\nExtract instructions.", encoding="utf-8"
    )
    src_protocols = _PROGRAM_ROOT / "shared" / "protocols"
    for name in ("tutor-turn.md", "grade-answer.md"):
        src = src_protocols / name
        if src.is_file():
            (root / "shared" / "protocols" / name).write_text(
                src.read_text(encoding="utf-8"), encoding="utf-8"
            )

    import json

    chapter = root / "domains" / "_test" / "chapters" / "01-intro"
    chapter.mkdir(parents=True)
    graph = {
        "nodes": [
            {
                "id": "set_theory_intro",
                "label": "Introduction to Set Theory",
                "depth": 1,
            }
        ],
        "edges": [],
    }
    (chapter / "concept-graph.json").write_text(json.dumps(graph), encoding="utf-8")
    wiki = chapter / "wiki"
    wiki.mkdir()
    (wiki / "set_theory_intro.md").write_text("# Intro\n\nSets are collections.", encoding="utf-8")
    return root


def _run_cycle(
    tmp_path: Path,
    state_path: Path,
    question_number: int = 1,
    session_id: str = "test-session",
    learner_response: str = "A set has unique elements; a multiset allows duplicates.",
) -> QuestionResult:
    root = _make_program_root(tmp_path / f"root_{question_number}")
    chapter = resolve_chapter("domain:_test/01-intro", root)
    metadata = {
        "fixture_commit": "abc1234",
        "provider": "stub",
        "model": "stub-model",
    }
    return run_question_cycle(
        session_id=session_id,
        question_number=question_number,
        learner_response=learner_response,
        chapter=chapter,
        concept_id="set_theory_intro",
        state_path=state_path,
        provider=StubProvider(),
        model="stub-model",
        config={},
        metadata=metadata,
        program_root=root,
    )


# ---------------------------------------------------------------------------
# Single-cycle structural tests
# ---------------------------------------------------------------------------

def test_returns_question_result(tmp_path: Path):
    state_path = tmp_path / "learner-state.md"
    state.initialize(state_path)
    result = _run_cycle(tmp_path, state_path)
    assert isinstance(result, QuestionResult)


def test_question_number_preserved(tmp_path: Path):
    state_path = tmp_path / "learner-state.md"
    state.initialize(state_path)
    result = _run_cycle(tmp_path, state_path, question_number=7)
    assert result.question_number == 7


def test_session_id_preserved(tmp_path: Path):
    state_path = tmp_path / "learner-state.md"
    state.initialize(state_path)
    result = _run_cycle(tmp_path, state_path, session_id="my-session")
    assert result.session_id == "my-session"


def test_parsed_concept_from_stub(tmp_path: Path):
    state_path = tmp_path / "learner-state.md"
    state.initialize(state_path)
    result = _run_cycle(tmp_path, state_path)
    assert result.concept == "Introduction to Set Theory"


def test_parsed_question_type_from_stub(tmp_path: Path):
    state_path = tmp_path / "learner-state.md"
    state.initialize(state_path)
    result = _run_cycle(tmp_path, state_path)
    assert result.question_type == "recall"


def test_parsed_intended_difficulty_from_stub(tmp_path: Path):
    state_path = tmp_path / "learner-state.md"
    state.initialize(state_path)
    result = _run_cycle(tmp_path, state_path)
    assert result.intended_difficulty == pytest.approx(0.5)


def test_question_text_contains_question(tmp_path: Path):
    state_path = tmp_path / "learner-state.md"
    state.initialize(state_path)
    result = _run_cycle(tmp_path, state_path)
    assert "set" in result.question_text.lower()
    assert len(result.question_text) > 0


def test_learner_response_preserved(tmp_path: Path):
    state_path = tmp_path / "learner-state.md"
    state.initialize(state_path)
    answer = "My answer here."
    result = _run_cycle(tmp_path, state_path, learner_response=answer)
    # Sim harness runs a follow-up turn when the stub tutor has not closed the question.
    assert result.learner_response == "I think the union of the sets is empty."


def test_signals_from_stub(tmp_path: Path):
    state_path = tmp_path / "learner-state.md"
    state.initialize(state_path)
    result = _run_cycle(tmp_path, state_path)
    assert result.explicit_rating == "ok"
    assert result.correct == "yes"
    assert result.hint_count == 1
    assert result.turn_count == 2
    assert result.hedging_count == 0


def test_reward_is_float_in_range(tmp_path: Path):
    state_path = tmp_path / "learner-state.md"
    state.initialize(state_path)
    result = _run_cycle(tmp_path, state_path)
    assert isinstance(result.reward, float)
    assert -1.0 <= result.reward <= 1.0


def test_new_difficulty_is_float_in_range(tmp_path: Path):
    state_path = tmp_path / "learner-state.md"
    state.initialize(state_path)
    result = _run_cycle(tmp_path, state_path)
    assert isinstance(result.new_difficulty, float)
    assert 0.1 <= result.new_difficulty <= 0.9


def test_metadata_keys_present(tmp_path: Path):
    state_path = tmp_path / "learner-state.md"
    state.initialize(state_path)
    result = _run_cycle(tmp_path, state_path)
    assert "fixture_commit" in result.metadata
    assert "provider" in result.metadata
    assert "model" in result.metadata


def test_metadata_values(tmp_path: Path):
    state_path = tmp_path / "learner-state.md"
    state.initialize(state_path)
    result = _run_cycle(tmp_path, state_path)
    assert result.metadata["fixture_commit"] == "abc1234"
    assert result.metadata["provider"] == "stub"
    assert result.metadata["model"] == "stub-model"


# ---------------------------------------------------------------------------
# State mutation tests (single cycle)
# ---------------------------------------------------------------------------

def test_scalar_updated_after_cycle(tmp_path: Path):
    state_path = tmp_path / "learner-state.md"
    state.initialize(state_path)
    initial = state.read_scalar(state_path)
    result = _run_cycle(tmp_path, state_path)
    new_scalar = state.read_scalar(state_path)
    assert new_scalar == pytest.approx(result.new_difficulty)
    # The stub produces a reward != 0, so difficulty should change
    assert new_scalar != pytest.approx(initial)


def test_log_row_appended_after_cycle(tmp_path: Path):
    state_path = tmp_path / "learner-state.md"
    state.initialize(state_path)
    _run_cycle(tmp_path, state_path)
    content = state_path.read_text(encoding="utf-8")
    # Should have at least one data row after the separator
    lines = [l for l in content.splitlines() if l.startswith("|") and "---" not in l and "Q#" not in l]
    assert len(lines) == 1


# ---------------------------------------------------------------------------
# Full 3-cycle session test
# ---------------------------------------------------------------------------

def test_three_cycles_produce_three_log_rows(tmp_path: Path):
    state_path = tmp_path / "learner-state.md"
    state.initialize(state_path)

    for i in range(1, 4):
        _run_cycle(tmp_path, state_path, question_number=i)

    content = state_path.read_text(encoding="utf-8")
    data_rows = [
        l for l in content.splitlines()
        if l.startswith("|") and "---" not in l and "Q#" not in l
    ]
    assert len(data_rows) == 3


def test_three_cycles_valid_log_content(tmp_path: Path):
    state_path = tmp_path / "learner-state.md"
    state.initialize(state_path)

    for i in range(1, 4):
        _run_cycle(tmp_path, state_path, question_number=i, session_id="sess-xyz")

    content = state_path.read_text(encoding="utf-8")
    assert "set_theory_intro" in content
    assert "sess-xyz" in content


def test_three_cycles_scalar_changes_from_initial(tmp_path: Path):
    state_path = tmp_path / "learner-state.md"
    state.initialize(state_path)
    initial = state.read_scalar(state_path)  # 0.5

    for i in range(1, 4):
        _run_cycle(tmp_path, state_path, question_number=i)

    final = state.read_scalar(state_path)
    assert final != pytest.approx(initial)


def test_three_cycles_question_numbers_in_log(tmp_path: Path):
    state_path = tmp_path / "learner-state.md"
    state.initialize(state_path)

    results = [_run_cycle(tmp_path, state_path, question_number=i) for i in range(1, 4)]

    assert [r.question_number for r in results] == [1, 2, 3]

    content = state_path.read_text(encoding="utf-8")
    for i in range(1, 4):
        assert f"| {i} |" in content


def test_three_cycles_metadata_in_all_results(tmp_path: Path):
    state_path = tmp_path / "learner-state.md"
    state.initialize(state_path)

    results = [_run_cycle(tmp_path, state_path, question_number=i) for i in range(1, 4)]

    for r in results:
        assert "fixture_commit" in r.metadata
        assert "provider" in r.metadata
        assert "model" in r.metadata


def test_generate_question_from_bank_not_ephemeral(tmp_path: Path):
    """Pytest chapter has question-bank.json; selection must not use LLM fallback."""
    state_path = tmp_path / "learner-state.md"
    state.initialize(state_path)
    chapter = resolve_chapter("domain:_pytest/01-intro", _PROGRAM_ROOT)
    metadata: dict = {}
    generated = generate_question(
        session_id="bank-test",
        question_number=1,
        chapter=chapter,
        concept_id=None,
        state_path=state_path,
        provider=StubProvider(),
        model="stub-model",
        config={},
        metadata=metadata,
        program_root=_PROGRAM_ROOT,
        asked_ids=set(),
    )
    assert not generated.question_id.startswith("ephemeral:")
    assert metadata.get("question_bank_fallback") is not True
    assert generated.question_text


def test_finalize_turn_appends_log_without_legacy_mastery(tmp_path: Path):
    state_path = tmp_path / "learner-state.md"
    state.initialize(state_path)
    question = GeneratedQuestion(
        question_number=1,
        question_id="q-1",
        concept_id="sets_definition",
        concept_label="Definition of a Set",
        question_type="recall",
        intended_difficulty=0.5,
        question_text="What is a set?",
        gen_response="",
    )
    assessment = AssessmentResult(
        correct="yes",
        hint_count=0,
        turn_count=1,
        hedging_count=0,
        llm_explicit_rating="ok",
        llm_inconsistency=False,
        flag_reason=None,
    )
    finalize_turn(
        session_id="sess-1",
        question=question,
        assessment=assessment,
        explicit_rating="ok",
        state_path=state_path,
    )
    # Legacy ## Mastery map is no longer written; logs are the source of truth.
    assert state.read_mastery(state_path) == {}
    rows = state.parse_question_log(state_path)
    assert len(rows) == 1
    assert rows[0]["concept"] == "sets_definition"
    assert rows[0]["correct"] == "yes"
