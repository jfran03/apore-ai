"""Core question cycle: generate question, extract signals, compute reward, update state."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from apore.knowledge.chapter import (
    ChapterContext,
    ConceptGraph,
    get_wiki_paths,
    load_concept_graph,
    select_next_concept,
)
from apore.providers.base import Provider
from apore.runtime import state
from apore.runtime.context import assemble_prompt
from apore.runtime.question_bank import (
    QuestionBankExhaustedError,
    format_question_block,
    load_question_bank,
    select_question,
)
from apore.runtime.reward import Correct, QuestionSignals, Rating, compute_reward, update_difficulty

_DEFAULT_SIGNALS: dict[str, object] = {
    "explicit_rating": "ok",
    "correct": "no",
    "hint_count": 0,
    "turn_count": 0,
    "hedging_count": 0,
}

_EXTRACT_SIGNALS_CLOSING = (
    "The question–answer exchange above is complete. "
    "Switch to extract-signals mode now. "
    "Reply with ONLY one JSON object matching the extract-signals schema. "
    "No prose, markdown fences, or teacher dialogue."
)


@dataclass
class GeneratedQuestion:
    question_number: int
    question_id: str
    concept_id: str
    concept_label: str
    question_type: str
    intended_difficulty: float
    question_text: str
    gen_response: str

    @property
    def concept(self) -> str:
        """Human-readable concept label (logging / backward compat)."""
        return self.concept_label


@dataclass
class TutorTurnResult:
    tutor_message: str
    question_closed: bool


@dataclass
class GradeAnswerTurnResult:
    tutor_message: str
    correct: bool


@dataclass
class AssessmentResult:
    """LLM-extracted signals before learner difficulty rating."""

    correct: str
    hint_count: int
    turn_count: int
    hedging_count: int
    llm_explicit_rating: str = "ok"
    llm_inconsistency: bool = False
    flag_reason: str | None = None


@dataclass
class GradingResult:
    question_number: int
    explicit_rating: str
    correct: str
    hint_count: int
    turn_count: int
    hedging_count: int
    reward: float
    new_difficulty: float
    inconsistency_flag: bool = False


@dataclass
class QuestionResult:
    """Full generate + grade cycle (sim and legacy callers)."""

    session_id: str
    question_number: int
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
    metadata: dict


def _strip_code_fence(text: str) -> str:
    lines = text.strip().splitlines()
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _parse_question_block_legacy(text: str) -> tuple[str, str, float, str]:
    """Parse legacy CONCEPT:/TYPE:/INTENDED_DIFFICULTY: format."""
    concept = "unknown"
    qtype = "recall"
    difficulty = 0.5
    question_text = text

    for line in text.splitlines():
        if line.startswith("CONCEPT:"):
            concept = line.split(":", 1)[1].strip()
        elif line.startswith("TYPE:"):
            qtype = line.split(":", 1)[1].strip()
        elif line.startswith("INTENDED_DIFFICULTY:"):
            difficulty = float(line.split(":", 1)[1].strip())

    parts = text.split("\n\n", 1)
    if len(parts) > 1:
        question_text = parts[1].strip()
    else:
        lines = [l for l in text.splitlines() if not l.startswith(("CONCEPT:", "TYPE:", "INTENDED_DIFFICULTY:"))]
        question_text = "\n".join(lines).strip()

    return concept, qtype, difficulty, question_text


def _parse_question_block_protocol(text: str) -> tuple[str, str, float, str]:
    """Parse protocol QUESTION block with concept:/type:/--- body."""
    lines = text.splitlines()
    if lines and lines[0].strip().upper() == "QUESTION":
        lines = lines[1:]

    concept = "unknown"
    qtype = "recall"
    difficulty = 0.5
    body_lines: list[str] = []
    in_body = False

    for line in lines:
        if line.strip() == "---":
            in_body = True
            continue
        if not in_body:
            stripped = line.strip()
            lower = stripped.lower()
            if lower.startswith("concept:"):
                concept = stripped.split(":", 1)[1].strip()
            elif lower.startswith("type:"):
                qtype = stripped.split(":", 1)[1].strip()
            elif lower.startswith("intended_difficulty:"):
                difficulty = float(stripped.split(":", 1)[1].strip())
        else:
            body_lines.append(line)

    question_text = "\n".join(body_lines).strip()
    return concept, qtype, difficulty, question_text


def _parse_question_block(raw: str) -> tuple[str, str, float, str]:
    """Parse generate-question response (protocol or legacy format)."""
    text = _strip_code_fence(raw)
    if re.search(r"^CONCEPT:", text, re.MULTILINE):
        return _parse_question_block_legacy(text)
    return _parse_question_block_protocol(text)


def _find_json_object(text: str) -> str | None:
    """Return the first balanced {...} substring that parses as JSON."""
    for start in (i for i, ch in enumerate(text) if ch == "{"):
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : i + 1]
                    try:
                        json.loads(candidate)
                    except json.JSONDecodeError:
                        break
                    return candidate
    return None


def _parse_signals(raw: str) -> dict:
    """Extract JSON object from extract-signals response."""
    stripped = _strip_code_fence((raw or "").strip())
    if not stripped:
        return dict(_DEFAULT_SIGNALS)

    for candidate in (stripped, _find_json_object(stripped)):
        if not candidate:
            continue
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed

    return dict(_DEFAULT_SIGNALS)


def _signals_inconsistency(explicit_rating: str, hint_count: int, turn_count: int) -> tuple[bool, str | None]:
    """FR-4.4: easy self-rating vs high scaffolding / turn count."""
    if explicit_rating == "easy" and (hint_count >= 4 or turn_count >= 10):
        return True, (
            f"Learner rated easy but required {hint_count} hints and {turn_count} turns."
        )
    return False, None


_TUTOR_CLOSE_PATTERN = re.compile(r"Yes, exactly\s*[—\-]", re.IGNORECASE)

_GRADE_CORRECT_PATTERN = re.compile(r"^Correct\.", re.IGNORECASE | re.MULTILINE)
_GRADE_INCORRECT_PATTERN = re.compile(r"^Not quite\.", re.IGNORECASE | re.MULTILINE)

_SKIP_PROMPT = (
    "Before we move on — briefly, why do you want to skip this question?"
)


def seed_dialogue_transcript(question: GeneratedQuestion) -> list[dict[str, str]]:
    """Initial assistant turn: the generated question block."""
    return [{"role": "assistant", "content": question.gen_response}]


def parse_tutor_response(raw: str) -> tuple[str, bool]:
    """Strip optional JSON trailer and detect question closure."""
    text = _strip_code_fence((raw or "").strip())
    question_closed = bool(_TUTOR_CLOSE_PATTERN.search(text))

    json_obj = _find_json_object(text)
    if json_obj:
        try:
            parsed = json.loads(json_obj)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict) and parsed.get("question_closed"):
            question_closed = True
            text = text.replace(json_obj, "").strip()

    return text.strip(), question_closed


def parse_grade_answer_response(raw: str) -> tuple[str, bool]:
    """Strip JSON trailer and determine correctness from grade-answer response."""
    text = _strip_code_fence((raw or "").strip())
    correct = bool(_GRADE_CORRECT_PATTERN.search(text))

    json_obj = _find_json_object(text)
    if json_obj:
        try:
            parsed = json.loads(json_obj)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            trailer_correct = parsed.get("correct")
            if trailer_correct in ("yes", "no"):
                correct = trailer_correct == "yes"
            text = text.replace(json_obj, "").strip()

    if _GRADE_INCORRECT_PATTERN.search(text):
        correct = False

    return text.strip(), correct


def skip_prompt_message() -> str:
    return _SKIP_PROMPT


def tutor_turn(
    *,
    question: GeneratedQuestion,
    dialogue_transcript: list[dict[str, str]],
    learner_message: str,
    chapter: ChapterContext,
    state_path: Path,
    provider: Provider,
    model: str,
    config: dict,
    program_root: Path,
) -> TutorTurnResult:
    """Run one Socratic tutor turn for the learner's latest message."""
    graph = load_concept_graph(chapter)
    wiki_paths = get_wiki_paths(chapter, question.concept_id, graph)
    assembled = assemble_prompt(
        "tutor-turn",
        state_path,
        concept_id=question.concept_id,
        chapter=chapter,
        graph=graph,
        wiki_paths=wiki_paths,
        program_root=program_root,
    )
    messages = list(assembled["messages"]) + list(dialogue_transcript)
    messages.append({"role": "user", "content": learner_message.strip()})
    raw = provider.invoke(
        assembled["system"],
        messages,
        model,
        {**config, "protocol": "tutor-turn"},
    )
    tutor_message, question_closed = parse_tutor_response(raw)
    return TutorTurnResult(tutor_message=tutor_message, question_closed=question_closed)


def grade_answer_turn(
    *,
    question: GeneratedQuestion,
    dialogue_transcript: list[dict[str, str]],
    learner_message: str,
    chapter: ChapterContext,
    state_path: Path,
    provider: Provider,
    model: str,
    config: dict,
    program_root: Path,
) -> GradeAnswerTurnResult:
    """Grade a learner answer attempt: verdict first, then explanation; always closes."""
    graph = load_concept_graph(chapter)
    wiki_paths = get_wiki_paths(chapter, question.concept_id, graph)
    assembled = assemble_prompt(
        "grade-answer",
        state_path,
        concept_id=question.concept_id,
        chapter=chapter,
        graph=graph,
        wiki_paths=wiki_paths,
        program_root=program_root,
    )
    messages = list(assembled["messages"]) + list(dialogue_transcript)
    messages.append({"role": "user", "content": learner_message.strip()})
    raw = provider.invoke(
        assembled["system"],
        messages,
        model,
        {**config, "protocol": "grade-answer"},
    )
    tutor_message, correct = parse_grade_answer_response(raw)
    return GradeAnswerTurnResult(tutor_message=tutor_message, correct=correct)


def _build_grade_messages(
    question: GeneratedQuestion,
    learner_response: str,
    dialogue_transcript: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    """Assemble transcript messages for extract-signals (single-shot or multi-turn)."""
    if dialogue_transcript:
        return list(dialogue_transcript)
    return [
        {"role": "assistant", "content": question.gen_response},
        {"role": "user", "content": learner_response},
    ]


def generate_question(
    *,
    session_id: str,
    question_number: int,
    chapter: ChapterContext,
    concept_id: str | None,
    state_path: Path,
    provider: Provider,
    model: str,
    config: dict,
    metadata: dict,
    program_root: Path,
    mastery: dict[str, float] | None = None,
    asked_ids: set[str] | None = None,
    focus_mode: str = "adaptive",
    last_concept_id: str | None = None,
    allowed_concept_ids: set[str] | None = None,
) -> GeneratedQuestion:
    """Select from question bank when present; otherwise fall back to LLM generation."""
    graph = load_concept_graph(chapter)
    scalar = state.read_scalar(state_path)
    mastery_map = mastery if mastery is not None else state.read_mastery(state_path)
    asked = asked_ids if asked_ids is not None else state.read_asked_ids(state_path)
    bank = load_question_bank(chapter)

    if bank is not None and bank.questions:
        entry = select_question(
            bank=bank,
            graph=graph,
            concept_id=concept_id,
            scalar=scalar,
            asked_ids=asked,
            question_number=question_number,
            mastery=mastery_map,
            requested_concept_id=concept_id,
            focus_mode=focus_mode,
            last_concept_id=last_concept_id,
            allowed_concept_ids=allowed_concept_ids,
        )
        gen_response = format_question_block(entry, graph)
        concept_label = graph.label_for(entry.concept_id)
        return GeneratedQuestion(
            question_number=question_number,
            question_id=entry.id,
            concept_id=entry.concept_id,
            concept_label=concept_label,
            question_type=entry.type,
            intended_difficulty=entry.intended_difficulty,
            question_text=entry.text,
            gen_response=gen_response,
        )

    metadata["question_bank_fallback"] = True
    weak_only = focus_mode == "weak_points"
    selected_id = select_next_concept(
        graph,
        requested_id=concept_id,
        mastery=mastery_map,
        scalar=scalar,
        weak_only=weak_only,
        allowed_concept_ids=allowed_concept_ids,
    )
    wiki_paths = get_wiki_paths(chapter, selected_id, graph)

    assembled = assemble_prompt(
        "generate-question",
        state_path,
        concept_id=selected_id,
        chapter=chapter,
        graph=graph,
        wiki_paths=wiki_paths,
        program_root=program_root,
    )
    gen_response = provider.invoke(
        assembled["system"],
        assembled["messages"],
        model,
        {**config, "protocol": "generate-question"},
    )
    parsed_concept, question_type, intended_difficulty, question_text = _parse_question_block(
        gen_response
    )
    if parsed_concept != selected_id and parsed_concept != "unknown":
        metadata["concept_mismatch"] = {"expected": selected_id, "parsed": parsed_concept}

    concept_label = graph.label_for(selected_id)
    ephemeral_id = f"ephemeral:{session_id}:{question_number}"
    return GeneratedQuestion(
        question_number=question_number,
        question_id=ephemeral_id,
        concept_id=selected_id,
        concept_label=concept_label,
        question_type=question_type,
        intended_difficulty=intended_difficulty,
        question_text=question_text,
        gen_response=gen_response,
    )


def assess_response(
    *,
    question: GeneratedQuestion,
    learner_response: str,
    chapter: ChapterContext,
    state_path: Path,
    provider: Provider,
    model: str,
    config: dict,
    program_root: Path,
    dialogue_transcript: list[dict[str, str]] | None = None,
) -> AssessmentResult:
    """LLM-only grading: correctness and implicit counts; no state write."""
    graph = load_concept_graph(chapter)
    wiki_paths = get_wiki_paths(chapter, question.concept_id, graph)
    assembled = assemble_prompt(
        "extract-signals",
        state_path,
        concept_id=question.concept_id,
        chapter=chapter,
        graph=graph,
        wiki_paths=wiki_paths,
        program_root=program_root,
    )
    transcript = _build_grade_messages(question, learner_response, dialogue_transcript)
    messages = list(assembled["messages"]) + transcript
    messages.append({"role": "user", "content": _EXTRACT_SIGNALS_CLOSING})
    extract_response = provider.invoke(
        assembled["system"],
        messages,
        model,
        {**config, "protocol": "extract-signals"},
    )
    signals = _parse_signals(extract_response)

    correct = signals.get("correct", "no")
    hint_count = int(signals.get("hint_count", 0))
    turn_count = int(signals.get("turn_count", 1))
    hedging_count = int(signals.get("hedging_count", 0))
    llm_inconsistency = bool(signals.get("inconsistency", False))
    flag_reason = signals.get("flag_reason")

    return AssessmentResult(
        correct=correct,
        hint_count=hint_count,
        turn_count=turn_count,
        hedging_count=hedging_count,
        llm_explicit_rating=signals.get("explicit_rating", "ok"),
        llm_inconsistency=llm_inconsistency,
        flag_reason=flag_reason if isinstance(flag_reason, str) else None,
    )


def finalize_turn(
    *,
    session_id: str,
    question: GeneratedQuestion,
    assessment: AssessmentResult,
    explicit_rating: Rating,
    state_path: Path,
) -> GradingResult:
    """Apply learner difficulty rating, compute reward, log, and update scalar."""
    inconsistency, _reason = _signals_inconsistency(
        explicit_rating, assessment.hint_count, assessment.turn_count
    )
    inconsistency_flag = inconsistency or assessment.llm_inconsistency

    signals_obj = QuestionSignals(
        explicit_rating=explicit_rating,
        correct=assessment.correct,  # type: ignore[arg-type]
        hint_count=assessment.hint_count,
        hedging_count=assessment.hedging_count,
        turn_count=assessment.turn_count,
    )
    reward = compute_reward(signals_obj)
    new_difficulty = update_difficulty(state.read_scalar(state_path), reward)

    state.append_log_row(
        state_path,
        {
            "Q#": question.question_number,
            "session": session_id,
            "date": datetime.now(timezone.utc).date().isoformat(),
            "question_id": question.question_id,
            "concept": question.concept_id,
            "question_type": question.question_type,
            "intended_difficulty": question.intended_difficulty,
            "explicit_rating": explicit_rating,
            "correct": assessment.correct,
            "hints": assessment.hint_count,
            "turns": assessment.turn_count,
            "hedging": assessment.hedging_count,
            "reward_R": reward,
            "new_difficulty": new_difficulty,
        },
    )
    state.write_scalar(state_path, new_difficulty)

    mastery = state.read_mastery(state_path)
    current = mastery.get(question.concept_id, 0.0)
    if assessment.correct == "yes":
        mastery[question.concept_id] = min(1.0, current + 0.15)
    else:
        mastery[question.concept_id] = max(0.0, current - 0.1)
    state.write_mastery(state_path, mastery)

    return GradingResult(
        question_number=question.question_number,
        explicit_rating=explicit_rating,
        correct=assessment.correct,
        hint_count=assessment.hint_count,
        turn_count=assessment.turn_count,
        hedging_count=assessment.hedging_count,
        reward=reward,
        new_difficulty=new_difficulty,
        inconsistency_flag=inconsistency_flag,
    )


def grade_response(
    *,
    session_id: str,
    question: GeneratedQuestion,
    learner_response: str,
    chapter: ChapterContext,
    state_path: Path,
    provider: Provider,
    model: str,
    config: dict,
    metadata: dict,
    program_root: Path,
    explicit_rating: Rating | None = None,
    dialogue_transcript: list[dict[str, str]] | None = None,
) -> GradingResult:
    """One-shot grade + finalize (sim harness and legacy callers)."""
    assessment = assess_response(
        question=question,
        learner_response=learner_response,
        chapter=chapter,
        state_path=state_path,
        provider=provider,
        model=model,
        config=config,
        program_root=program_root,
        dialogue_transcript=dialogue_transcript,
    )
    rating: Rating = explicit_rating or assessment.llm_explicit_rating  # type: ignore[assignment]
    return finalize_turn(
        session_id=session_id,
        question=question,
        assessment=assessment,
        explicit_rating=rating,
        state_path=state_path,
    )


def run_question_cycle(
    *,
    session_id: str,
    question_number: int,
    learner_response: str,
    chapter: ChapterContext,
    concept_id: str | None = None,
    state_path: Path,
    provider: Provider,
    model: str,
    config: dict,
    metadata: dict,
    program_root: Path,
    explicit_rating: Rating | None = None,
) -> QuestionResult:
    """Generate a question, run multi-turn dialogue, grade, update state (sim harness)."""
    generated = generate_question(
        session_id=session_id,
        question_number=question_number,
        chapter=chapter,
        concept_id=concept_id,
        state_path=state_path,
        provider=provider,
        model=model,
        config=config,
        metadata=metadata,
        program_root=program_root,
    )
    transcript = seed_dialogue_transcript(generated)
    turn = tutor_turn(
        question=generated,
        dialogue_transcript=transcript,
        learner_message=learner_response,
        chapter=chapter,
        state_path=state_path,
        provider=provider,
        model=model,
        config=config,
        program_root=program_root,
    )
    transcript.append({"role": "user", "content": learner_response.strip()})
    transcript.append({"role": "assistant", "content": turn.tutor_message})

    if not turn.question_closed:
        follow_up = "I think the union of the sets is empty."
        turn2 = tutor_turn(
            question=generated,
            dialogue_transcript=transcript,
            learner_message=follow_up,
            chapter=chapter,
            state_path=state_path,
            provider=provider,
            model=model,
            config=config,
            program_root=program_root,
        )
        transcript.append({"role": "user", "content": follow_up})
        transcript.append({"role": "assistant", "content": turn2.tutor_message})

    last_user = next(
        (m["content"] for m in reversed(transcript) if m["role"] == "user"),
        learner_response,
    )
    grading = grade_response(
        session_id=session_id,
        question=generated,
        learner_response=last_user,
        chapter=chapter,
        state_path=state_path,
        provider=provider,
        model=model,
        config=config,
        metadata=metadata,
        program_root=program_root,
        explicit_rating=explicit_rating,
        dialogue_transcript=transcript,
    )
    return QuestionResult(
        session_id=session_id,
        question_number=generated.question_number,
        concept=generated.concept_label,
        question_type=generated.question_type,
        intended_difficulty=generated.intended_difficulty,
        question_text=generated.question_text,
        learner_response=last_user,
        explicit_rating=grading.explicit_rating,
        correct=grading.correct,
        hint_count=grading.hint_count,
        turn_count=grading.turn_count,
        hedging_count=grading.hedging_count,
        reward=grading.reward,
        new_difficulty=grading.new_difficulty,
        metadata=metadata,
    )
