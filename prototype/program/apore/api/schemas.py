"""Pydantic schemas for the Apore API (OpenAPI types for the web client)."""

from __future__ import annotations

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# POST /sessions
# ---------------------------------------------------------------------------

class CreateSessionRequest(BaseModel):
    provider: str = "stub"
    model: str = "stub"
    fixture: str = "apore-lite"


class CreateSessionResponse(BaseModel):
    session_id: str
    scalar: float
    created_at: str


# ---------------------------------------------------------------------------
# POST /sessions/{session_id}/turn
# ---------------------------------------------------------------------------

class TurnRequest(BaseModel):
    learner_response: str
    concept_id: str = "set_theory_intro"


class TurnResponse(BaseModel):
    question_number: int
    question_text: str
    explicit_rating: str
    correct: str
    hint_count: int
    turn_count: int
    reward: float
    new_difficulty: float
    inconsistency_flag: bool


# ---------------------------------------------------------------------------
# GET /sessions/{session_id}/state
# ---------------------------------------------------------------------------

class SessionStateResponse(BaseModel):
    session_id: str
    scalar: float
    question_count: int
    mastery: dict[str, float]


# ---------------------------------------------------------------------------
# GET /config/provider  /  PUT /config/provider
# ---------------------------------------------------------------------------

class ProviderConfig(BaseModel):
    provider: str
    model: str


# ---------------------------------------------------------------------------
# POST /runs/batch
# ---------------------------------------------------------------------------

class BatchProfile(BaseModel):
    ability: float = 0.5
    misconceptions: list[str] = []
    seed: int = 0


class BatchRunRequest(BaseModel):
    sessions: int = 1
    profile: BatchProfile = BatchProfile()


class BatchRunResponse(BaseModel):
    run_id: str
    status: str
