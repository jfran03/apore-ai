"""FastAPI application for the Apore study client."""

from __future__ import annotations

import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.exception_handlers import http_exception_handler
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from apore.api.domain_routes import domain_router
from apore.api.session_flow import (  # noqa: F401 - re-exported for tests/compat
    PendingGrading,
    ReflectionState,
    SessionState,
    run_question,
    run_turn,
    session_state_response,
)
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
from apore.fixtures.aliases import fixture_to_domain_chapter
from apore.fixtures.loader import load_manifest
from apore.knowledge.chapter import ChapterContext, load_concept_graph, resolve_chapter
from apore.providers import get_provider
from apore.runtime import state
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

sessions: dict[str, SessionState] = {}

app = FastAPI(title="Apore API", version="0.1.0")

# Dev runs the Vite client on :5173; the packaged desktop app serves the webview
# from a tauri:// (and https://tauri.localhost) origin. Allow both.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "tauri://localhost",
        "https://tauri.localhost",
    ],
    allow_origin_regex=r"^(tauri://localhost|https://tauri\.localhost|http://localhost:\d+)$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(domain_router)

# Path pattern for the testbed-gated seed endpoint (see domain_routes.py).
# domain_id is a single path segment (no slashes), so this matches only the
# exact route and nothing else (e.g. not /domains/{id}/sessions).
_SEED_PATH_RE = re.compile(r"^/domains/[^/]+/seed$")


@app.exception_handler(StarletteHTTPException)
async def _mask_seed_endpoint_405(request: Request, exc: StarletteHTTPException):
    """Rewrite 405s on the seed path to a generic 404, for every HTTP verb.

    `/domains/{domain_id}/seed` is only ever registered for POST. Starlette's
    router still matches the path for any other method (GET, HEAD, OPTIONS,
    PROPFIND, ...) and raises a 405 with an `Allow: POST` header before any
    handler runs — which leaks the route's existence, and the Allow header
    actively confirms POST is valid, even when the endpoint is gated off via
    APORE_TESTBED. No enumeration of per-verb stub routes can fully close
    this (HEAD/OPTIONS and arbitrary custom verbs from raw ASGI clients
    bypass any fixed list), so instead we intercept the 405 generically here
    and return the same 404 shape the POST handler itself returns when
    ungated, with no Allow header — making the path indistinguishable from a
    nonexistent route for every method except the real POST handler.
    """
    if exc.status_code == 405 and _SEED_PATH_RE.match(request.url.path):
        return JSONResponse({"detail": "Not Found"}, status_code=404)
    return await http_exception_handler(request, exc)


@app.get("/health")
def health() -> dict:
    """Lightweight reachability check used by the desktop shell on startup."""
    return {
        "status": "ok",
        "service": "apore-backend",
        "version": "0.1.0",
        "testbed": os.environ.get("APORE_TESTBED") == "1",
    }


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
    state_path = PROGRAM_ROOT / "sessions" / f"{session_id}.md"
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
    return run_question(
        sess,
        body,
        session_id=session_id,
        provider_factory=_require_provider,
        metadata_factory=lambda: _build_metadata(sess),
        program_root=PROGRAM_ROOT,
    )


@app.post("/sessions/{session_id}/turn", response_model=TurnResponse)
def post_turn(session_id: str, body: TurnRequest) -> TurnResponse:
    sess = _get_session(session_id)
    return run_turn(
        sess,
        body,
        session_id=session_id,
        provider_factory=_require_provider,
        program_root=PROGRAM_ROOT,
    )


@app.get("/sessions/{session_id}/state", response_model=SessionStateResponse)
def get_session_state(session_id: str) -> SessionStateResponse:
    return session_state_response(_get_session(session_id))


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
