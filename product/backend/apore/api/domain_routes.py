"""Domain-workspace HTTP surface: /domains."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from apore.api.schemas import (
    CreateSessionResponse,
    QuestionRequest,
    QuestionResponse,
    SeedRequest,
    SeedResponse,
    TurnRequest,
    TurnResponse,
    WorkspaceChapterSummary,
    WorkspaceDomainCreate,
    WorkspaceDomainListResponse,
    WorkspaceDomainSummary,
    WorkspaceSessionCreateRequest,
    WorkspaceSessionDetailResponse,
    WorkspaceSessionListResponse,
    WorkspaceSessionSummary,
)
from apore.api.session_flow import (
    PendingGrading,
    ReflectionState,
    SessionState,
    run_question,
    run_turn,
)
from apore.domains import seed, sessionfile, store
from apore.domains.store import DomainRecord
from apore.knowledge.chapter import resolve_chapter
from apore.runtime import state
from apore.runtime.session_meta import generate_session_title

domain_router = APIRouter(prefix="/domains", tags=["domains"])


def _chapter_summaries(record: DomainRecord) -> list[WorkspaceChapterSummary]:
    chapters_root = store.chapters_dir(record)
    if not chapters_root.is_dir():
        return []
    out: list[WorkspaceChapterSummary] = []
    for chapter in sorted(p for p in chapters_root.iterdir() if p.is_dir()):
        wiki = chapter / "wiki"
        out.append(
            WorkspaceChapterSummary(
                id=chapter.name,
                has_concept_graph=(chapter / "concept-graph.json").is_file(),
                wiki_count=(
                    len([p for p in wiki.iterdir() if p.is_file()])
                    if wiki.is_dir()
                    else 0
                ),
                has_question_bank=(chapter / "question-bank.json").is_file(),
            )
        )
    return out


def _summary(record: DomainRecord) -> WorkspaceDomainSummary:
    chapters = _chapter_summaries(record)
    status = "ready" if any(c.has_concept_graph for c in chapters) else "empty"
    sessions_root = store.sessions_dir(record)
    session_count = (
        len([p for p in sessions_root.iterdir() if p.is_dir()])
        if sessions_root.is_dir()
        else 0
    )
    sources_root = store.sources_dir(record)
    source_files = (
        sorted(p.name for p in sources_root.iterdir() if p.is_file())
        if sources_root.is_dir()
        else []
    )
    return WorkspaceDomainSummary(
        id=record.domain_id,
        name=record.name,
        objective=record.objective,
        teaching_style=record.teaching_style,
        teaching_prompt=record.teaching_prompt,
        model_preference=record.model_preference,
        created_at=record.created_at,
        status=status,
        chapters=chapters,
        session_count=session_count,
        source_files=source_files,
    )


def _invalid_summary(item: store.InvalidDomain) -> WorkspaceDomainSummary:
    return WorkspaceDomainSummary(
        id=item.domain_id,
        name=item.domain_id,
        objective="",
        teaching_style="",
        teaching_prompt="",
        model_preference="",
        created_at="",
        status="invalid",
        reason=item.reason,
    )


@domain_router.get("", response_model=WorkspaceDomainListResponse)
def list_domains() -> WorkspaceDomainListResponse:
    records, invalid = store.list_domains()
    return WorkspaceDomainListResponse(
        domains=[_summary(r) for r in records] + [_invalid_summary(i) for i in invalid]
    )


@domain_router.post("", response_model=WorkspaceDomainSummary, status_code=201)
def create_domain(body: WorkspaceDomainCreate) -> WorkspaceDomainSummary:
    record = store.create_domain(
        name=body.name,
        objective=body.objective,
        teaching_style=body.teaching_style,
        teaching_prompt=body.teaching_prompt,
        model_preference=body.model_preference,
    )
    return _summary(record)


def _load_or_404(domain_id: str) -> DomainRecord:
    try:
        return store.load_domain(domain_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=f"Domain is invalid: {exc}") from exc


@domain_router.get("/{domain_id}", response_model=WorkspaceDomainSummary)
def get_domain(domain_id: str) -> WorkspaceDomainSummary:
    return _summary(_load_or_404(domain_id))


def _ready_chapter_ids(record: DomainRecord) -> list[str]:
    chapters_root = store.chapters_dir(record)
    if not chapters_root.is_dir():
        return []
    return sorted(
        p.name
        for p in chapters_root.iterdir()
        if p.is_dir() and (p / "concept-graph.json").is_file()
    )


def derive_phase(data: dict) -> str:
    resume = data.get("resume") or {}
    if resume.get("pending_grading"):
        return "awaiting_rating"
    if resume.get("reflection"):
        return "reflection"
    if resume.get("pending_question"):
        return "awaiting_answer"
    if data["question_count"] >= data["max_questions"]:
        return "complete"
    return "idle"


@domain_router.post("/{domain_id}/sessions", response_model=CreateSessionResponse)
def create_domain_session(
    domain_id: str, body: WorkspaceSessionCreateRequest
) -> CreateSessionResponse:
    from apore.api import app as app_module

    record = _load_or_404(domain_id)
    ready = _ready_chapter_ids(record)
    if not ready:
        raise HTTPException(status_code=409, detail="Domain has no compiled curriculum")
    chapter_id = body.chapter_id or ready[0]
    if chapter_id not in ready:
        raise HTTPException(status_code=404, detail=f"Chapter {chapter_id!r} not found")
    focus_mode = (body.focus_mode or "adaptive").strip().lower()
    if focus_mode not in ("adaptive", "weak_points"):
        raise HTTPException(
            status_code=400, detail='focus_mode must be "adaptive" or "weak_points"'
        )

    knowledge_source = f"workspace:{domain_id}/{chapter_id}"
    chapter = resolve_chapter(knowledge_source, app_module.PROGRAM_ROOT)

    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    provider_name = app_module._active_provider_name()
    provider = app_module.get_provider(provider_name) if provider_name else None
    model = app_module._active_model_name() or "stub-model"
    title = generate_session_title(
        chapter=chapter,
        knowledge_source=knowledge_source,
        focus_mode=focus_mode,  # type: ignore[arg-type]
        max_questions=body.max_questions,
        provider=provider,
        model=model,
        program_root=app_module.PROGRAM_ROOT,
    )

    state_path = sessionfile.learner_state_path(record, session_id)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state.initialize(
        state_path,
        title=title,
        session_id=session_id,
        created_at=now,
        knowledge_source=knowledge_source,
        focus_mode=focus_mode,
        max_questions=body.max_questions,
    )
    sessionfile.create_session_file(
        record,
        session_id=session_id,
        title=title,
        knowledge_source=knowledge_source,
        chapter_id=chapter_id,
        focus_mode=focus_mode,
        max_questions=body.max_questions,
        created_at=now,
    )

    app_module.sessions[session_id] = SessionState(
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
    )
    return CreateSessionResponse(
        session_id=session_id,
        title=title,
        scalar=0.5,
        created_at=now,
        knowledge_source=knowledge_source,
        focus_mode=focus_mode,
        max_questions=body.max_questions,
    )


@domain_router.get("/{domain_id}/sessions", response_model=WorkspaceSessionListResponse)
def list_domain_sessions(domain_id: str) -> WorkspaceSessionListResponse:
    record = _load_or_404(domain_id)
    return WorkspaceSessionListResponse(
        sessions=[WorkspaceSessionSummary(**s) for s in sessionfile.list_sessions(record)]
    )


@domain_router.get(
    "/{domain_id}/sessions/{session_id}",
    response_model=WorkspaceSessionDetailResponse,
)
def get_domain_session(domain_id: str, session_id: str) -> WorkspaceSessionDetailResponse:
    record = _load_or_404(domain_id)
    try:
        data = sessionfile.load_session_file(record, session_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except sessionfile.SessionFileError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    scalar = state.read_scalar(sessionfile.learner_state_path(record, session_id))
    return WorkspaceSessionDetailResponse(
        session_id=data["session_id"],
        title=data["title"],
        chapter_id=data.get("chapter_id", ""),
        knowledge_source=data["knowledge_source"],
        created_at=data["created_at"],
        updated_at=data["updated_at"],
        question_count=data["question_count"],
        max_questions=data["max_questions"],
        scalar=scalar,
        phase=derive_phase(data),
        transcript=data["transcript"],
    )


def _snapshot(sess: SessionState) -> dict | None:
    if not (
        sess.pending_question or sess.pending_grading or sess.reflection
        or sess.active_transcript or sess.tutor_mode or sess.awaiting_skip_reason
    ):
        return None
    snap: dict = {
        "question_count": sess.question_count,
        "active_concept_id": sess.active_concept_id,
        "tutor_mode": sess.tutor_mode,
        "awaiting_skip_reason": sess.awaiting_skip_reason,
        "active_transcript": list(sess.active_transcript),
        "pending_question": (
            sessionfile.question_to_dict(sess.pending_question)
            if sess.pending_question else None
        ),
        "pending_grading": None,
        "reflection": None,
    }
    if sess.pending_grading:
        snap["pending_grading"] = {
            "question": sessionfile.question_to_dict(sess.pending_grading.question),
            "learner_response": sess.pending_grading.learner_response,
            "assessment": sessionfile.assessment_to_dict(sess.pending_grading.assessment),
            "dialogue_transcript": list(sess.pending_grading.dialogue_transcript),
        }
    if sess.reflection:
        snap["reflection"] = {
            "question": sessionfile.question_to_dict(sess.reflection.question),
            "assessment": sessionfile.assessment_to_dict(sess.reflection.assessment),
            "grading": sessionfile.grading_to_dict(sess.reflection.grading),
            "transcript": list(sess.reflection.transcript),
        }
    return snap


def _rehydrate(record: DomainRecord, session_id: str) -> SessionState:
    from apore.api import app as app_module

    try:
        data = sessionfile.load_session_file(record, session_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except sessionfile.SessionFileError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    state_path = sessionfile.learner_state_path(record, session_id)
    if not state_path.is_file():
        raise HTTPException(status_code=409, detail="learner-state.md missing for session")

    chapter = resolve_chapter(data["knowledge_source"], app_module.PROGRAM_ROOT)
    resume = data.get("resume") or {}
    sess = SessionState(
        session_id=session_id,
        title=data["title"],
        knowledge_source=data["knowledge_source"],
        chapter=chapter,
        state_path=state_path,
        scalar=state.read_scalar(state_path),
        question_count=resume.get("question_count", data["question_count"]),
        created_at=data["created_at"],
        focus_mode=data.get("focus_mode", "adaptive"),
        max_questions=data["max_questions"],
        asked_question_ids=state.read_asked_ids(state_path),
        active_transcript=list(resume.get("active_transcript") or []),
        awaiting_skip_reason=bool(resume.get("awaiting_skip_reason")),
        tutor_mode=bool(resume.get("tutor_mode")),
        active_concept_id=resume.get("active_concept_id"),
    )
    if resume.get("pending_question"):
        sess.pending_question = sessionfile.question_from_dict(resume["pending_question"])
    if resume.get("pending_grading"):
        pg = resume["pending_grading"]
        sess.pending_grading = PendingGrading(
            question=sessionfile.question_from_dict(pg["question"]),
            learner_response=pg["learner_response"],
            assessment=sessionfile.assessment_from_dict(pg["assessment"]),
            dialogue_transcript=list(pg.get("dialogue_transcript") or []),
        )
    if resume.get("reflection"):
        rf = resume["reflection"]
        sess.reflection = ReflectionState(
            question=sessionfile.question_from_dict(rf["question"]),
            assessment=sessionfile.assessment_from_dict(rf["assessment"]),
            grading=sessionfile.grading_from_dict(rf["grading"]),
            transcript=list(rf.get("transcript") or []),
        )
    app_module.sessions[session_id] = sess
    return sess


def _get_or_rehydrate(record: DomainRecord, session_id: str) -> SessionState:
    from apore.api import app as app_module

    sess = app_module.sessions.get(session_id)
    if sess is not None:
        return sess
    return _rehydrate(record, session_id)


def _persist(record: DomainRecord, sess: SessionState, events: list[dict]) -> None:
    if events:
        sessionfile.append_events(record, sess.session_id, events)
    sessionfile.write_resume(
        record, sess.session_id,
        question_count=sess.question_count,
        resume=_snapshot(sess),
    )


@domain_router.post(
    "/{domain_id}/sessions/{session_id}/question", response_model=QuestionResponse
)
def post_domain_question(
    domain_id: str, session_id: str, body: QuestionRequest
) -> QuestionResponse:
    from apore.api import app as app_module

    record = _load_or_404(domain_id)
    sess = _get_or_rehydrate(record, session_id)
    response = run_question(
        sess,
        body,
        session_id=session_id,
        provider_factory=app_module._require_provider,
        metadata_factory=lambda: app_module._build_metadata(sess),
        program_root=app_module.PROGRAM_ROOT,
    )
    _persist(record, sess, [{
        "type": "question",
        "question_number": response.question_number,
        "question_id": response.question_id,
        "concept_id": response.concept_id,
        "concept_label": response.concept_label,
        "question_text": response.question_text,
    }])
    return response


@domain_router.post(
    "/{domain_id}/sessions/{session_id}/turn", response_model=TurnResponse
)
def post_domain_turn(domain_id: str, session_id: str, body: TurnRequest) -> TurnResponse:
    from apore.api import app as app_module

    record = _load_or_404(domain_id)
    sess = _get_or_rehydrate(record, session_id)
    response = run_turn(
        sess,
        body,
        session_id=session_id,
        provider_factory=app_module._require_provider,
        program_root=app_module.PROGRAM_ROOT,
    )

    events: list[dict] = []
    learner_message = (body.learner_message or body.learner_response or "").strip()
    if learner_message:
        events.append({"type": "learner_message", "text": learner_message})
    if body.skip:
        events.append({"type": "system", "text": "Learner requested to skip."})
    if body.skip_reason:
        events.append({"type": "learner_message", "text": body.skip_reason.strip()})
    if response.tutor_message:
        events.append({"type": "tutor_message", "text": response.tutor_message})
    if response.phase == "graded":
        events.append({"type": "graded", "correct": response.correct})
    if response.phase == "reflection" and body.explicit_rating:
        events.append({
            "type": "rating",
            "rating": response.explicit_rating,
            "reward": response.reward,
            "new_difficulty": response.new_difficulty,
        })
    _persist(record, sess, events)
    return response


@domain_router.post("/{domain_id}/seed", response_model=SeedResponse)
def seed_domain_endpoint(domain_id: str, body: SeedRequest) -> SeedResponse:
    from apore.api import app as app_module

    if os.environ.get("APORE_TESTBED") != "1":
        # Invisible outside the testbed — indistinguishable from a missing route.
        raise HTTPException(status_code=404, detail="Not Found")
    record = _load_or_404(domain_id)
    try:
        chapters = seed.seed_domain(
            record,
            program_root=app_module.PROGRAM_ROOT,
            source_domain_id=body.source_domain_id,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SeedResponse(chapters=chapters)


# Non-POST methods (GET/PUT/PATCH/DELETE/HEAD/OPTIONS/anything else) on this
# path are intentionally NOT enumerated here. Starlette resolves the path
# match for any registered route and raises a 405 (with an `Allow: POST`
# header) before reaching a handler for verbs other than POST — enumerating
# stub routes per verb can never cover every possible method (HEAD, OPTIONS,
# and arbitrary/nonstandard verbs from raw ASGI clients all bypass a
# per-verb decorator list). Instead, `app.py` installs an app-wide
# StarletteHTTPException handler that rewrites any 405 on this exact path
# pattern to the same generic 404 this handler returns when ungated, with no
# Allow header — keeping the route indistinguishable from a nonexistent one
# for every HTTP method except the real POST handler.
