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
    QuestionBankEntry,
    QuestionBankGenerateStatus,
    QuestionBankReplaceRequest,
    QuestionBankResponse,
    QuestionRequest,
    QuestionResponse,
    SessionListResponse,
    SessionStateResponse,
    SessionSummary,
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
from apore.fixtures.aliases import fixture_to_domain_chapter
from apore.fixtures.loader import load_manifest
from apore.knowledge.chapter import ChapterContext, load_concept_graph, resolve_chapter
from apore.providers import get_provider
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
from apore.runtime.session_meta import generate_session_title
from apore.setup.catalog import list_knowledge
from apore.setup.fixtures import fetch_fixture
from apore.setup.paths import chapter_dir, validate_id
from apore.setup.scaffold import scaffold_chapter, scaffold_domain
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
from apore.setup.stub_compile import stub_compile_chapter
from apore.runtime.question_bank import QuestionBank
from apore.sim.runner import run_sessions as sim_run_sessions
from apore.sim.student import StudentProfile

PROGRAM_ROOT = Path(__file__).resolve().parent.parent.parent
SESSIONS_DIR = PROGRAM_ROOT / "sessions"


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


def _session_state_response(sess: SessionState) -> SessionStateResponse:
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

    session_id = str(uuid.uuid4())
    state_path = SESSIONS_DIR / f"{session_id}.md"
    state_path.parent.mkdir(parents=True, exist_ok=True)

    fixture_commit = _upstream_commit_for_knowledge_source(knowledge_source)
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
        program_root=PROGRAM_ROOT,
    )

    state.initialize(
        state_path,
        title=title,
        session_id=session_id,
        created_at=now,
        knowledge_source=knowledge_source,
        focus_mode=focus_mode,
        max_questions=body.max_questions,
    )

    sessions[session_id] = SessionState(
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
        asked_question_ids=state.read_asked_ids(state_path),
        metadata={"fixture_commit": fixture_commit},
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


@app.post("/sessions/{session_id}/turn", response_model=TurnResponse)
def post_turn(session_id: str, body: TurnRequest) -> TurnResponse:
    sess = _get_session(session_id)

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
            program_root=PROGRAM_ROOT,
        )
        sess.active_transcript.append({"role": "assistant", "content": turn.tutor_message})

        if turn.question_closed:
            return _grade_pending_dialogue(
                sess,
                provider=provider,
                model=model,
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
        program_root=PROGRAM_ROOT,
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
            summaries.append(
                SessionSummary(
                    session_id=meta["id"],
                    title=title,
                    created_at=meta["created_at"],
                    knowledge_source=meta["knowledge_source"],
                )
            )
    summaries.sort(key=lambda s: s.created_at, reverse=True)
    return SessionListResponse(sessions=summaries)


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
