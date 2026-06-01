"""Tests for apore.runtime.core.run_question_cycle using StubProvider."""

from __future__ import annotations

import pytest
from pathlib import Path

from apore.providers.stub import StubProvider
from apore.runtime import state
from apore.runtime.core import QuestionResult, run_question_cycle


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
    return root


def _run_cycle(
    tmp_path: Path,
    state_path: Path,
    question_number: int = 1,
    session_id: str = "test-session",
    learner_response: str = "A set has unique elements; a multiset allows duplicates.",
) -> QuestionResult:
    root = _make_program_root(tmp_path / f"root_{question_number}")
    metadata = {
        "fixture_commit": "abc1234",
        "provider": "stub",
        "model": "stub-model",
    }
    return run_question_cycle(
        session_id=session_id,
        question_number=question_number,
        learner_response=learner_response,
        grounding_paths=[],
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
    assert result.concept == "set_theory_intro"


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
    assert result.learner_response == answer


def test_signals_from_stub(tmp_path: Path):
    state_path = tmp_path / "learner-state.md"
    state.initialize(state_path)
    result = _run_cycle(tmp_path, state_path)
    assert result.explicit_rating == "ok"
    assert result.correct == "yes"
    assert result.hint_count == 1
    assert result.turn_count == 3
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
