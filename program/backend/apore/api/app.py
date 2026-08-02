"""FastAPI application for the Apore study client."""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from apore.api.schemas import (
    AddUrlSourceRequest,
    BatchRunRequest,
    BatchRunResponse,
    BKTParamsView,
    ChapterArtifactStatus,
    CompileStatus,
    ConceptMasteryDeltaView,
    ConceptMasteryView,
    ConceptOrderRequest,
    CreateChapterRequest,
    CreateDomainRequest,
    DomainGraphResponse,
    GraphChapterView,
    GraphConceptView,
    RenameChapterRequest,
    RenameDomainRequest,
    CreateSessionRequest,
    CreateSessionResponse,
    DialogueMessageView,
    EndSessionResponse,
    PendingQuestionView,
    ResumeHistoryItem,
    ResumeSessionResponse,
    FixtureFetchResponse,
    KnowledgeCatalogResponse,
    LearnerMasteryResponse,
    ProviderConfigResponse,
    ProviderConfigUpdate,
    QuestionBankEntry,
    QuestionBankGenerateStatus,
    QuestionBankReplaceRequest,
    QuestionBankResponse,
    QuestionRequest,
    QuestionResponse,
    SessionHistoryMessageView,
    SessionHistoryQuestionView,
    SessionListResponse,
    SessionStateResponse,
    SessionSummary,
    SessionTranscriptResponse,
    SourceEntryView,
    SourceListResponse,
    StubCompileResponse,
    TurnRequest,
    TurnResponse,
    UploadSourcesResponse,
    WikiPreviewResponse,
)
from apore.config.llm import (
    get_active_model,
    get_active_provider,
    get_provider_config,
    set_provider_config,
)
from apore.fixtures.aliases import fixture_to_domain_chapter
from apore.fixtures.loader import load_manifest
from apore.knowledge.chapter import (
    ChapterContext,
    load_concept_graph,
    resolve_chapter,
    resolve_wiki_page,
)
from apore.providers import get_provider
from apore.runtime import state
from apore.runtime.bkt import DEFAULT_PARAMS
from apore.runtime.mastery import (
    ConceptMasteryDelta,
    derive_mastery,
    derive_mastery_delta,
    derive_mastery_floats,
)
from apore.runtime.core import (
    AssessmentResult,
    GeneratedQuestion,
    GradingResult,
    TUTOR_MODE_NOTICE,
    assess_response,
    finalize_turn,
    generate_question,
    grade_answer_turn,
    seed_dialogue_transcript,
    skip_prompt_message,
    tutor_turn,
)
from apore.runtime.intent import is_help_request
from apore.runtime.question_bank import (
    QuestionBank,
    QuestionBankExhaustedError,
    load_question_bank,
)
from apore.runtime.session_meta import fallback_session_title, generate_session_title
from apore.setup.catalog import list_knowledge
from apore.setup.fixtures import fetch_fixture
from apore.setup.paths import chapter_dir, validate_id
from apore.setup.scaffold import (
    delete_chapter,
    delete_domain,
    rename_chapter,
    rename_domain,
    scaffold_chapter,
    scaffold_domain,
)
from apore.setup.question_bank import (
    BankQuestion,
    add_question,
    bank_response_dict,
    chapter_root_for_domain,
    delete_question,
    update_question,
    write_bank,
)
from apore.setup.question_bank_jobs import get_job_status, start_job
from apore.setup import artifacts as artifacts_module
from apore.setup import sources as sources_module
from apore.setup.compile_jobs import (
    approve_compile,
    get_compile_status,
    live_run_tokens,
    load_wiki_preview,
    start_compile,
)
from apore.setup.stub_compile import stub_compile_chapter
from apore.sim.runner import run_sessions as sim_run_sessions
from apore.sim.student import StudentProfile

PROGRAM_ROOT = Path(__file__).resolve().parent.parent.parent
SESSIONS_DIR = PROGRAM_ROOT / "sessions"
logger = logging.getLogger(__name__)


@dataclass
class PendingGrading:
    """Awaiting learner difficulty rating after LLM assessed correctness."""

    question: GeneratedQuestion
    learner_response: str
    assessment: AssessmentResult
    # Future multi-turn Socratic: append Teacher/learner turns before assess_response.
    dialogue_transcript: list[dict[str, str]] = field(default_factory=list)
    assisted: bool = False


@dataclass
class ReflectionState:
    """Optional post-rating tutor chat on a closed question."""

    question: GeneratedQuestion
    assessment: AssessmentResult
    grading: GradingResult
    transcript: list[dict[str, str]] = field(default_factory=list)
    assisted: bool = False


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
    concept_ids: list[str] = field(default_factory=list)
    title_pending: bool = False
    status: str = "active"
    ended_at: str | None = None
    pending_question: GeneratedQuestion | None = None
    pending_grading: PendingGrading | None = None
    reflection: ReflectionState | None = None
    active_transcript: list[dict[str, str]] = field(default_factory=list)
    awaiting_skip_reason: bool = False
    tutor_mode: bool = False
    active_concept_id: str | None = None
    asked_question_ids: set[str] = field(default_factory=set)
    metadata: dict = field(default_factory=dict)
    # Committed completed questions; in-flight item merged on persist.
    conversation_items: list[dict[str, Any]] = field(default_factory=list)


sessions: dict[str, SessionState] = {}

app = FastAPI(title="Apore API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _normalize_knowledge_source(body: CreateSessionRequest) -> str:
    if body.fixture:
        return f"fixture:{body.fixture}"
    return body.knowledge_source


def _normalize_focus_mode(body: CreateSessionRequest) -> str:
    mode = (body.focus_mode or "adaptive").strip().lower()
    if mode not in ("adaptive", "weak_points"):
        raise HTTPException(
            status_code=400,
            detail='focus_mode must be "adaptive" or "weak_points"',
        )
    return mode


def _resolve_session_concept_ids(
    chapter: ChapterContext,
    requested: list[str] | None,
) -> list[str]:
    """Validate and order concept ids for a session; default to all with bank questions."""
    graph = load_concept_graph(chapter)
    if not graph.nodes:
        raise HTTPException(
            status_code=400,
            detail="Chapter has no compiled concept graph",
        )
    bank = load_question_bank(chapter)
    if bank is None or not bank.questions:
        raise HTTPException(
            status_code=400,
            detail="Chapter has no question bank; generate one before starting a session",
        )
    banked = {q.concept_id for q in bank.questions}
    available = [cid for cid in graph.ordered_ids() if cid in banked]
    if not available:
        raise HTTPException(
            status_code=400,
            detail="No concepts in the compiled wiki have bank questions",
        )

    if requested is None:
        return available

    if not requested:
        raise HTTPException(
            status_code=400,
            detail="concept_ids must include at least one concept",
        )

    seen: set[str] = set()
    ordered: list[str] = []
    unknown: list[str] = []
    no_questions: list[str] = []
    for cid in requested:
        if cid in seen:
            raise HTTPException(
                status_code=400,
                detail=f"Duplicate concept_id: {cid!r}",
            )
        seen.add(cid)
        if cid not in graph.nodes:
            unknown.append(cid)
            continue
        if cid not in banked:
            no_questions.append(cid)
            continue
        ordered.append(cid)

    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown concept_ids: {', '.join(unknown)}",
        )
    if no_questions:
        raise HTTPException(
            status_code=400,
            detail=f"Concepts with no bank questions: {', '.join(no_questions)}",
        )
    # Preserve teaching order from the compiled graph.
    available_set = set(ordered)
    return [cid for cid in graph.ordered_ids() if cid in available_set]


def _mastery_delta_views(
    deltas: dict[str, ConceptMasteryDelta],
) -> dict[str, ConceptMasteryDeltaView]:
    return {
        cid: ConceptMasteryDeltaView(
            band_before=d.before.band,
            band_after=d.after.band,
            pct_before=d.before.display_pct,
            pct_after=d.after.display_pct,
            n_observed_session=d.n_observed_session,
        )
        for cid, d in deltas.items()
    }


def _session_mastery_delta(sess: SessionState) -> dict[str, ConceptMasteryDeltaView]:
    graph = load_concept_graph(sess.chapter)
    concept_ids = graph.ordered_ids() or list(sess.concept_ids)
    return _mastery_delta_views(
        derive_mastery_delta(
            SESSIONS_DIR,
            sess.knowledge_source,
            sess.session_id,
            concept_ids,
        )
    )


def _session_state_response(sess: SessionState) -> SessionStateResponse:
    remaining = max(0, sess.max_questions - sess.question_count)
    graph = load_concept_graph(sess.chapter)
    concept_ids = graph.ordered_ids() or list(sess.concept_ids)
    mastery = derive_mastery_floats(
        SESSIONS_DIR,
        sess.knowledge_source,
        concept_ids,
    )
    return SessionStateResponse(
        session_id=sess.session_id,
        title=sess.title,
        scalar=state.read_scalar(sess.state_path),
        question_count=sess.question_count,
        mastery=mastery,
        mastery_delta=_session_mastery_delta(sess),
        knowledge_source=sess.knowledge_source,
        focus_mode=sess.focus_mode,
        max_questions=sess.max_questions,
        questions_remaining=remaining,
        active_concept_id=sess.active_concept_id,
        concept_ids=list(sess.concept_ids),
        title_pending=sess.title_pending,
        status=sess.status,  # type: ignore[arg-type]
        ended_at=sess.ended_at,
    )


def _session_status_from_meta(meta: dict[str, str]) -> tuple[str, str | None]:
    status = meta.get("status") or "active"
    if status not in ("active", "completed", "ended_early"):
        status = "active"
    ended_raw = (meta.get("ended_at") or "").strip()
    return status, ended_raw or None


def _serialize_question(q: GeneratedQuestion) -> dict[str, Any]:
    return {
        "question_number": q.question_number,
        "question_id": q.question_id,
        "concept_id": q.concept_id,
        "concept_label": q.concept_label,
        "question_type": q.question_type,
        "intended_difficulty": q.intended_difficulty,
        "question_text": q.question_text,
        "gen_response": q.gen_response,
    }


def _deserialize_question(data: dict[str, Any]) -> GeneratedQuestion:
    return GeneratedQuestion(
        question_number=int(data["question_number"]),
        question_id=str(data["question_id"]),
        concept_id=str(data["concept_id"]),
        concept_label=str(data["concept_label"]),
        question_type=str(data["question_type"]),
        intended_difficulty=float(data["intended_difficulty"]),
        question_text=str(data["question_text"]),
        gen_response=str(data.get("gen_response") or ""),
    )


def _serialize_assessment(a: AssessmentResult) -> dict[str, Any]:
    return asdict(a)


def _deserialize_assessment(data: dict[str, Any]) -> AssessmentResult:
    return AssessmentResult(
        correct=str(data.get("correct") or "no"),
        hint_count=int(data.get("hint_count") or 0),
        turn_count=int(data.get("turn_count") or 0),
        hedging_count=int(data.get("hedging_count") or 0),
        llm_explicit_rating=str(data.get("llm_explicit_rating") or "ok"),
        llm_inconsistency=bool(data.get("llm_inconsistency") or False),
        flag_reason=data.get("flag_reason"),
    )


def _serialize_grading(g: GradingResult) -> dict[str, Any]:
    return asdict(g)


def _deserialize_grading(data: dict[str, Any]) -> GradingResult:
    return GradingResult(
        question_number=int(data["question_number"]),
        explicit_rating=str(data["explicit_rating"]),
        correct=str(data["correct"]),
        hint_count=int(data["hint_count"]),
        turn_count=int(data["turn_count"]),
        hedging_count=int(data["hedging_count"]),
        reward=float(data["reward"]),
        new_difficulty=float(data["new_difficulty"]),
        inconsistency_flag=bool(data.get("inconsistency_flag") or False),
    )


def _messages_copy(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        {"role": str(m.get("role", "")), "content": str(m.get("content", ""))}
        for m in messages
        if m.get("role") is not None and m.get("content") is not None
    ]


def _question_history_item(
    q: GeneratedQuestion,
    *,
    status: str,
    messages: list[dict[str, str]],
    correct: str | None = None,
    explicit_rating: str | None = None,
    assisted: bool = False,
) -> dict[str, Any]:
    return {
        "question_number": q.question_number,
        "question_id": q.question_id,
        "question_text": q.question_text,
        "concept_id": q.concept_id,
        "concept_label": q.concept_label,
        "correct": correct,
        "explicit_rating": explicit_rating,
        "assisted": assisted,
        "status": status,
        "messages": _messages_copy(messages),
    }


def _in_flight_conversation_item(sess: SessionState) -> dict[str, Any] | None:
    """Structured item for the current unfinished question (if any)."""
    if sess.reflection is not None:
        ref = sess.reflection
        return _question_history_item(
            ref.question,
            status="reflection",
            messages=ref.transcript,
            correct=ref.assessment.correct,
            explicit_rating=ref.grading.explicit_rating,
            assisted=ref.assisted,
        )
    if sess.pending_grading is not None:
        pg = sess.pending_grading
        return _question_history_item(
            pg.question,
            status="awaiting_rating",
            messages=pg.dialogue_transcript,
            correct=pg.assessment.correct,
            assisted=pg.assisted,
        )
    if sess.pending_question is not None:
        return _question_history_item(
            sess.pending_question,
            status="in_progress",
            messages=sess.active_transcript,
            assisted=sess.tutor_mode,
        )
    return None


def _commit_in_flight_to_conversation(sess: SessionState) -> None:
    """Finalize current in-flight question into committed conversation items."""
    item = _in_flight_conversation_item(sess)
    if item is None:
        return
    item["status"] = "completed"
    # Prefer grading fields when leaving reflection; keep assessment correct otherwise.
    if sess.reflection is not None:
        item["correct"] = sess.reflection.assessment.correct
        item["explicit_rating"] = sess.reflection.grading.explicit_rating
        item["assisted"] = sess.reflection.assisted
        item["messages"] = _messages_copy(sess.reflection.transcript)
    elif sess.pending_grading is not None:
        item["correct"] = sess.pending_grading.assessment.correct
        item["assisted"] = sess.pending_grading.assisted
        item["messages"] = _messages_copy(sess.pending_grading.dialogue_transcript)
    # Drop any prior incomplete entry for the same question number.
    qn = item["question_number"]
    sess.conversation_items = [
        existing
        for existing in sess.conversation_items
        if int(existing.get("question_number") or 0) != qn
    ]
    sess.conversation_items.append(item)


def _conversation_view_items(sess: SessionState) -> list[dict[str, Any]]:
    """Committed items plus current in-flight (for disk + transcript API)."""
    items = [dict(item) for item in sess.conversation_items]
    inflight = _in_flight_conversation_item(sess)
    if inflight is None:
        return items
    qn = inflight["question_number"]
    items = [existing for existing in items if int(existing.get("question_number") or 0) != qn]
    items.append(inflight)
    items.sort(key=lambda row: int(row.get("question_number") or 0))
    return items


def _serialize_runtime(sess: SessionState) -> dict[str, Any]:
    pending_grading = None
    if sess.pending_grading is not None:
        pg = sess.pending_grading
        pending_grading = {
            "question": _serialize_question(pg.question),
            "learner_response": pg.learner_response,
            "assessment": _serialize_assessment(pg.assessment),
            "dialogue_transcript": list(pg.dialogue_transcript),
            "assisted": pg.assisted,
        }
    reflection = None
    if sess.reflection is not None:
        ref = sess.reflection
        reflection = {
            "question": _serialize_question(ref.question),
            "assessment": _serialize_assessment(ref.assessment),
            "grading": _serialize_grading(ref.grading),
            "transcript": list(ref.transcript),
            "assisted": ref.assisted,
        }
    return {
        "question_count": sess.question_count,
        "scalar": sess.scalar,
        "awaiting_skip_reason": sess.awaiting_skip_reason,
        "tutor_mode": sess.tutor_mode,
        "active_concept_id": sess.active_concept_id,
        "active_transcript": list(sess.active_transcript),
        "conversation_items": list(sess.conversation_items),
        "pending_question": (
            _serialize_question(sess.pending_question)
            if sess.pending_question is not None
            else None
        ),
        "pending_grading": pending_grading,
        "reflection": reflection,
    }


def _persist_session(sess: SessionState) -> None:
    """Write conversation + runtime snapshot (or clear runtime when ended)."""
    state.write_conversation_items(sess.state_path, _conversation_view_items(sess))
    if sess.status != "active":
        state.write_runtime(sess.state_path, None)
        return
    state.write_runtime(sess.state_path, _serialize_runtime(sess))


def _session_ui_phase(sess: SessionState) -> str:
    if sess.reflection is not None:
        return "reflection"
    if sess.pending_grading is not None:
        return "graded"
    if sess.awaiting_skip_reason:
        return "skip_prompt"
    if sess.pending_question is not None:
        return "dialogue"
    return "idle"


def _session_dialogue_messages(sess: SessionState) -> list[dict[str, str]]:
    if sess.reflection is not None:
        return list(sess.reflection.transcript)
    if sess.pending_grading is not None:
        return list(sess.pending_grading.dialogue_transcript)
    if sess.pending_question is not None:
        return list(sess.active_transcript)
    return []


def _pending_question_view(sess: SessionState) -> PendingQuestionView | None:
    q: GeneratedQuestion | None = None
    if sess.pending_question is not None:
        q = sess.pending_question
    elif sess.pending_grading is not None:
        q = sess.pending_grading.question
    elif sess.reflection is not None:
        q = sess.reflection.question
    if q is None:
        return None
    return PendingQuestionView(
        question_number=q.question_number,
        question_id=q.question_id,
        concept_id=q.concept_id,
        concept_label=q.concept_label,
        concept=q.concept_label,
        question_type=q.question_type,
        intended_difficulty=q.intended_difficulty,
        question_text=q.question_text,
    )


def _resume_history_items(sess: SessionState) -> list[ResumeHistoryItem]:
    """Build Study sidebar history from graded completed conversation items."""
    log_by_qn: dict[int, dict[str, str]] = {}
    for row in state.parse_question_log(sess.state_path):
        try:
            qn = int(row.get("Q#") or 0)
        except (TypeError, ValueError):
            continue
        if qn > 0:
            log_by_qn[qn] = row

    history: list[ResumeHistoryItem] = []
    for item in sess.conversation_items:
        status = str(item.get("status") or "completed")
        if status != "completed":
            continue
        try:
            qn = int(item.get("question_number") or 0)
        except (TypeError, ValueError):
            continue
        if qn <= 0:
            continue
        log = log_by_qn.get(qn, {})
        rating = str(item.get("explicit_rating") or log.get("explicit_rating") or "").strip()
        if not rating:
            # Abandoned in-flight commits (end early) have no rating — skip.
            continue
        correct = str(item.get("correct") or log.get("correct") or "no").strip() or "no"
        reward: float | None = None
        raw_reward = log.get("reward_R")
        if raw_reward not in (None, ""):
            try:
                reward = float(raw_reward)
            except (TypeError, ValueError):
                reward = None
        history.append(
            ResumeHistoryItem(
                question_number=qn,
                question_text=str(item.get("question_text") or ""),
                explicit_rating=rating,
                correct=correct,
                reward=reward,
            )
        )
    history.sort(key=lambda h: h.question_number)
    return history


def _resume_session_response(sess: SessionState) -> ResumeSessionResponse:
    base = _session_state_response(sess)
    correct = hint_count = turn_count = hedging_count = None
    flag_reason = assisted = explicit_rating = reward = new_difficulty = None
    if sess.pending_grading is not None:
        a = sess.pending_grading.assessment
        correct = a.correct
        hint_count = a.hint_count
        turn_count = a.turn_count
        hedging_count = a.hedging_count
        flag_reason = a.flag_reason
        assisted = sess.pending_grading.assisted
    elif sess.reflection is not None:
        a = sess.reflection.assessment
        g = sess.reflection.grading
        correct = a.correct
        hint_count = a.hint_count
        turn_count = a.turn_count
        hedging_count = a.hedging_count
        flag_reason = a.flag_reason
        assisted = sess.reflection.assisted
        explicit_rating = g.explicit_rating
        reward = g.reward
        new_difficulty = g.new_difficulty
    return ResumeSessionResponse(
        **base.model_dump(),
        phase=_session_ui_phase(sess),  # type: ignore[arg-type]
        pending_question=_pending_question_view(sess),
        dialogue_messages=[
            DialogueMessageView(role=m["role"], content=m["content"])
            for m in _session_dialogue_messages(sess)
            if m.get("role") and m.get("content") is not None
        ],
        awaiting_skip_reason=sess.awaiting_skip_reason,
        tutor_mode=sess.tutor_mode,
        history=_resume_history_items(sess),
        correct=correct,
        hint_count=hint_count,
        turn_count=turn_count,
        hedging_count=hedging_count,
        flag_reason=flag_reason,
        assisted=assisted,
        explicit_rating=explicit_rating,
        reward=reward,
        new_difficulty=new_difficulty,
    )


def _apply_runtime_to_session(sess: SessionState, runtime: dict[str, Any]) -> None:
    """Restore in-flight fields from a persisted runtime snapshot."""
    sess.question_count = int(runtime.get("question_count") or sess.question_count)
    if "scalar" in runtime:
        try:
            sess.scalar = float(runtime["scalar"])
        except (TypeError, ValueError):
            pass
    sess.awaiting_skip_reason = bool(runtime.get("awaiting_skip_reason") or False)
    sess.tutor_mode = bool(runtime.get("tutor_mode") or False)
    active_concept = runtime.get("active_concept_id")
    sess.active_concept_id = str(active_concept) if active_concept else None
    transcript = runtime.get("active_transcript") or []
    sess.active_transcript = (
        [{"role": str(m.get("role", "")), "content": str(m.get("content", ""))} for m in transcript]
        if isinstance(transcript, list)
        else []
    )
    conv_items = runtime.get("conversation_items")
    if isinstance(conv_items, list):
        sess.conversation_items = [item for item in conv_items if isinstance(item, dict)]
    elif isinstance(runtime.get("conversation_md"), str):
        # Legacy runtime field; ignore prose — completed items come from disk.
        sess.conversation_items = state.read_conversation_items(sess.state_path)
        sess.conversation_items = [
            item
            for item in sess.conversation_items
            if item.get("status") == "completed"
        ]

    pq = runtime.get("pending_question")
    sess.pending_question = _deserialize_question(pq) if isinstance(pq, dict) else None

    pg = runtime.get("pending_grading")
    if isinstance(pg, dict) and isinstance(pg.get("question"), dict):
        sess.pending_grading = PendingGrading(
            question=_deserialize_question(pg["question"]),
            learner_response=str(pg.get("learner_response") or ""),
            assessment=_deserialize_assessment(pg.get("assessment") or {}),
            dialogue_transcript=[
                {"role": str(m.get("role", "")), "content": str(m.get("content", ""))}
                for m in (pg.get("dialogue_transcript") or [])
                if isinstance(m, dict)
            ],
            assisted=bool(pg.get("assisted") or False),
        )
    else:
        sess.pending_grading = None

    ref = runtime.get("reflection")
    if isinstance(ref, dict) and isinstance(ref.get("question"), dict):
        sess.reflection = ReflectionState(
            question=_deserialize_question(ref["question"]),
            assessment=_deserialize_assessment(ref.get("assessment") or {}),
            grading=_deserialize_grading(ref.get("grading") or {}),
            transcript=[
                {"role": str(m.get("role", "")), "content": str(m.get("content", ""))}
                for m in (ref.get("transcript") or [])
                if isinstance(m, dict)
            ],
            assisted=bool(ref.get("assisted") or False),
        )
    else:
        sess.reflection = None


def _reactivate_session_on_disk(path: Path) -> None:
    """Clear ended_early lifecycle fields so the session can continue."""
    state.write_session_status(path, status="active", ended_at="")


def _hydrate_session_from_disk(session_id: str) -> SessionState:
    """Rebuild a SessionState from its persisted markdown file.

    Accepts ``active`` and ``ended_early`` (reactivated to active). Rejects
    ``completed`` sessions.
    """
    path = SESSIONS_DIR / f"{session_id}.md"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Session not found")
    meta = state.read_session_meta(path)
    status, ended_at = _session_status_from_meta(meta)
    if status == "completed":
        raise HTTPException(
            status_code=409,
            detail="Session is completed; start a new session to continue",
        )
    if status not in ("active", "ended_early"):
        raise HTTPException(
            status_code=409,
            detail=f"Session is {status}; start a new session to continue",
        )
    if status == "ended_early":
        _reactivate_session_on_disk(path)
        status = "active"
        ended_at = None

    knowledge_source = meta.get("knowledge_source") or ""
    if not knowledge_source:
        raise HTTPException(status_code=400, detail="Session missing knowledge_source")
    try:
        chapter = resolve_chapter(knowledge_source, PROGRAM_ROOT)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        max_questions = int(meta.get("max_questions") or "10")
    except ValueError:
        max_questions = 10
    focus_mode = meta.get("focus_mode") or "adaptive"
    if focus_mode not in ("adaptive", "weak_points"):
        focus_mode = "adaptive"
    concept_ids = state.parse_concept_ids(meta.get("concept_ids"))
    try:
        scalar = state.read_scalar(path)
    except ValueError:
        scalar = 0.5

    log_rows = state.parse_question_log(path)
    question_count = len(log_rows)

    sess = SessionState(
        session_id=session_id,
        title=state.read_title(path),
        knowledge_source=knowledge_source,
        chapter=chapter,
        state_path=path,
        scalar=scalar,
        question_count=question_count,
        created_at=meta.get("created_at") or "",
        focus_mode=focus_mode,
        max_questions=max_questions,
        concept_ids=concept_ids,
        status=status,
        ended_at=ended_at,
        asked_question_ids=state.read_asked_ids(path),
        metadata={
            "fixture_commit": _upstream_commit_for_knowledge_source(knowledge_source),
        },
    )
    runtime = state.read_runtime(path)
    if runtime:
        _apply_runtime_to_session(sess, runtime)
    else:
        # Between questions (or never started): Conversation JSON is committed-only.
        sess.conversation_items = [
            item
            for item in state.read_conversation_items(path)
            if item.get("status") == "completed"
        ]
    return sess


def _clear_in_flight_question(sess: SessionState) -> None:
    """Drop unfinished question state without writing a question-log row.

    Rated questions already persist via finalize_turn; only roll back the
    in-memory count when the current question was never rated.
    """
    unfinished = sess.pending_question is not None or sess.pending_grading is not None
    if unfinished and sess.question_count > 0:
        sess.question_count -= 1
    sess.pending_question = None
    sess.pending_grading = None
    sess.reflection = None
    sess.active_transcript = []
    sess.awaiting_skip_reason = False
    sess.tutor_mode = False
    sess.active_concept_id = None


def _mark_session_ended(
    sess: SessionState,
    *,
    status: str,
    ended_at: str | None = None,
) -> str:
    """Persist lifecycle status and clear in-flight question state."""
    _commit_in_flight_to_conversation(sess)
    stamp = ended_at or datetime.now(timezone.utc).isoformat()
    state.write_session_status(sess.state_path, status=status, ended_at=stamp)
    sess.status = status
    sess.ended_at = stamp
    _clear_in_flight_question(sess)
    _persist_session(sess)
    return stamp


def _require_active_session(sess: SessionState) -> None:
    if sess.status != "active":
        raise HTTPException(
            status_code=409,
            detail=f"Session is {sess.status}; start a new session to continue",
        )


def _run_session_title_job(
    session_id: str,
    *,
    chapter: ChapterContext,
    knowledge_source: str,
    focus_mode: str,
    max_questions: int,
    concept_ids: list[str],
    state_path: Path,
    provider_name: str,
    model: str,
) -> None:
    """Generate an LLM title in the background and update session state + markdown."""
    try:
        provider = get_provider(provider_name)
        title = generate_session_title(
            chapter=chapter,
            knowledge_source=knowledge_source,
            focus_mode=focus_mode,  # type: ignore[arg-type]
            max_questions=max_questions,
            provider=provider,
            model=model,
            program_root=PROGRAM_ROOT,
            concept_ids=concept_ids,
        )
        sess = sessions.get(session_id)
        if sess is None:
            return
        sess.title = title
        state.write_title(state_path, title)
    except Exception:
        logger.exception("Background session title job failed for %s", session_id)
    finally:
        sess = sessions.get(session_id)
        if sess is not None:
            sess.title_pending = False


def _start_session_title_job(sess: SessionState) -> bool:
    """Spawn a daemon title job when a provider is configured. Returns whether pending."""
    provider_name = get_active_provider()
    if provider_name is None:
        sess.title_pending = False
        return False
    model = get_active_model() or "stub-model"
    sess.title_pending = True
    thread = threading.Thread(
        target=_run_session_title_job,
        kwargs={
            "session_id": sess.session_id,
            "chapter": sess.chapter,
            "knowledge_source": sess.knowledge_source,
            "focus_mode": sess.focus_mode,
            "max_questions": sess.max_questions,
            "concept_ids": list(sess.concept_ids),
            "state_path": sess.state_path,
            "provider_name": provider_name,
            "model": model,
        },
        daemon=True,
        name=f"session-title-{sess.session_id[:8]}",
    )
    thread.start()
    return True


def _upstream_commit_for_knowledge_source(knowledge_source: str) -> str:
    manifest = load_manifest(PROGRAM_ROOT / "apore" / "fixtures" / "manifest.json")
    fixtures = manifest.get("fixtures", {})
    if knowledge_source.startswith("fixture:"):
        name = knowledge_source.split(":", 1)[1]
        return fixtures.get(name, {}).get("commit", knowledge_source)
    if knowledge_source.startswith("domain:"):
        rest = knowledge_source.split(":", 1)[1]
        if "/" not in rest:
            return knowledge_source
        domain_id, chapter_id = rest.split("/", 1)
        for spec in fixtures.values():
            if spec.get("domain_id") == domain_id and spec.get("chapter_id") == chapter_id:
                return spec.get("commit", knowledge_source)
    return knowledge_source


def _get_session(session_id: str) -> SessionState:
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail=f"Session {session_id!r} not found")
    return sessions[session_id]


def _domain_knowledge_prefix(domain_id: str) -> str:
    return f"domain:{domain_id}/"


def _rewrite_domain_knowledge_source(knowledge_source: str, old_domain_id: str, new_domain_id: str) -> str | None:
    prefix = _domain_knowledge_prefix(old_domain_id)
    if not knowledge_source.startswith(prefix):
        return None
    chapter_id = knowledge_source[len(prefix) :]
    if not chapter_id or "/" in chapter_id:
        return None
    return f"domain:{new_domain_id}/{chapter_id}"


def _migrate_sessions_for_domain_rename(old_domain_id: str, new_domain_id: str) -> int:
    """Rewrite persisted and in-memory session knowledge sources after a domain rename."""
    if old_domain_id == new_domain_id:
        return 0

    updated = 0
    if SESSIONS_DIR.is_dir():
        for path in SESSIONS_DIR.glob("*.md"):
            try:
                uuid.UUID(path.stem)
            except ValueError:
                continue
            try:
                meta = state.read_session_meta(path)
            except OSError:
                continue
            old_source = meta.get("knowledge_source")
            if not old_source:
                continue
            new_source = _rewrite_domain_knowledge_source(old_source, old_domain_id, new_domain_id)
            if new_source is None:
                continue
            if state.rewrite_knowledge_source(path, old_source, new_source):
                updated += 1

    for sess in list(sessions.values()):
        new_source = _rewrite_domain_knowledge_source(
            sess.knowledge_source, old_domain_id, new_domain_id
        )
        if new_source is None:
            continue
        try:
            chapter = resolve_chapter(new_source, PROGRAM_ROOT)
        except FileNotFoundError:
            continue
        sess.knowledge_source = new_source
        sess.chapter = chapter

    return updated


def _delete_sessions_for_domain(domain_id: str) -> int:
    """Delete persisted and in-memory sessions that belong to a domain."""
    prefix = _domain_knowledge_prefix(domain_id)
    deleted = 0

    if SESSIONS_DIR.is_dir():
        for path in list(SESSIONS_DIR.glob("*.md")):
            try:
                uuid.UUID(path.stem)
            except ValueError:
                continue
            try:
                meta = state.read_session_meta(path)
            except OSError:
                continue
            knowledge_source = meta.get("knowledge_source", "")
            if not knowledge_source.startswith(prefix):
                continue
            try:
                path.unlink()
            except OSError:
                continue
            deleted += 1
            sessions.pop(path.stem, None)

    for session_id, sess in list(sessions.items()):
        if sess.knowledge_source.startswith(prefix):
            sessions.pop(session_id, None)

    return deleted


def _require_provider():
    provider_name = get_active_provider()
    if provider_name is None:
        raise HTTPException(
            status_code=503,
            detail="No LLM provider configured. Set API keys via PUT /config/provider",
        )
    provider = get_provider(provider_name)
    model = get_active_model() or "claude-sonnet-4-20250514"
    return provider, model


def _grade_pending_dialogue(
    sess: SessionState,
    *,
    provider,
    model: str,
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
    assisted = sess.tutor_mode
    assessment = assess_response(
        question=pending,
        learner_response=last_user,
        chapter=sess.chapter,
        state_path=sess.state_path,
        provider=provider,
        model=model,
        config={},
        program_root=PROGRAM_ROOT,
        dialogue_transcript=transcript,
    )
    sess.pending_grading = PendingGrading(
        question=pending,
        learner_response=last_user,
        assessment=assessment,
        dialogue_transcript=transcript,
        assisted=assisted,
    )
    sess.pending_question = None
    sess.active_transcript = []
    sess.awaiting_skip_reason = False
    return TurnResponse(
        phase="graded",
        question_number=pending.question_number,
        tutor_message=tutor_message,
        mode="tutor" if assisted else "answer",
        correct=assessment.correct,
        hint_count=assessment.hint_count,
        turn_count=assessment.turn_count,
        hedging_count=assessment.hedging_count,
        flag_reason=assessment.flag_reason,
        assisted=assisted,
    )


def _turn_response_from_grading(
    *,
    phase: str,
    grading: GradingResult,
    flag_reason: str | None = None,
    tutor_message: str | None = None,
    mode: str = "answer",
    assisted: bool = False,
) -> TurnResponse:
    return TurnResponse(
        phase=phase,
        question_number=grading.question_number,
        tutor_message=tutor_message,
        mode=mode,  # type: ignore[arg-type]
        explicit_rating=grading.explicit_rating,
        correct=grading.correct,
        hint_count=grading.hint_count,
        turn_count=grading.turn_count,
        hedging_count=grading.hedging_count,
        reward=grading.reward,
        new_difficulty=grading.new_difficulty,
        inconsistency_flag=grading.inconsistency_flag,
        flag_reason=flag_reason,
        assisted=assisted,
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
        assisted=pending_grade.assisted,
    )
    sess.tutor_mode = True
    return _turn_response_from_grading(
        phase="reflection",
        grading=grading,
        flag_reason=pending_grade.assessment.flag_reason,
        mode="tutor",
        assisted=pending_grade.assisted,
    )


def _resolve_domain_chapter_root(domain_id: str, chapter_id: str) -> Path:
    try:
        root = chapter_root_for_domain(PROGRAM_ROOT, domain_id, chapter_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not root.is_dir():
        raise HTTPException(status_code=404, detail="Chapter not found")
    return root


def _resolve_upstream_chapter_root(name: str) -> Path:
    """Chapter root for a manifest upstream template (e.g. apore-lite → discrete-math)."""
    manifest = load_manifest(PROGRAM_ROOT / "apore" / "fixtures" / "manifest.json")
    spec = manifest.get("fixtures", {}).get(name)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"Unknown upstream template {name!r}")
    domain_id = spec.get("domain_id")
    chapter_id = spec.get("chapter_id")
    if not domain_id or not chapter_id:
        mapped = fixture_to_domain_chapter(name)
        if mapped is None:
            raise HTTPException(
                status_code=404,
                detail=f"No domain mapping for upstream template {name!r}",
            )
        domain_id, chapter_id = mapped
    return _resolve_domain_chapter_root(domain_id, chapter_id)


def _graph_for_chapter_root(chapter_root: Path) -> object:
    chapter = ChapterContext(
        knowledge_source="",
        chapter_root=chapter_root,
        display_name="",
    )
    return load_concept_graph(chapter)


def _provider_factory() -> object:
    provider_name = get_active_provider()
    if provider_name is None:
        raise ValueError("No LLM provider configured")
    return get_provider(provider_name)


def _start_question_bank_generation(
    chapter_root: Path, knowledge_source: str
) -> QuestionBankGenerateStatus:
    provider, model = _require_provider()
    status = artifacts_module.chapter_artifact_status(
        chapter_root,
        current_source_hash=sources_module.source_hash(chapter_root),
        live_run_tokens=live_run_tokens(),
    )
    if not status["is_approved"]:
        raise HTTPException(
            status_code=409,
            detail="Approve the compiled wiki before generating questions.",
        )
    if status["is_stale"]:
        raise HTTPException(
            status_code=409,
            detail="Sources changed since approval. Recompile and approve before generating.",
        )
    graph = _graph_for_chapter_root(chapter_root)
    if not graph.nodes:
        raise HTTPException(status_code=400, detail="concept-graph.json has no nodes")

    job = start_job(
        chapter_root,
        provider=provider,
        model=model,
        program_root=PROGRAM_ROOT,
        knowledge_source=knowledge_source,
        concepts_total=len(graph.nodes),
        provider_factory=_provider_factory,
    )
    return QuestionBankGenerateStatus(**job.snapshot())


def _question_bank_generation_status(chapter_root: Path) -> QuestionBankGenerateStatus:
    return QuestionBankGenerateStatus(**get_job_status(chapter_root))


def _build_metadata(sess: SessionState) -> dict:
    return {
        **sess.metadata,
        "provider": get_active_provider() or "stub",
        "model": get_active_model() or "stub-model",
        "knowledge_source": sess.knowledge_source,
    }


@app.post("/sessions", response_model=CreateSessionResponse)
def create_session(body: CreateSessionRequest) -> CreateSessionResponse:
    knowledge_source = _normalize_knowledge_source(body)
    focus_mode = _normalize_focus_mode(body)
    try:
        chapter = resolve_chapter(knowledge_source, PROGRAM_ROOT)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    concept_ids = _resolve_session_concept_ids(chapter, body.concept_ids)

    session_id = str(uuid.uuid4())
    state_path = SESSIONS_DIR / f"{session_id}.md"
    state_path.parent.mkdir(parents=True, exist_ok=True)

    fixture_commit = _upstream_commit_for_knowledge_source(knowledge_source)
    now = datetime.now(timezone.utc).isoformat()

    title = fallback_session_title(
        knowledge_source=knowledge_source,
        focus_mode=focus_mode,  # type: ignore[arg-type]
    )

    state.initialize(
        state_path,
        title=title,
        session_id=session_id,
        created_at=now,
        knowledge_source=knowledge_source,
        focus_mode=focus_mode,
        max_questions=body.max_questions,
        concept_ids=concept_ids,
    )

    sess = SessionState(
        session_id=session_id,
        title=title,
        knowledge_source=knowledge_source,
        chapter=chapter,
        state_path=state_path,
        scalar=0.5,
        question_count=0,
        created_at=now,
        focus_mode=focus_mode,
        max_questions=body.max_questions,
        concept_ids=concept_ids,
        asked_question_ids=state.read_asked_ids(state_path),
        metadata={"fixture_commit": fixture_commit},
    )
    sessions[session_id] = sess
    # Persist before spawning the title job so the background writer cannot
    # race with the initial Conversation/Runtime snapshot.
    _persist_session(sess)
    title_pending = _start_session_title_job(sess)
    return CreateSessionResponse(
        session_id=session_id,
        title=title,
        scalar=0.5,
        created_at=now,
        knowledge_source=knowledge_source,
        focus_mode=focus_mode,
        max_questions=body.max_questions,
        concept_ids=concept_ids,
        title_pending=title_pending,
    )


@app.post("/sessions/{session_id}/question", response_model=QuestionResponse)
def post_question(session_id: str, body: QuestionRequest) -> QuestionResponse:
    sess = _get_session(session_id)
    _require_active_session(sess)
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

    bank = load_question_bank(sess.chapter)
    has_bank = bank is not None and bool(bank.questions)
    if not has_bank:
        raise HTTPException(
            status_code=400,
            detail="Chapter has no question bank; generate one before starting a session",
        )

    # Bank selection is local; provider is only needed for LLM dialogue/grading later.
    provider_name = get_active_provider()
    provider = get_provider(provider_name) if provider_name else None
    model = get_active_model() or "claude-sonnet-4-20250514"
    if provider is None:
        # Stub provider object is not required for bank path; use a no-op only if needed.
        from apore.providers.stub import StubProvider

        provider = StubProvider()
        model = "stub-model"

    question_number = sess.question_count + 1
    metadata = _build_metadata(sess)
    allowed = set(sess.concept_ids) if sess.concept_ids else None
    graph = load_concept_graph(sess.chapter)
    mastery = derive_mastery_floats(
        SESSIONS_DIR,
        sess.knowledge_source,
        graph.ordered_ids() or list(sess.concept_ids),
    )

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
            program_root=PROGRAM_ROOT,
            mastery=mastery,
            asked_ids=sess.asked_question_ids,
            focus_mode=sess.focus_mode,
            last_concept_id=sess.active_concept_id,
            allowed_concept_ids=allowed,
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
    _persist_session(sess)

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


@app.post("/sessions/{session_id}/turn", response_model=TurnResponse)
def post_turn(session_id: str, body: TurnRequest) -> TurnResponse:
    sess = _get_session(session_id)
    _require_active_session(sess)
    try:
        return _post_turn_inner(sess, body)
    finally:
        # Keep disk conversation/runtime in sync after every mutation path.
        if session_id in sessions:
            _persist_session(sess)


def _post_turn_inner(sess: SessionState, body: TurnRequest) -> TurnResponse:
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

    provider, model = _require_provider()

    if has_continue:
        if sess.reflection is None:
            raise HTTPException(
                status_code=409,
                detail="No reflection in progress; submit a difficulty rating first",
            )
        reflection = sess.reflection
        grading = reflection.grading
        _commit_in_flight_to_conversation(sess)
        sess.reflection = None
        sess.tutor_mode = False
        if grading.question_number >= sess.max_questions:
            _mark_session_ended(sess, status="completed")
            phase = "session_complete"
        else:
            phase = "completed"
        return _turn_response_from_grading(
            phase=phase,
            grading=grading,
            flag_reason=reflection.assessment.flag_reason,
            assisted=reflection.assisted,
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
            session_id=sess.session_id,
            question=pending_grade.question,
            assessment=pending_grade.assessment,
            explicit_rating=rating_raw,  # type: ignore[arg-type]
            state_path=sess.state_path,
            assisted=pending_grade.assisted,
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
            sess, provider=provider, model=model, tutor_message=ack
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
            program_root=PROGRAM_ROOT,
        )
        reflection.transcript.append(
            {"role": "assistant", "content": turn.tutor_message}
        )
        return _turn_response_from_grading(
            phase="reflection",
            grading=reflection.grading,
            flag_reason=reflection.assessment.flag_reason,
            tutor_message=turn.tutor_message,
            mode="tutor",
            assisted=reflection.assisted,
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
            sess, provider=provider, model=model, tutor_message=ack
        )

    entered_tutor = False
    if is_help_request(learner_message):
        if not sess.tutor_mode:
            entered_tutor = True
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
            program_root=PROGRAM_ROOT,
        )
        tutor_message = turn.tutor_message
        if entered_tutor:
            tutor_message = f"{TUTOR_MODE_NOTICE}\n\n{tutor_message}"
        sess.active_transcript.append({"role": "assistant", "content": tutor_message})

        if turn.question_closed:
            return _grade_pending_dialogue(
                sess,
                provider=provider,
                model=model,
                tutor_message=tutor_message,
            )

        return TurnResponse(
            phase="dialogue",
            question_number=pending.question_number,
            tutor_message=tutor_message,
            question_closed=False,
            mode="tutor",
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
        program_root=PROGRAM_ROOT,
    )

    if grade.help_request:
        sess.tutor_mode = True
        # Discard the escape-marker reply; re-run under tutor-turn rules.
        turn = tutor_turn(
            question=pending,
            dialogue_transcript=sess.active_transcript[:-1],
            learner_message=learner_message,
            chapter=sess.chapter,
            state_path=sess.state_path,
            provider=provider,
            model=model,
            config={},
            program_root=PROGRAM_ROOT,
        )
        tutor_message = f"{TUTOR_MODE_NOTICE}\n\n{turn.tutor_message}"
        sess.active_transcript.append({"role": "assistant", "content": tutor_message})

        if turn.question_closed:
            return _grade_pending_dialogue(
                sess,
                provider=provider,
                model=model,
                tutor_message=tutor_message,
            )

        return TurnResponse(
            phase="dialogue",
            question_number=pending.question_number,
            tutor_message=tutor_message,
            question_closed=False,
            mode="tutor",
        )

    sess.active_transcript.append({"role": "assistant", "content": grade.tutor_message})
    return _grade_pending_dialogue(
        sess,
        provider=provider,
        model=model,
        tutor_message=grade.tutor_message,
    )


@app.get("/sessions/{session_id}/state", response_model=SessionStateResponse)
def get_session_state(session_id: str) -> SessionStateResponse:
    sess = _get_session(session_id)
    return _session_state_response(sess)


@app.post("/sessions/{session_id}/resume", response_model=ResumeSessionResponse)
def resume_session(session_id: str) -> ResumeSessionResponse:
    """Hydrate a resumable session from disk into memory (idempotent if already live).

    Resumable: ``active`` or ``ended_early`` (reactivated). ``completed`` → 409.
    """
    try:
        uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Session not found")

    if session_id in sessions:
        sess = sessions[session_id]
        if sess.status == "completed":
            raise HTTPException(
                status_code=409,
                detail="Session is completed; start a new session to continue",
            )
        if sess.status == "ended_early":
            _reactivate_session_on_disk(sess.state_path)
            sess.status = "active"
            sess.ended_at = None
        _require_active_session(sess)
        return _resume_session_response(sess)

    sess = _hydrate_session_from_disk(session_id)
    sessions[session_id] = sess
    return _resume_session_response(sess)


@app.get("/learner/mastery", response_model=LearnerMasteryResponse)
def get_learner_mastery(knowledge_source: str) -> LearnerMasteryResponse:
    """Derive-on-read BKT mastery for all concepts in a chapter."""
    source = (knowledge_source or "").strip()
    if not source:
        raise HTTPException(status_code=400, detail="knowledge_source is required")
    try:
        chapter = resolve_chapter(source, PROGRAM_ROOT)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    graph = load_concept_graph(chapter)
    concept_ids = graph.ordered_ids()
    derived = derive_mastery(SESSIONS_DIR, chapter.knowledge_source, concept_ids)
    params = DEFAULT_PARAMS
    return LearnerMasteryResponse(
        knowledge_source=chapter.knowledge_source,
        params=BKTParamsView(
            p_L0=params.p_L0,
            p_T=params.p_T,
            p_G=params.p_G,
            p_S=params.p_S,
            p_F=params.p_F,
        ),
        concepts={
            cid: ConceptMasteryView(
                p_mastery=m.p_mastery,
                band=m.band,
                n_observed=m.n_observed,
                display_pct=m.display_pct,
            )
            for cid, m in derived.items()
        },
    )


@app.get("/domains/{domain_id}/graph", response_model=DomainGraphResponse)
def get_domain_graph(domain_id: str) -> DomainGraphResponse:
    """Domain-level knowledge graph: chapters, concepts, prerequisite edges,
    and derive-on-read BKT mastery per concept. Read-only; adds no storage."""
    try:
        validate_id(domain_id, "domain_id")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    chapters_dir = PROGRAM_ROOT / "domains" / domain_id / "chapters"
    if not chapters_dir.is_dir():
        raise HTTPException(status_code=404, detail="Domain not found")

    chapters: list[GraphChapterView] = []
    for chapter_path in sorted(chapters_dir.iterdir()):
        if not chapter_path.is_dir():
            continue
        chapter_id = chapter_path.name
        knowledge_source = f"domain:{domain_id}/{chapter_id}"
        chapter = resolve_chapter(knowledge_source, PROGRAM_ROOT)
        graph = load_concept_graph(chapter)
        ordered_ids = graph.ordered_ids()
        derived = derive_mastery(SESSIONS_DIR, knowledge_source, ordered_ids)

        concepts: list[GraphConceptView] = []
        proficient = 0
        mastery_sum = 0.0
        for cid in ordered_ids:
            node = graph.get(cid)
            mastery = derived[cid]
            if mastery.band == "proficient":
                proficient += 1
            mastery_sum += mastery.p_mastery or 0.0
            wiki_page = resolve_wiki_page(
                chapter.wiki_dir, cid, node.source_file if node else None
            )
            concepts.append(
                GraphConceptView(
                    id=cid,
                    label=graph.label_for(cid),
                    depth=node.depth if node else 0,
                    p_mastery=mastery.p_mastery,
                    band=mastery.band,
                    n_observed=mastery.n_observed,
                    display_pct=mastery.display_pct,
                    has_wiki=wiki_page is not None,
                )
            )

        mastery_pct = round(100 * mastery_sum / len(concepts)) if concepts else 0
        edges = [
            {
                "source": e.get("source"),
                "target": e.get("target"),
                "relation": e.get("relation", "prerequisite_of"),
            }
            for e in graph.edges
            if e.get("relation") == "prerequisite_of"
            and isinstance(e.get("source"), str)
            and isinstance(e.get("target"), str)
        ]
        chapters.append(
            GraphChapterView(
                id=chapter_id,
                knowledge_source=knowledge_source,
                has_concept_graph=chapter.concept_graph_path.is_file(),
                mastery_pct=mastery_pct,
                concepts_proficient=proficient,
                concepts_total=len(concepts),
                concepts=concepts,
                edges=edges,
            )
        )

    return DomainGraphResponse(domain_id=domain_id, chapters=chapters)


@app.post("/sessions/{session_id}/end", response_model=EndSessionResponse)
def end_session(session_id: str) -> EndSessionResponse:
    """End an active session early; keep completed questions, drop unfinished ones."""
    sess = _get_session(session_id)
    if sess.status == "ended_early" and sess.ended_at:
        # Idempotent: ending again returns the same terminal state.
        return EndSessionResponse(
            session_id=sess.session_id,
            status="ended_early",
            ended_at=sess.ended_at,
            title=sess.title,
            knowledge_source=sess.knowledge_source,
            question_count=sess.question_count,
            max_questions=sess.max_questions,
            scalar=state.read_scalar(sess.state_path),
            mastery_delta=_session_mastery_delta(sess),
        )
    if sess.status != "active":
        raise HTTPException(
            status_code=409,
            detail=f"Session is already {sess.status}",
        )
    ended_at = _mark_session_ended(sess, status="ended_early")
    return EndSessionResponse(
        session_id=sess.session_id,
        status="ended_early",
        ended_at=ended_at,
        title=sess.title,
        knowledge_source=sess.knowledge_source,
        question_count=sess.question_count,
        max_questions=sess.max_questions,
        scalar=state.read_scalar(sess.state_path),
        mastery_delta=_session_mastery_delta(sess),
    )


@app.get("/sessions", response_model=SessionListResponse)
def list_sessions() -> SessionListResponse:
    """Summaries of persisted sessions, newest first (spec: sidebar histories)."""
    summaries: list[SessionSummary] = []
    if SESSIONS_DIR.is_dir():
        for path in SESSIONS_DIR.glob("*.md"):
            try:
                uuid.UUID(path.stem)
            except ValueError:
                continue
            try:
                meta = state.read_session_meta(path)
                title = state.read_title(path)
            except OSError:
                continue
            if not all(k in meta for k in ("id", "created_at", "knowledge_source")):
                continue
            status, ended_at = _session_status_from_meta(meta)
            summaries.append(
                SessionSummary(
                    session_id=meta["id"],
                    title=title,
                    created_at=meta["created_at"],
                    knowledge_source=meta["knowledge_source"],
                    status=status,  # type: ignore[arg-type]
                    ended_at=ended_at,
                )
            )
    summaries.sort(key=lambda s: s.created_at, reverse=True)
    return SessionListResponse(sessions=summaries)


def _history_question_views(items: list[dict[str, Any]]) -> list[SessionHistoryQuestionView]:
    views: list[SessionHistoryQuestionView] = []
    for item in items:
        try:
            qn = int(item.get("question_number") or 0)
        except (TypeError, ValueError):
            continue
        status_raw = str(item.get("status") or "completed")
        if status_raw not in ("completed", "in_progress", "awaiting_rating", "reflection"):
            status_raw = "completed"
        messages = [
            SessionHistoryMessageView(
                role=str(m.get("role") or ""),
                content=str(m.get("content") or ""),
            )
            for m in (item.get("messages") or [])
            if isinstance(m, dict)
        ]
        views.append(
            SessionHistoryQuestionView(
                question_number=qn,
                question_id=str(item.get("question_id") or ""),
                question_text=str(item.get("question_text") or ""),
                concept_id=str(item.get("concept_id") or ""),
                concept_label=str(item.get("concept_label") or ""),
                correct=item.get("correct"),
                explicit_rating=item.get("explicit_rating"),
                assisted=bool(item.get("assisted") or False),
                status=status_raw,  # type: ignore[arg-type]
                messages=messages,
            )
        )
    views.sort(key=lambda q: q.question_number)
    return views


@app.get("/sessions/{session_id}/transcript", response_model=SessionTranscriptResponse)
def get_session_transcript(session_id: str) -> SessionTranscriptResponse:
    """Read-only transcript of a persisted session (works after server restart)."""
    try:
        uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Session not found")
    path = SESSIONS_DIR / f"{session_id}.md"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Session not found")
    meta = state.read_session_meta(path)
    try:
        max_questions = int(meta.get("max_questions", "0"))
    except ValueError:
        max_questions = 0
    status, ended_at = _session_status_from_meta(meta)
    if session_id in sessions:
        question_items = _conversation_view_items(sessions[session_id])
    else:
        question_items = state.read_conversation_items(path)
    return SessionTranscriptResponse(
        session_id=session_id,
        title=state.read_title(path),
        created_at=meta.get("created_at", ""),
        knowledge_source=meta.get("knowledge_source", ""),
        focus_mode=meta.get("focus_mode", "adaptive"),
        max_questions=max_questions,
        status=status,  # type: ignore[arg-type]
        ended_at=ended_at,
        body=path.read_text(encoding="utf-8"),
        questions=_history_question_views(question_items),
    )


@app.get("/setup/knowledge", response_model=KnowledgeCatalogResponse)
def get_setup_knowledge() -> KnowledgeCatalogResponse:
    data = list_knowledge(PROGRAM_ROOT)
    return KnowledgeCatalogResponse(**data)


@app.post("/setup/domains")
def post_setup_domain(body: CreateDomainRequest) -> dict:
    try:
        validate_id(body.domain_id, "domain_id")
        path = scaffold_domain(
            PROGRAM_ROOT,
            body.domain_id,
            name=body.name,
            scope=body.scope,
            goal=body.goal,
            tutor_style=body.tutor_style,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"domain_id": body.domain_id, "path": str(path)}


@app.patch("/setup/domains/{domain_id}")
def patch_setup_domain(domain_id: str, body: RenameDomainRequest) -> dict:
    try:
        path = rename_domain(PROGRAM_ROOT, domain_id, body.domain_id)
        sessions_updated = _migrate_sessions_for_domain_rename(domain_id, body.domain_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "domain_id": body.domain_id,
        "path": str(path),
        "sessions_updated": sessions_updated,
    }


@app.delete("/setup/domains/{domain_id}")
def delete_setup_domain(domain_id: str) -> dict:
    try:
        validate_id(domain_id, "domain_id")
        sessions_deleted = _delete_sessions_for_domain(domain_id)
        delete_domain(PROGRAM_ROOT, domain_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "domain_id": domain_id,
        "deleted": True,
        "sessions_deleted": sessions_deleted,
    }


@app.post("/setup/domains/{domain_id}/chapters")
def post_setup_chapter(domain_id: str, body: CreateChapterRequest) -> dict:
    try:
        path = scaffold_chapter(PROGRAM_ROOT, domain_id, body.chapter_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "domain_id": domain_id,
        "chapter_id": body.chapter_id,
        "knowledge_source": f"domain:{domain_id}/{body.chapter_id}",
        "path": str(path),
    }


@app.patch("/setup/domains/{domain_id}/chapters/{chapter_id}")
def patch_setup_chapter(domain_id: str, chapter_id: str, body: RenameChapterRequest) -> dict:
    try:
        path = rename_chapter(PROGRAM_ROOT, domain_id, chapter_id, body.chapter_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "domain_id": domain_id,
        "chapter_id": body.chapter_id,
        "knowledge_source": f"domain:{domain_id}/{body.chapter_id}",
        "path": str(path),
    }


@app.delete("/setup/domains/{domain_id}/chapters/{chapter_id}")
def delete_setup_chapter(domain_id: str, chapter_id: str) -> dict:
    try:
        delete_chapter(PROGRAM_ROOT, domain_id, chapter_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"domain_id": domain_id, "chapter_id": chapter_id, "deleted": True}


def _chapter_root_or_404(domain_id: str, chapter_id: str) -> Path:
    try:
        root = chapter_dir(PROGRAM_ROOT, domain_id, chapter_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not root.is_dir():
        raise HTTPException(status_code=404, detail="Chapter not found")
    return root


@app.get(
    "/setup/domains/{domain_id}/chapters/{chapter_id}/sources",
    response_model=SourceListResponse,
)
def get_chapter_sources(domain_id: str, chapter_id: str) -> SourceListResponse:
    root = _chapter_root_or_404(domain_id, chapter_id)
    return SourceListResponse(
        sources=[SourceEntryView(**s) for s in sources_module.list_sources(root)]
    )


@app.post("/setup/domains/{domain_id}/chapters/{chapter_id}/sources", response_model=UploadSourcesResponse)
async def post_upload_sources(
    domain_id: str,
    chapter_id: str,
    files: list[UploadFile] = File(...),
) -> UploadSourcesResponse:
    root = _chapter_root_or_404(domain_id, chapter_id)
    uploaded: list[str] = []
    for upload in files:
        name = Path(upload.filename or "upload").name
        content = await upload.read()
        try:
            sources_module.add_file_source(
                root, name, content, media_type=upload.content_type
            )
        except sources_module.SourceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        uploaded.append(name)
    return UploadSourcesResponse(uploaded=uploaded)


@app.post(
    "/setup/domains/{domain_id}/chapters/{chapter_id}/sources/url",
    response_model=SourceEntryView,
)
def post_url_source(
    domain_id: str, chapter_id: str, body: AddUrlSourceRequest
) -> SourceEntryView:
    root = _chapter_root_or_404(domain_id, chapter_id)
    try:
        entry = sources_module.add_url_source(root, body.url)
    except sources_module.SourceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SourceEntryView(**entry)


@app.delete(
    "/setup/domains/{domain_id}/chapters/{chapter_id}/sources/{source_id}",
    response_model=SourceListResponse,
)
def delete_chapter_source(
    domain_id: str, chapter_id: str, source_id: str
) -> SourceListResponse:
    root = _chapter_root_or_404(domain_id, chapter_id)
    try:
        sources_module.delete_source(root, source_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SourceListResponse(
        sources=[SourceEntryView(**s) for s in sources_module.list_sources(root)]
    )


@app.get(
    "/setup/domains/{domain_id}/chapters/{chapter_id}/artifact",
    response_model=ChapterArtifactStatus,
)
def get_chapter_artifact(domain_id: str, chapter_id: str) -> ChapterArtifactStatus:
    root = _chapter_root_or_404(domain_id, chapter_id)
    status = artifacts_module.chapter_artifact_status(
        root,
        current_source_hash=sources_module.source_hash(root),
        live_run_tokens=live_run_tokens(),
    )
    return ChapterArtifactStatus(**status)


@app.post(
    "/setup/domains/{domain_id}/chapters/{chapter_id}/compile",
    response_model=CompileStatus,
    status_code=202,
)
def post_compile_chapter(domain_id: str, chapter_id: str) -> CompileStatus:
    root = _chapter_root_or_404(domain_id, chapter_id)
    provider, model = _require_provider()
    try:
        status = start_compile(
            root, provider=provider, model=model, program_root=PROGRAM_ROOT
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CompileStatus(**status)


@app.get(
    "/setup/domains/{domain_id}/chapters/{chapter_id}/compile/status",
    response_model=CompileStatus,
)
def get_compile_chapter_status(domain_id: str, chapter_id: str) -> CompileStatus:
    root = _chapter_root_or_404(domain_id, chapter_id)
    return CompileStatus(**get_compile_status(root))


@app.post(
    "/setup/domains/{domain_id}/chapters/{chapter_id}/compile/approve",
    response_model=ChapterArtifactStatus,
)
def post_approve_compile(domain_id: str, chapter_id: str) -> ChapterArtifactStatus:
    root = _chapter_root_or_404(domain_id, chapter_id)
    try:
        status = approve_compile(root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ChapterArtifactStatus(**status)


@app.get(
    "/setup/domains/{domain_id}/chapters/{chapter_id}/wiki",
    response_model=WikiPreviewResponse,
)
def get_chapter_wiki(
    domain_id: str, chapter_id: str, source: str = "staging"
) -> WikiPreviewResponse:
    root = _chapter_root_or_404(domain_id, chapter_id)
    try:
        preview = load_wiki_preview(root, source)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return WikiPreviewResponse(**preview)


@app.put(
    "/setup/domains/{domain_id}/chapters/{chapter_id}/concept-order",
    response_model=WikiPreviewResponse,
)
def put_chapter_concept_order(
    domain_id: str,
    chapter_id: str,
    body: ConceptOrderRequest,
    source: str = "published",
) -> WikiPreviewResponse:
    root = _chapter_root_or_404(domain_id, chapter_id)
    if source == "staging":
        directory = artifacts_module.staging_dir(root)
    elif source == "published":
        directory = root
    else:
        raise HTTPException(status_code=400, detail="source must be 'staging' or 'published'")
    try:
        artifacts_module.write_teaching_order(directory, body.order)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except artifacts_module.ArtifactValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        preview = load_wiki_preview(root, source)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return WikiPreviewResponse(**preview)


@app.post(
    "/setup/domains/{domain_id}/chapters/{chapter_id}/compile-stub",
    response_model=StubCompileResponse,
)
def post_compile_stub(domain_id: str, chapter_id: str) -> StubCompileResponse:
    try:
        root = chapter_dir(PROGRAM_ROOT, domain_id, chapter_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not root.is_dir():
        raise HTTPException(status_code=404, detail="Chapter not found")

    try:
        summary = stub_compile_chapter(root)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return StubCompileResponse(**summary)


@app.get(
    "/setup/domains/{domain_id}/chapters/{chapter_id}/question-bank",
    response_model=QuestionBankResponse,
)
def get_domain_question_bank(domain_id: str, chapter_id: str) -> QuestionBankResponse:
    root = _resolve_domain_chapter_root(domain_id, chapter_id)
    graph = _graph_for_chapter_root(root)
    return QuestionBankResponse(**bank_response_dict(root, graph))


@app.put(
    "/setup/domains/{domain_id}/chapters/{chapter_id}/question-bank",
    response_model=QuestionBankResponse,
)
def put_domain_question_bank(
    domain_id: str,
    chapter_id: str,
    body: QuestionBankReplaceRequest,
) -> QuestionBankResponse:
    root = _resolve_domain_chapter_root(domain_id, chapter_id)
    graph = _graph_for_chapter_root(root)
    bank = QuestionBank(
        version=body.version,
        questions=[
            BankQuestion(
                id=q.id,
                concept_id=q.concept_id,
                type=q.type.lower(),
                intended_difficulty=q.intended_difficulty,
                text=q.text.strip(),
            )
            for q in body.questions
        ],
    )
    try:
        write_bank(root, bank, graph)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return QuestionBankResponse(**bank_response_dict(root, graph))


@app.post(
    "/setup/domains/{domain_id}/chapters/{chapter_id}/question-bank/questions",
    response_model=QuestionBankResponse,
)
def post_domain_question(
    domain_id: str,
    chapter_id: str,
    body: QuestionBankEntry,
) -> QuestionBankResponse:
    root = _resolve_domain_chapter_root(domain_id, chapter_id)
    graph = _graph_for_chapter_root(root)
    entry = BankQuestion(
        id=body.id,
        concept_id=body.concept_id,
        type=body.type.lower(),
        intended_difficulty=body.intended_difficulty,
        text=body.text.strip(),
    )
    try:
        add_question(root, entry, graph=graph)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return QuestionBankResponse(**bank_response_dict(root, graph))


@app.patch(
    "/setup/domains/{domain_id}/chapters/{chapter_id}/question-bank/questions/{question_id}",
    response_model=QuestionBankResponse,
)
def patch_domain_question(
    domain_id: str,
    chapter_id: str,
    question_id: str,
    body: QuestionBankEntry,
) -> QuestionBankResponse:
    root = _resolve_domain_chapter_root(domain_id, chapter_id)
    graph = _graph_for_chapter_root(root)
    try:
        update_question(
            root,
            question_id,
            graph=graph,
            concept_id=body.concept_id,
            type=body.type.lower(),
            intended_difficulty=body.intended_difficulty,
            text=body.text.strip(),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return QuestionBankResponse(**bank_response_dict(root, graph))


@app.delete(
    "/setup/domains/{domain_id}/chapters/{chapter_id}/question-bank/questions/{question_id}",
    response_model=QuestionBankResponse,
)
def delete_domain_question(
    domain_id: str, chapter_id: str, question_id: str
) -> QuestionBankResponse:
    root = _resolve_domain_chapter_root(domain_id, chapter_id)
    graph = _graph_for_chapter_root(root)
    try:
        delete_question(root, question_id, graph=graph)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return QuestionBankResponse(**bank_response_dict(root, graph))


@app.post(
    "/setup/domains/{domain_id}/chapters/{chapter_id}/question-bank/generate",
    response_model=QuestionBankGenerateStatus,
    status_code=202,
)
def post_generate_domain_question_bank(
    domain_id: str, chapter_id: str
) -> QuestionBankGenerateStatus:
    root = _resolve_domain_chapter_root(domain_id, chapter_id)
    knowledge_source = f"domain:{domain_id}/{chapter_id}"
    return _start_question_bank_generation(root, knowledge_source)


@app.get(
    "/setup/domains/{domain_id}/chapters/{chapter_id}/question-bank/generate/status",
    response_model=QuestionBankGenerateStatus,
)
def get_generate_domain_question_bank_status(
    domain_id: str, chapter_id: str
) -> QuestionBankGenerateStatus:
    root = _resolve_domain_chapter_root(domain_id, chapter_id)
    return _question_bank_generation_status(root)


@app.get("/setup/fixtures/{name}/question-bank", response_model=QuestionBankResponse)
def get_fixture_question_bank(name: str) -> QuestionBankResponse:
    root = _resolve_upstream_chapter_root(name)
    graph = _graph_for_chapter_root(root)
    return QuestionBankResponse(**bank_response_dict(root, graph))


@app.put("/setup/fixtures/{name}/question-bank", response_model=QuestionBankResponse)
def put_fixture_question_bank(
    name: str, body: QuestionBankReplaceRequest
) -> QuestionBankResponse:
    root = _resolve_upstream_chapter_root(name)
    graph = _graph_for_chapter_root(root)
    bank = QuestionBank(
        version=body.version,
        questions=[
            BankQuestion(
                id=q.id,
                concept_id=q.concept_id,
                type=q.type.lower(),
                intended_difficulty=q.intended_difficulty,
                text=q.text.strip(),
            )
            for q in body.questions
        ],
    )
    try:
        write_bank(root, bank, graph)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return QuestionBankResponse(**bank_response_dict(root, graph))


@app.post(
    "/setup/fixtures/{name}/question-bank/questions",
    response_model=QuestionBankResponse,
)
def post_fixture_question(name: str, body: QuestionBankEntry) -> QuestionBankResponse:
    root = _resolve_upstream_chapter_root(name)
    graph = _graph_for_chapter_root(root)
    entry = BankQuestion(
        id=body.id,
        concept_id=body.concept_id,
        type=body.type.lower(),
        intended_difficulty=body.intended_difficulty,
        text=body.text.strip(),
    )
    try:
        add_question(root, entry, graph=graph)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return QuestionBankResponse(**bank_response_dict(root, graph))


@app.patch(
    "/setup/fixtures/{name}/question-bank/questions/{question_id}",
    response_model=QuestionBankResponse,
)
def patch_fixture_question(
    name: str, question_id: str, body: QuestionBankEntry
) -> QuestionBankResponse:
    root = _resolve_upstream_chapter_root(name)
    graph = _graph_for_chapter_root(root)
    try:
        update_question(
            root,
            question_id,
            graph=graph,
            concept_id=body.concept_id,
            type=body.type.lower(),
            intended_difficulty=body.intended_difficulty,
            text=body.text.strip(),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return QuestionBankResponse(**bank_response_dict(root, graph))


@app.delete(
    "/setup/fixtures/{name}/question-bank/questions/{question_id}",
    response_model=QuestionBankResponse,
)
def delete_fixture_question(name: str, question_id: str) -> QuestionBankResponse:
    root = _resolve_upstream_chapter_root(name)
    graph = _graph_for_chapter_root(root)
    try:
        delete_question(root, question_id, graph=graph)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return QuestionBankResponse(**bank_response_dict(root, graph))


@app.post(
    "/setup/fixtures/{name}/question-bank/generate",
    response_model=QuestionBankGenerateStatus,
    status_code=202,
)
def post_generate_fixture_question_bank(name: str) -> QuestionBankGenerateStatus:
    root = _resolve_upstream_chapter_root(name)
    manifest = load_manifest(PROGRAM_ROOT / "apore" / "fixtures" / "manifest.json")
    spec = manifest.get("fixtures", {}).get(name, {})
    domain_id = spec.get("domain_id", "discrete-math")
    chapter_id = spec.get("chapter_id", "01-set-theory")
    knowledge_source = f"domain:{domain_id}/{chapter_id}"
    return _start_question_bank_generation(root, knowledge_source)


@app.get(
    "/setup/fixtures/{name}/question-bank/generate/status",
    response_model=QuestionBankGenerateStatus,
)
def get_generate_fixture_question_bank_status(name: str) -> QuestionBankGenerateStatus:
    root = _resolve_upstream_chapter_root(name)
    return _question_bank_generation_status(root)


@app.post("/setup/fixtures/{name}/fetch", response_model=FixtureFetchResponse)
def post_fetch_fixture(name: str) -> FixtureFetchResponse:
    try:
        result = fetch_fixture(PROGRAM_ROOT, name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return FixtureFetchResponse(**result)


@app.get("/config/provider", response_model=ProviderConfigResponse)
def get_provider_config_endpoint() -> ProviderConfigResponse:
    cfg = get_provider_config()
    return ProviderConfigResponse(
        anthropic_api_key_set=cfg["anthropic_api_key_set"],
        anthropic_api_key_hint=cfg["anthropic_api_key_hint"],
        nim_api_key_set=cfg["nim_api_key_set"],
        nim_api_key_hint=cfg["nim_api_key_hint"],
        model=cfg["model"],
        active_provider=cfg["active_provider"],
        active_model=cfg["active_model"],
    )


@app.put("/config/provider", response_model=ProviderConfigResponse)
def put_provider_config(body: ProviderConfigUpdate) -> ProviderConfigResponse:
    cfg = set_provider_config(
        anthropic_api_key=body.anthropic_api_key,
        nim_api_key=body.nim_api_key,
        model=body.model,
    )
    return ProviderConfigResponse(
        anthropic_api_key_set=cfg["anthropic_api_key_set"],
        anthropic_api_key_hint=cfg["anthropic_api_key_hint"],
        nim_api_key_set=cfg["nim_api_key_set"],
        nim_api_key_hint=cfg["nim_api_key_hint"],
        model=cfg["model"],
        active_provider=cfg["active_provider"],
        active_model=cfg["active_model"],
    )


@app.post("/runs/batch", response_model=BatchRunResponse)
def post_batch_run(body: BatchRunRequest) -> BatchRunResponse:
    run_id = str(uuid.uuid4())
    profile = StudentProfile(
        ability=body.profile.get("ability", 0.5),
        misconceptions=body.profile.get("misconceptions", []),
        seed=body.profile.get("seed", 42),
    )
    provider_name = get_active_provider() or "stub"
    model = get_active_model() or "stub-model"

    sim_run_sessions(
        num_sessions=body.sessions,
        questions_per_session=10,
        profile=profile,
        provider_name=provider_name,
        model=model,
        program_root=PROGRAM_ROOT,
        knowledge_source="domain:_pytest/01-intro",
    )
    return BatchRunResponse(run_id=run_id, status="completed")
