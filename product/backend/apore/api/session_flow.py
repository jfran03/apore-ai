"""Tutoring session flow shared by legacy and domain-scoped routes.

Extracted verbatim from app.py so domain routes can wrap the same loop with
transcript persistence. Behavior must not diverge from the legacy routes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from fastapi import HTTPException

from apore.api.schemas import (
    QuestionRequest,
    QuestionResponse,
    SessionStateResponse,
    TurnRequest,
    TurnResponse,
)
from apore.knowledge.chapter import ChapterContext
from apore.runtime import state
from apore.runtime.core import (
    AssessmentResult,
    GeneratedQuestion,
    GradingResult,
    assess_response,
    finalize_turn,
    generate_question,
    grade_answer_turn,
    seed_dialogue_transcript,
    skip_prompt_message,
    tutor_turn,
)
from apore.runtime.intent import is_help_request
from apore.runtime.question_bank import QuestionBankExhaustedError


@dataclass
class PendingGrading:
    """Awaiting learner difficulty rating after LLM assessed correctness."""

    question: GeneratedQuestion
    learner_response: str
    assessment: AssessmentResult
    # Future multi-turn Socratic: append Teacher/learner turns before assess_response.
    dialogue_transcript: list[dict[str, str]] = field(default_factory=list)


@dataclass
class ReflectionState:
    """Optional post-rating tutor chat on a closed question."""

    question: GeneratedQuestion
    assessment: AssessmentResult
    grading: GradingResult
    transcript: list[dict[str, str]] = field(default_factory=list)


@dataclass
class SessionState:
    session_id: str
    title: str
    knowledge_source: str
    chapter: ChapterContext
    state_path: Path
    scalar: float
    question_count: int
    created_at: str
    focus_mode: str = "adaptive"
    max_questions: int = 10
    pending_question: GeneratedQuestion | None = None
    pending_grading: PendingGrading | None = None
    reflection: ReflectionState | None = None
    active_transcript: list[dict[str, str]] = field(default_factory=list)
    awaiting_skip_reason: bool = False
    tutor_mode: bool = False
    active_concept_id: str | None = None
    asked_question_ids: set[str] = field(default_factory=set)
    metadata: dict = field(default_factory=dict)


def session_state_response(sess: SessionState) -> SessionStateResponse:
    remaining = max(0, sess.max_questions - sess.question_count)
    return SessionStateResponse(
        session_id=sess.session_id,
        title=sess.title,
        scalar=state.read_scalar(sess.state_path),
        question_count=sess.question_count,
        mastery=state.read_mastery(sess.state_path),
        knowledge_source=sess.knowledge_source,
        focus_mode=sess.focus_mode,
        max_questions=sess.max_questions,
        questions_remaining=remaining,
        active_concept_id=sess.active_concept_id,
    )


def _grade_pending_dialogue(
    sess: SessionState,
    *,
    provider,
    model: str,
    program_root: Path,
    tutor_message: str | None = None,
) -> TurnResponse:
    """Assess active transcript and move session to pending_grading."""
    pending = sess.pending_question
    if pending is None:
        raise HTTPException(status_code=409, detail="No pending question to grade")

    transcript = list(sess.active_transcript)
    last_user = next(
        (m["content"] for m in reversed(transcript) if m["role"] == "user"),
        "",
    )
    assessment = assess_response(
        question=pending,
        learner_response=last_user,
        chapter=sess.chapter,
        state_path=sess.state_path,
        provider=provider,
        model=model,
        config={},
        program_root=program_root,
        dialogue_transcript=transcript,
    )
    sess.pending_grading = PendingGrading(
        question=pending,
        learner_response=last_user,
        assessment=assessment,
        dialogue_transcript=transcript,
    )
    sess.pending_question = None
    sess.active_transcript = []
    sess.awaiting_skip_reason = False
    return TurnResponse(
        phase="graded",
        question_number=pending.question_number,
        tutor_message=tutor_message,
        correct=assessment.correct,
        hint_count=assessment.hint_count,
        turn_count=assessment.turn_count,
        hedging_count=assessment.hedging_count,
        flag_reason=assessment.flag_reason,
    )


def _turn_response_from_grading(
    *,
    phase: str,
    grading: GradingResult,
    flag_reason: str | None = None,
    tutor_message: str | None = None,
) -> TurnResponse:
    return TurnResponse(
        phase=phase,
        question_number=grading.question_number,
        tutor_message=tutor_message,
        explicit_rating=grading.explicit_rating,
        correct=grading.correct,
        hint_count=grading.hint_count,
        turn_count=grading.turn_count,
        hedging_count=grading.hedging_count,
        reward=grading.reward,
        new_difficulty=grading.new_difficulty,
        inconsistency_flag=grading.inconsistency_flag,
        flag_reason=flag_reason,
    )


def _enter_reflection(
    sess: SessionState,
    pending_grade: PendingGrading,
    grading: GradingResult,
) -> TurnResponse:
    sess.reflection = ReflectionState(
        question=pending_grade.question,
        assessment=pending_grade.assessment,
        grading=grading,
        transcript=list(pending_grade.dialogue_transcript),
    )
    sess.tutor_mode = True
    return _turn_response_from_grading(
        phase="reflection",
        grading=grading,
        flag_reason=pending_grade.assessment.flag_reason,
    )


def run_question(
    sess: SessionState,
    body: QuestionRequest,
    *,
    session_id: str,
    provider_factory,
    metadata_factory,
    program_root: Path,
) -> QuestionResponse:
    if sess.pending_question is not None:
        raise HTTPException(
            status_code=409,
            detail="A question is already pending; submit the learner response first",
        )
    if sess.pending_grading is not None:
        raise HTTPException(
            status_code=409,
            detail="Submit a difficulty rating before loading the next question",
        )
    if sess.reflection is not None:
        raise HTTPException(
            status_code=409,
            detail="Finish reflection or continue to the next question first",
        )
    if sess.question_count >= sess.max_questions:
        raise HTTPException(
            status_code=409,
            detail="Session question limit reached",
        )

    provider, model = provider_factory()
    question_number = sess.question_count + 1
    metadata = metadata_factory()

    try:
        generated = generate_question(
            session_id=session_id,
            question_number=question_number,
            chapter=sess.chapter,
            concept_id=body.concept_id,
            state_path=sess.state_path,
            provider=provider,
            model=model,
            config={},
            metadata=metadata,
            program_root=program_root,
            asked_ids=sess.asked_question_ids,
            focus_mode=sess.focus_mode,
            last_concept_id=sess.active_concept_id,
        )
    except QuestionBankExhaustedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    sess.asked_question_ids.add(generated.question_id)
    if not generated.question_id.startswith("ephemeral:"):
        state.append_asked_id(sess.state_path, generated.question_id)

    sess.pending_question = generated
    sess.active_transcript = seed_dialogue_transcript(generated)
    sess.awaiting_skip_reason = False
    sess.tutor_mode = False
    sess.active_concept_id = generated.concept_id
    sess.question_count = question_number

    return QuestionResponse(
        question_number=generated.question_number,
        concept_id=generated.concept_id,
        concept_label=generated.concept_label,
        concept=generated.concept_label,
        question_type=generated.question_type,
        intended_difficulty=generated.intended_difficulty,
        question_text=generated.question_text,
        question_id=generated.question_id,
    )


def run_turn(
    sess: SessionState,
    body: TurnRequest,
    *,
    session_id: str,
    provider_factory,
    program_root: Path,
) -> TurnResponse:
    learner_message = (body.learner_message or body.learner_response or "").strip()
    skip_reason = (body.skip_reason or "").strip()
    has_message = bool(learner_message)
    has_rating = bool(body.explicit_rating and body.explicit_rating.strip())
    has_skip = body.skip is True
    has_skip_reason = bool(skip_reason)
    has_continue = body.continue_to_next is True

    action_count = sum(
        [has_message, has_rating, has_skip, has_skip_reason, has_continue]
    )
    if action_count != 1:
        raise HTTPException(
            status_code=400,
            detail=(
                "Send exactly one of: learner_message, skip, skip_reason, "
                "explicit_rating, or continue"
            ),
        )

    provider, model = provider_factory()

    if has_continue:
        if sess.reflection is None:
            raise HTTPException(
                status_code=409,
                detail="No reflection in progress; submit a difficulty rating first",
            )
        reflection = sess.reflection
        grading = reflection.grading
        sess.reflection = None
        sess.tutor_mode = False
        phase = (
            "session_complete"
            if grading.question_number >= sess.max_questions
            else "completed"
        )
        return _turn_response_from_grading(
            phase=phase,
            grading=grading,
            flag_reason=reflection.assessment.flag_reason,
        )

    if has_rating:
        rating_raw = body.explicit_rating.strip().lower()  # type: ignore[union-attr]
        if rating_raw not in ("easy", "ok", "hard"):
            raise HTTPException(
                status_code=400,
                detail="explicit_rating must be one of: easy, ok, hard",
            )
        if sess.pending_grading is None:
            raise HTTPException(
                status_code=409,
                detail="No pending grading; complete the question dialogue first",
            )

        pending_grade = sess.pending_grading
        grading = finalize_turn(
            session_id=session_id,
            question=pending_grade.question,
            assessment=pending_grade.assessment,
            explicit_rating=rating_raw,  # type: ignore[arg-type]
            state_path=sess.state_path,
        )
        sess.pending_grading = None
        sess.scalar = grading.new_difficulty
        return _enter_reflection(sess, pending_grade, grading)

    if has_skip:
        if sess.pending_question is None:
            raise HTTPException(
                status_code=409,
                detail="No pending question; call POST /sessions/{id}/question first",
            )
        if sess.pending_grading is not None:
            raise HTTPException(
                status_code=409,
                detail="Submit a difficulty rating before starting a new question",
            )
        if sess.reflection is not None:
            raise HTTPException(
                status_code=409,
                detail="Finish reflection or continue to the next question first",
            )
        sess.awaiting_skip_reason = True
        prompt = skip_prompt_message()
        sess.active_transcript.append({"role": "assistant", "content": prompt})
        return TurnResponse(
            phase="skip_prompt",
            question_number=sess.pending_question.question_number,
            tutor_message=prompt,
        )

    if has_skip_reason:
        if not sess.awaiting_skip_reason or sess.pending_question is None:
            raise HTTPException(
                status_code=409,
                detail="Skip was not requested for the current question",
            )
        sess.active_transcript.append({"role": "user", "content": skip_reason})
        ack = "Understood — we'll move on from this question."
        sess.active_transcript.append({"role": "assistant", "content": ack})
        return _grade_pending_dialogue(
            sess, provider=provider, model=model, program_root=program_root, tutor_message=ack
        )

    if sess.reflection is not None:
        reflection = sess.reflection
        reflection.transcript.append({"role": "user", "content": learner_message})
        turn = tutor_turn(
            question=reflection.question,
            dialogue_transcript=reflection.transcript[:-1],
            learner_message=learner_message,
            chapter=sess.chapter,
            state_path=sess.state_path,
            provider=provider,
            model=model,
            config={},
            program_root=program_root,
        )
        reflection.transcript.append(
            {"role": "assistant", "content": turn.tutor_message}
        )
        return _turn_response_from_grading(
            phase="reflection",
            grading=reflection.grading,
            flag_reason=reflection.assessment.flag_reason,
            tutor_message=turn.tutor_message,
        )

    # Dialogue message
    if sess.pending_question is None:
        raise HTTPException(
            status_code=409,
            detail="No pending question; call POST /sessions/{id}/question first",
        )
    if sess.pending_grading is not None:
        raise HTTPException(
            status_code=409,
            detail="Submit a difficulty rating before continuing dialogue",
        )

    pending = sess.pending_question
    if sess.awaiting_skip_reason:
        sess.active_transcript.append({"role": "user", "content": learner_message})
        ack = "Understood — we'll move on from this question."
        sess.active_transcript.append({"role": "assistant", "content": ack})
        return _grade_pending_dialogue(
            sess, provider=provider, model=model, program_root=program_root, tutor_message=ack
        )

    if is_help_request(learner_message):
        sess.tutor_mode = True

    sess.active_transcript.append({"role": "user", "content": learner_message})

    if sess.tutor_mode:
        turn = tutor_turn(
            question=pending,
            dialogue_transcript=sess.active_transcript[:-1],
            learner_message=learner_message,
            chapter=sess.chapter,
            state_path=sess.state_path,
            provider=provider,
            model=model,
            config={},
            program_root=program_root,
        )
        sess.active_transcript.append({"role": "assistant", "content": turn.tutor_message})

        if turn.question_closed:
            return _grade_pending_dialogue(
                sess,
                provider=provider,
                model=model,
                program_root=program_root,
                tutor_message=turn.tutor_message,
            )

        return TurnResponse(
            phase="dialogue",
            question_number=pending.question_number,
            tutor_message=turn.tutor_message,
            question_closed=False,
        )

    grade = grade_answer_turn(
        question=pending,
        dialogue_transcript=sess.active_transcript[:-1],
        learner_message=learner_message,
        chapter=sess.chapter,
        state_path=sess.state_path,
        provider=provider,
        model=model,
        config={},
        program_root=program_root,
    )
    sess.active_transcript.append({"role": "assistant", "content": grade.tutor_message})
    return _grade_pending_dialogue(
        sess,
        provider=provider,
        model=model,
        program_root=program_root,
        tutor_message=grade.tutor_message,
    )
