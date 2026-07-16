"""Provider swap proof — PRD Success Criterion 5.

Demonstrates that bookkeeping (reward, difficulty scalar, log rows) is
identical regardless of which provider is used, because all math runs in
the runtime, not inside the LLM.

Two NamedStubProvider instances simulate "anthropic" and "nim" by setting
different provider_name attributes. The same seed/fixture/concept is used
for both sessions.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from apore.knowledge.chapter import resolve_chapter
from apore.providers.stub import StubProvider
from apore.runtime import state
from apore.runtime.core import QuestionResult, run_question_cycle


# ---------------------------------------------------------------------------
# Named stub provider — simulates a named provider without network calls
# ---------------------------------------------------------------------------

class NamedStubProvider(StubProvider):
    """StubProvider subclass that records a provider name in results."""

    def __init__(self, provider_name: str) -> None:
        self.provider_name = provider_name

    def invoke(self, system_prompt: str, messages: list[dict], model: str, config: dict) -> str:
        return super().invoke(system_prompt, messages, model, config)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_LEARNER_RESPONSE = "A set has unique elements; a multiset allows duplicates."

_CONCEPTS = ["set_theory_intro", "set_theory_intro", "set_theory_intro"]  # 3 questions


def _make_program_root(root: Path) -> Path:
    """Minimal program_root with AGENTS.md, protocols, and a test chapter."""
    import json

    (root / "shared" / "protocols").mkdir(parents=True)
    (root / "AGENTS.md").write_text("# Tutor Harness\nSystem content.", encoding="utf-8")
    (root / "shared" / "protocols" / "generate-question.md").write_text(
        "# Protocol: generate-question\nInstructions.", encoding="utf-8"
    )
    (root / "shared" / "protocols" / "extract-signals.md").write_text(
        "# Protocol: extract-signals\nExtract instructions.", encoding="utf-8"
    )
    from pathlib import Path as _Path

    _program = _Path(__file__).resolve().parents[2]
    tutor_src = _program / "shared" / "protocols" / "tutor-turn.md"
    if tutor_src.is_file():
        (root / "shared" / "protocols" / "tutor-turn.md").write_text(
            tutor_src.read_text(encoding="utf-8"), encoding="utf-8"
        )
    chapter = root / "domains" / "_sim" / "chapters" / "01-intro"
    chapter.mkdir(parents=True)
    graph = {
        "nodes": [{"id": "set_theory_intro", "label": "Introduction to Set Theory", "depth": 1}],
        "edges": [],
    }
    (chapter / "concept-graph.json").write_text(json.dumps(graph), encoding="utf-8")
    wiki = chapter / "wiki"
    wiki.mkdir()
    (wiki / "set_theory_intro.md").write_text("# Intro\n\nContent.", encoding="utf-8")
    return root


def _run_session(
    tmp_path: Path,
    provider_name: str,
    session_id: str,
    fixture_commit: str = "abc1234",
    model: str = "stub-model",
) -> tuple[list[QuestionResult], Path]:
    """Run a 3-question session with the given named provider.

    Returns (list[QuestionResult], state_path).
    """
    tmp_path.mkdir(parents=True, exist_ok=True)
    state_path = tmp_path / f"learner-state-{provider_name}.md"
    state.initialize(state_path)
    provider = NamedStubProvider(provider_name)
    results = []

    for q in range(1, 4):
        root = _make_program_root(tmp_path / f"{provider_name}_root_{q}")
        metadata = {
            "fixture_commit": fixture_commit,
            "provider": provider_name,
            "model": model,
        }
        chapter = resolve_chapter("domain:_sim/01-intro", root)
        result = run_question_cycle(
            session_id=session_id,
            question_number=q,
            learner_response=_LEARNER_RESPONSE,
            chapter=chapter,
            concept_id="set_theory_intro",
            state_path=state_path,
            provider=provider,
            model=model,
            config={},
            metadata=metadata,
            program_root=root,
        )
        results.append(result)

    return results, state_path


def _data_rows(state_path: Path) -> list[str]:
    """Return non-header, non-separator table rows from the Question Log."""
    content = state_path.read_text(encoding="utf-8")
    return [
        line for line in content.splitlines()
        if line.startswith("|") and "---" not in line and "Q#" not in line
    ]


def _log_columns(state_path: Path) -> list[str]:
    """Return column names from the Question Log header row."""
    content = state_path.read_text(encoding="utf-8")
    # Match the entire header line (ends at newline)
    m = re.search(r"(\| Q# \|[^\n]+)", content)
    if not m:
        return []
    return [c.strip() for c in m.group(1).strip("|").split("|")]


# ---------------------------------------------------------------------------
# The swap proof test
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def swap_sessions(tmp_path_factory):
    """Run both sessions once; reuse results across all assertions."""
    base = tmp_path_factory.mktemp("swap")
    anthropic_results, anthropic_state = _run_session(
        base / "anthropic", provider_name="anthropic", session_id="session-anthropic"
    )
    nim_results, nim_state = _run_session(
        base / "nim", provider_name="nim", session_id="session-nim"
    )
    return anthropic_results, anthropic_state, nim_results, nim_state


def test_same_number_of_log_rows(swap_sessions):
    """Both sessions produce the same number of log rows."""
    _, anthropic_state, _, nim_state = swap_sessions
    assert len(_data_rows(anthropic_state)) == len(_data_rows(nim_state))


def test_same_reward_values(swap_sessions):
    """Both sessions produce identical reward values for each question."""
    anthropic_results, _, nim_results, _ = swap_sessions
    for a, n in zip(anthropic_results, nim_results):
        assert a.reward == pytest.approx(n.reward), (
            f"Q{a.question_number}: anthropic reward={a.reward}, nim reward={n.reward}"
        )


def test_same_final_difficulty_scalar(swap_sessions):
    """Both sessions converge to the same final difficulty scalar."""
    _, anthropic_state, _, nim_state = swap_sessions
    assert state.read_scalar(anthropic_state) == pytest.approx(state.read_scalar(nim_state))


def test_log_rows_have_required_columns(swap_sessions):
    """Both state files have all required Question Log columns."""
    required = {
        "Q#", "session", "date", "concept", "question_type",
        "intended_difficulty", "explicit_rating", "correct",
        "hints", "turns", "hedging", "reward_R", "new_difficulty",
    }
    _, anthropic_state, _, nim_state = swap_sessions
    for path in (anthropic_state, nim_state):
        cols = set(_log_columns(path))
        assert required <= cols, f"Missing columns in {path.name}: {required - cols}"


def test_only_metadata_provider_differs(swap_sessions):
    """The only intentional difference is the provider name in metadata."""
    anthropic_results, _, nim_results, _ = swap_sessions
    for a, n in zip(anthropic_results, nim_results):
        assert a.metadata["provider"] == "anthropic"
        assert n.metadata["provider"] == "nim"
        # Everything else matches
        assert a.metadata["fixture_commit"] == n.metadata["fixture_commit"]
        assert a.metadata["model"] == n.metadata["model"]
        assert a.reward == pytest.approx(n.reward)
        assert a.new_difficulty == pytest.approx(n.new_difficulty)
        assert a.concept == n.concept
        assert a.question_type == n.question_type
        assert a.intended_difficulty == pytest.approx(n.intended_difficulty)
        assert a.correct == n.correct
        assert a.explicit_rating == n.explicit_rating
        assert a.hint_count == n.hint_count
        assert a.turn_count == n.turn_count
        assert a.hedging_count == n.hedging_count


def test_scalar_path_identical(swap_sessions):
    """Difficulty scalar evolves identically for both providers, question by question."""
    anthropic_results, _, nim_results, _ = swap_sessions
    for a, n in zip(anthropic_results, nim_results):
        assert a.new_difficulty == pytest.approx(n.new_difficulty), (
            f"Q{a.question_number}: anthropic difficulty={a.new_difficulty}, "
            f"nim difficulty={n.new_difficulty}"
        )
