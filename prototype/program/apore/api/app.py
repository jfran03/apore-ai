"""FastAPI application — thin JSON layer over apore.runtime.core."""

from __future__ import annotations

import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from apore.api.schemas import (
    BatchRunRequest,
    BatchRunResponse,
    CreateSessionRequest,
    CreateSessionResponse,
    ProviderConfig,
    SessionStateResponse,
    TurnRequest,
    TurnResponse,
)
from apore.fixtures.loader import get_grounding_paths
from apore.providers.stub import StubProvider
from apore.runtime import state as state_io
from apore.runtime.core import run_question_cycle
from apore.runtime.paths import get_program_root

# ---------------------------------------------------------------------------
# In-memory stores
# ---------------------------------------------------------------------------

@dataclass
class SessionState:
    id: str
    state_path: Path
    provider_name: str
    model: str
    fixture_name: str
    question_count: int
    created_at: str
    _tmpdir: object = field(default=None, repr=False)  # keep tempdir alive


sessions: dict[str, SessionState] = {}

# Global provider config (mutable at runtime via PUT /config/provider)
_provider_config: ProviderConfig = ProviderConfig(provider="stub", model="stub")

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="Apore API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_session(session_id: str) -> SessionState:
    sess = sessions.get(session_id)
    if sess is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id!r} not found")
    return sess


def _make_provider(provider_name: str):
    """Return a provider instance. Falls back to StubProvider for 'stub'."""
    if provider_name == "stub":
        return StubProvider()
    from apore.providers import get_provider
    return get_provider(provider_name)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/sessions", response_model=CreateSessionResponse)
def create_session(body: CreateSessionRequest) -> CreateSessionResponse:
    session_id = str(uuid.uuid4())
    tmpdir = tempfile.mkdtemp(prefix="apore-session-")
    state_path = Path(tmpdir) / "learner-state.md"
    state_io.initialize(state_path)
    scalar = state_io.read_scalar(state_path)
    created_at = datetime.now(timezone.utc).isoformat()

    sessions[session_id] = SessionState(
        id=session_id,
        state_path=state_path,
        provider_name=body.provider,
        model=body.model,
        fixture_name=body.fixture,
        question_count=0,
        created_at=created_at,
        _tmpdir=tmpdir,
    )

    return CreateSessionResponse(
        session_id=session_id,
        scalar=scalar,
        created_at=created_at,
    )


@app.post("/sessions/{session_id}/turn", response_model=TurnResponse)
def session_turn(session_id: str, body: TurnRequest) -> TurnResponse:
    sess = _get_session(session_id)

    program_root = get_program_root()
    grounding_paths = get_grounding_paths(
        sess.fixture_name, body.concept_id, program_root
    )

    provider = _make_provider(sess.provider_name)
    sess.question_count += 1

    result = run_question_cycle(
        session_id=session_id,
        question_number=sess.question_count,
        learner_response=body.learner_response,
        grounding_paths=grounding_paths,
        state_path=sess.state_path,
        provider=provider,
        model=sess.model,
        config={},
        metadata={"provider": sess.provider_name, "model": sess.model},
        program_root=program_root,
    )

    return TurnResponse(
        question_number=result.question_number,
        question_text=result.question_text,
        explicit_rating=result.explicit_rating,
        correct=result.correct,
        hint_count=result.hint_count,
        turn_count=result.turn_count,
        reward=result.reward,
        new_difficulty=result.new_difficulty,
        inconsistency_flag=False,
    )


@app.get("/sessions/{session_id}/state", response_model=SessionStateResponse)
def get_session_state(session_id: str) -> SessionStateResponse:
    sess = _get_session(session_id)
    scalar = state_io.read_scalar(sess.state_path)
    mastery = state_io.read_mastery(sess.state_path)
    return SessionStateResponse(
        session_id=session_id,
        scalar=scalar,
        question_count=sess.question_count,
        mastery=mastery,
    )


@app.get("/config/provider", response_model=ProviderConfig)
def get_provider_config() -> ProviderConfig:
    return _provider_config


@app.put("/config/provider", response_model=ProviderConfig)
def put_provider_config(body: ProviderConfig) -> ProviderConfig:
    global _provider_config
    _provider_config = body
    return _provider_config


@app.post("/runs/batch", response_model=BatchRunResponse)
def batch_run(body: BatchRunRequest) -> BatchRunResponse:
    run_id = str(uuid.uuid4())
    return BatchRunResponse(run_id=run_id, status="queued")
