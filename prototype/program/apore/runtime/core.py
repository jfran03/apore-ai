"""Core orchestration loop for one question cycle (PRD §6)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from apore.providers.base import Provider
from apore.runtime import state
from apore.runtime.context import assemble_prompt
from apore.runtime.reward import QuestionSignals, compute_reward, update_difficulty


@dataclass
class QuestionResult:
    question_number: int
    session_id: str
    concept: str
    question_type: str
    intended_difficulty: float
    question_text: str
    learner_response: str
    explicit_rating: str
    correct: str
    hint_count: int
    turn_count: int
    hedging_count: int
    reward: float
    new_difficulty: float
    metadata: dict  # fixture_commit, provider, model


def _parse_question_block(response: str) -> tuple[str, str, float, str]:
    """Parse the generate-question response.

    Returns (concept, question_type, intended_difficulty, question_text).

    Expected format:
        CONCEPT: <value>
        TYPE: <value>
        INTENDED_DIFFICULTY: <value>

        <question body (everything after the blank line)>
    """
    lines = response.splitlines()
    concept = ""
    question_type = ""
    intended_difficulty = 0.5
    blank_index = -1

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("CONCEPT:"):
            concept = stripped[len("CONCEPT:"):].strip()
        elif stripped.startswith("TYPE:"):
            question_type = stripped[len("TYPE:"):].strip()
        elif stripped.startswith("INTENDED_DIFFICULTY:"):
            intended_difficulty = float(stripped[len("INTENDED_DIFFICULTY:"):].strip())
        elif stripped == "" and blank_index == -1 and concept:
            blank_index = i

    if blank_index == -1:
        question_text = ""
    else:
        question_text = "\n".join(lines[blank_index + 1:]).strip()

    return concept, question_type, intended_difficulty, question_text


def _parse_signals(response: str) -> dict:
    """Extract JSON object from the extract-signals response."""
    match = re.search(r"\{.*\}", response, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in extract-signals response: {response!r}")
    return json.loads(match.group())


def run_question_cycle(
    session_id: str,
    question_number: int,
    learner_response: str,
    grounding_paths: list[Path],
    state_path: Path,
    provider: Provider,
    model: str,
    config: dict,
    metadata: dict,
    program_root: Path | None = None,
) -> QuestionResult:
    """Run one full question cycle: generate → respond → extract → reward → state append."""

    # 1. Generate question
    gen_prompt = assemble_prompt(
        "generate-question", grounding_paths, state_path, program_root=program_root
    )
    gen_response = provider.invoke(
        gen_prompt["system"], gen_prompt["messages"], model, config
    )
    concept, question_type, intended_difficulty, question_text = _parse_question_block(gen_response)

    # 2. Build dialogue transcript for extract-signals
    transcript_messages = gen_prompt["messages"] + [
        {"role": "assistant", "content": gen_response},
        {"role": "user", "content": learner_response},
    ]

    # 3. Extract signals
    extract_prompt = assemble_prompt(
        "extract-signals", grounding_paths, state_path, program_root=program_root
    )
    extract_messages = extract_prompt["messages"] + [
        {"role": "assistant", "content": gen_response},
        {"role": "user", "content": learner_response},
    ]
    extract_response = provider.invoke(
        extract_prompt["system"], extract_messages, model, config
    )
    signals_data = _parse_signals(extract_response)

    # 4. Compute reward
    signals = QuestionSignals(
        explicit_rating=signals_data["explicit_rating"],
        correct=signals_data["correct"],
        hint_count=int(signals_data["hint_count"]),
        hedging_count=int(signals_data["hedging_count"]),
        turn_count=int(signals_data["turn_count"]),
    )
    reward = compute_reward(signals)

    current_difficulty = state.read_scalar(state_path)
    new_difficulty = update_difficulty(current_difficulty, reward)

    # 5. Append state
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    state.append_log_row(
        state_path,
        {
            "Q#": question_number,
            "session": session_id,
            "date": today,
            "concept": concept,
            "question_type": question_type,
            "intended_difficulty": intended_difficulty,
            "explicit_rating": signals.explicit_rating,
            "correct": signals.correct,
            "hints": signals.hint_count,
            "turns": signals.turn_count,
            "hedging": signals.hedging_count,
            "reward_R": round(reward, 4),
            "new_difficulty": round(new_difficulty, 4),
        },
    )
    state.write_scalar(state_path, new_difficulty)

    return QuestionResult(
        question_number=question_number,
        session_id=session_id,
        concept=concept,
        question_type=question_type,
        intended_difficulty=intended_difficulty,
        question_text=question_text,
        learner_response=learner_response,
        explicit_rating=signals.explicit_rating,
        correct=signals.correct,
        hint_count=signals.hint_count,
        turn_count=signals.turn_count,
        hedging_count=signals.hedging_count,
        reward=reward,
        new_difficulty=new_difficulty,
        metadata=metadata,
    )
