"""FastAPI application for the Apore study client."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from apore.api.schemas import (
    BatchRunRequest,
    BatchRunResponse,
    CreateChapterRequest,
    CreateDomainRequest,
    CreateSessionRequest,
    CreateSessionResponse,
    FixtureFetchResponse,
    KnowledgeCatalogResponse,
    ProviderConfigResponse,
    ProviderConfigUpdate,
    QuestionRequest,
    QuestionResponse,
    SessionStateResponse,
    StubCompileResponse,
    TurnRequest,
    TurnResponse,
    UploadSourcesResponse,
)
from apore.config.llm import (
    get_active_model,
    get_active_provider,
    get_provider_config,
    set_provider_config,
)
from apore.fixtures.loader import load_manifest
from apore.knowledge.chapter import ChapterContext, resolve_chapter
from apore.providers import get_provider
from apore.runtime import state
from apore.runtime.core import (
    AssessmentResult,
    GeneratedQuestion,
    assess_response,
    finalize_turn,
    generate_question,
)
from apore.setup.catalog import list_knowledge
from apore.setup.fixtures import fetch_fixture
from apore.setup.paths import chapter_dir, validate_id
from apore.setup.scaffold import scaffold_chapter, scaffold_domain
from apore.setup.stub_compile import stub_compile_chapter
from apore.sim.runner import run_sessions as sim_run_sessions
from apore.sim.student import StudentProfile

PROGRAM_ROOT = Path(__file__).resolve().parent.parent.parent


@dataclass
class PendingGrading:
    """Awaiting learner difficulty rating after LLM assessed correctness."""

    question: GeneratedQuestion
    learner_response: str
    assessment: AssessmentResult
    # Future multi-turn Socratic: append Teacher/learner turns before assess_response.
    dialogue_transcript: list[dict[str, str]] = field(default_factory=list)


@dataclass
class SessionState:
    session_id: str
    knowledge_source: str
    chapter: ChapterContext
    state_path: Path
    scalar: float
    question_count: int
    created_at: str
    pending_question: GeneratedQuestion | None = None
    pending_grading: PendingGrading | None = None
    active_concept_id: str | None = None
    metadata: dict = field(default_factory=dict)


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


def _get_session(session_id: str) -> SessionState:
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail=f"Session {session_id!r} not found")
    return sessions[session_id]


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
    try:
        chapter = resolve_chapter(knowledge_source, PROGRAM_ROOT)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    session_id = str(uuid.uuid4())
    state_path = PROGRAM_ROOT / "sessions" / f"{session_id}.md"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state.initialize(state_path)

    fixture_commit = knowledge_source
    if knowledge_source.startswith("fixture:"):
        fixture_name = knowledge_source.split(":", 1)[1]
        manifest = load_manifest(PROGRAM_ROOT / "apore" / "fixtures" / "manifest.json")
        fixture_commit = manifest["fixtures"].get(fixture_name, {}).get("commit", fixture_name)

    now = datetime.now(timezone.utc).isoformat()
    sessions[session_id] = SessionState(
        session_id=session_id,
        knowledge_source=knowledge_source,
        chapter=chapter,
        state_path=state_path,
        scalar=0.5,
        question_count=0,
        created_at=now,
        metadata={"fixture_commit": fixture_commit},
    )
    return CreateSessionResponse(
        session_id=session_id,
        scalar=0.5,
        created_at=now,
        knowledge_source=knowledge_source,
    )


@app.post("/sessions/{session_id}/question", response_model=QuestionResponse)
def post_question(session_id: str, body: QuestionRequest) -> QuestionResponse:
    sess = _get_session(session_id)
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

    provider_name = get_active_provider()
    if provider_name is None:
        raise HTTPException(
            status_code=503,
            detail="No LLM provider configured. Set API keys via PUT /config/provider",
        )

    provider = get_provider(provider_name)
    model = get_active_model() or "claude-sonnet-4-20250514"
    question_number = sess.question_count + 1
    metadata = _build_metadata(sess)

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
    )
    sess.pending_question = generated
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
    )


@app.post("/sessions/{session_id}/turn", response_model=TurnResponse)
def post_turn(session_id: str, body: TurnRequest) -> TurnResponse:
    sess = _get_session(session_id)

    has_response = bool(body.learner_response and body.learner_response.strip())
    has_rating = bool(body.explicit_rating and body.explicit_rating.strip())

    if has_response and has_rating:
        raise HTTPException(
            status_code=400,
            detail="Send learner_response alone to grade, or explicit_rating alone to finish the turn",
        )
    if not has_response and not has_rating:
        raise HTTPException(
            status_code=400,
            detail="Provide learner_response (grade step) or explicit_rating (rating step)",
        )

    provider_name = get_active_provider()
    if provider_name is None:
        raise HTTPException(
            status_code=503,
            detail="No LLM provider configured. Set API keys via PUT /config/provider",
        )

    provider = get_provider(provider_name)
    model = get_active_model() or "claude-sonnet-4-20250514"
    if has_response:
        if sess.pending_question is None:
            raise HTTPException(
                status_code=409,
                detail="No pending question; call POST /sessions/{id}/question first",
            )
        pending = sess.pending_question
        learner_response = body.learner_response.strip()  # type: ignore[union-attr]
        assessment = assess_response(
            question=pending,
            learner_response=learner_response,
            chapter=sess.chapter,
            state_path=sess.state_path,
            provider=provider,
            model=model,
            config={},
            program_root=PROGRAM_ROOT,
            dialogue_transcript=None,
        )
        sess.pending_grading = PendingGrading(
            question=pending,
            learner_response=learner_response,
            assessment=assessment,
        )
        sess.pending_question = None
        return TurnResponse(
            phase="graded",
            question_number=pending.question_number,
            correct=assessment.correct,
            hint_count=assessment.hint_count,
            turn_count=assessment.turn_count,
            hedging_count=assessment.hedging_count,
            flag_reason=assessment.flag_reason,
        )

    rating_raw = body.explicit_rating.strip().lower()  # type: ignore[union-attr]
    if rating_raw not in ("easy", "ok", "hard"):
        raise HTTPException(
            status_code=400,
            detail="explicit_rating must be one of: easy, ok, hard",
        )
    if sess.pending_grading is None:
        raise HTTPException(
            status_code=409,
            detail="No pending grading; submit learner_response first",
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

    return TurnResponse(
        phase="completed",
        question_number=grading.question_number,
        explicit_rating=grading.explicit_rating,
        correct=grading.correct,
        hint_count=grading.hint_count,
        turn_count=grading.turn_count,
        hedging_count=grading.hedging_count,
        reward=grading.reward,
        new_difficulty=grading.new_difficulty,
        inconsistency_flag=grading.inconsistency_flag,
        flag_reason=pending_grade.assessment.flag_reason,
    )


@app.get("/sessions/{session_id}/state", response_model=SessionStateResponse)
def get_session_state(session_id: str) -> SessionStateResponse:
    sess = _get_session(session_id)
    return SessionStateResponse(
        session_id=session_id,
        scalar=state.read_scalar(sess.state_path),
        question_count=sess.question_count,
        mastery={},
        knowledge_source=sess.knowledge_source,
        active_concept_id=sess.active_concept_id,
    )


@app.get("/setup/knowledge", response_model=KnowledgeCatalogResponse)
def get_setup_knowledge() -> KnowledgeCatalogResponse:
    data = list_knowledge(PROGRAM_ROOT)
    return KnowledgeCatalogResponse(**data)


@app.post("/setup/domains")
def post_setup_domain(body: CreateDomainRequest) -> dict:
    try:
        validate_id(body.domain_id, "domain_id")
        path = scaffold_domain(PROGRAM_ROOT, body.domain_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"domain_id": body.domain_id, "path": str(path)}


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


@app.post("/setup/domains/{domain_id}/chapters/{chapter_id}/sources", response_model=UploadSourcesResponse)
async def post_upload_sources(
    domain_id: str,
    chapter_id: str,
    files: list[UploadFile] = File(...),
) -> UploadSourcesResponse:
    try:
        dest_dir = chapter_dir(PROGRAM_ROOT, domain_id, chapter_id) / "sources"
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not dest_dir.parent.is_dir():
        raise HTTPException(status_code=404, detail="Chapter not found")

    dest_dir.mkdir(parents=True, exist_ok=True)
    uploaded: list[str] = []
    for upload in files:
        name = Path(upload.filename or "upload").name
        if ".." in name or name.startswith("/"):
            raise HTTPException(status_code=400, detail=f"Invalid filename: {name}")
        target = dest_dir / name
        content = await upload.read()
        target.write_bytes(content)
        uploaded.append(name)
    return UploadSourcesResponse(uploaded=uploaded)


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
