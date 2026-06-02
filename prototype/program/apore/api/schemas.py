"""Pydantic request/response models for the Apore API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CreateSessionRequest(BaseModel):
    knowledge_source: str = Field(
        default="fixture:apore-lite",
        description="fixture:name or domain:domain_id/chapter_id",
    )
    fixture: str | None = Field(
        default=None,
        description="Deprecated: use knowledge_source=fixture:{name}",
    )


class CreateSessionResponse(BaseModel):
    session_id: str
    scalar: float
    created_at: str
    knowledge_source: str


class TurnRequest(BaseModel):
    learner_response: str | None = None
    concept_id: str | None = None
    explicit_rating: str | None = None
    correct: str | None = Field(
        default=None,
        description="Deprecated; correctness is LLM-assessed on the grade step",
    )


class QuestionRequest(BaseModel):
    concept_id: str | None = Field(
        default=None,
        description="Optional; server selects from graph when omitted",
    )


class QuestionResponse(BaseModel):
    question_number: int
    concept_id: str
    concept_label: str
    concept: str
    question_type: str
    intended_difficulty: float
    question_text: str


class TurnResponse(BaseModel):
    phase: str = Field(description='"graded" after answer LLM check; "completed" after difficulty rating')
    question_number: int
    correct: str
    hint_count: int
    turn_count: int
    hedging_count: int = 0
    explicit_rating: str | None = None
    reward: float | None = None
    new_difficulty: float | None = None
    inconsistency_flag: bool = False
    flag_reason: str | None = None


class SessionStateResponse(BaseModel):
    session_id: str
    scalar: float
    question_count: int
    mastery: dict[str, float]
    knowledge_source: str
    active_concept_id: str | None = None


class ProviderConfigResponse(BaseModel):
    anthropic_api_key_set: bool
    anthropic_api_key_hint: str | None
    nim_api_key_set: bool
    nim_api_key_hint: str | None
    model: str
    active_provider: str | None
    active_model: str | None


class ProviderConfigUpdate(BaseModel):
    anthropic_api_key: str | None = None
    nim_api_key: str | None = None
    model: str | None = None


class BatchRunRequest(BaseModel):
    sessions: int = Field(default=10, ge=1)
    profile: dict = Field(
        default_factory=lambda: {
            "ability": 0.5,
            "misconceptions": [],
            "seed": 42,
        }
    )


class BatchRunResponse(BaseModel):
    run_id: str
    status: str


class CreateDomainRequest(BaseModel):
    domain_id: str


class CreateChapterRequest(BaseModel):
    chapter_id: str


class KnowledgeCatalogResponse(BaseModel):
    fixtures: list[dict]
    domains: list[dict]


class FixtureFetchResponse(BaseModel):
    name: str
    commit: str
    path: str
    status: str
    chapter_ready: bool = False
    chapter_path: str | None = None
    nodes: int = 0
    bootstrap_status: str | None = None


class StubCompileResponse(BaseModel):
    nodes: int
    wiki_files: int
    concept_graph: str


class UploadSourcesResponse(BaseModel):
    uploaded: list[str]
