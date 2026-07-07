"""Domain-workspace HTTP surface: /domains."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from apore.api.schemas import (
    CreateSessionResponse,
    WorkspaceChapterSummary,
    WorkspaceDomainCreate,
    WorkspaceDomainListResponse,
    WorkspaceDomainSummary,
    WorkspaceSessionCreateRequest,
    WorkspaceSessionDetailResponse,
    WorkspaceSessionListResponse,
    WorkspaceSessionSummary,
)
from apore.api.session_flow import SessionState
from apore.config.llm import get_active_model, get_active_provider
from apore.domains import sessionfile, store
from apore.domains.store import DomainRecord
from apore.knowledge.chapter import resolve_chapter
from apore.providers import get_provider
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
    provider_name = get_active_provider()
    provider = get_provider(provider_name) if provider_name else None
    model = get_active_model() or "stub-model"
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
