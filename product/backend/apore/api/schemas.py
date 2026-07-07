"""Pydantic request/response models for the Apore API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class CreateSessionRequest(BaseModel):
    knowledge_source: str = Field(
        default="domain:discrete-math/01-set-theory",
        description="domain:domain_id/chapter_id (fixture:name aliases supported)",
    )
    fixture: str | None = Field(
        default=None,
        description="Deprecated: use knowledge_source=fixture:{name}",
    )
    focus_mode: str = Field(
        default="adaptive",
        description='Question selection strategy: "adaptive" or "weak_points"',
    )
    max_questions: int = Field(default=10, ge=1, le=50)


class CreateSessionResponse(BaseModel):
    session_id: str
    title: str
    scalar: float
    created_at: str
    knowledge_source: str
    focus_mode: str
    max_questions: int


class TurnRequest(BaseModel):
    learner_message: str | None = Field(
        default=None,
        description="Learner message during Socratic dialogue",
    )
    learner_response: str | None = Field(
        default=None,
        description="Deprecated alias for learner_message",
    )
    concept_id: str | None = None
    skip: bool = Field(default=False, description="Request to skip the current question")
    skip_reason: str | None = Field(
        default=None,
        description="Explanation after skip prompt",
    )
    explicit_rating: str | None = None
    continue_to_next: bool = Field(
        default=False,
        alias="continue",
        description="Leave post-rating reflection and advance to the next question",
    )
    correct: str | None = Field(
        default=None,
        description="Deprecated; correctness is LLM-assessed on the grade step",
    )

    model_config = {"populate_by_name": True}


class QuestionRequest(BaseModel):
    concept_id: str | None = Field(
        default=None,
        description="Optional; server selects from graph when omitted",
    )


class QuestionResponse(BaseModel):
    question_number: int
    question_id: str
    concept_id: str
    concept_label: str
    concept: str
    question_type: str
    intended_difficulty: float
    question_text: str


class TurnResponse(BaseModel):
    phase: str = Field(
        description=(
            '"dialogue" tutor reply; "skip_prompt" awaiting skip reason; '
            '"graded" after assessment; "reflection" after difficulty rating '
            '(optional follow-up chat); "completed" after leaving reflection; '
            '"session_complete" when max_questions reached'
        )
    )
    question_number: int
    tutor_message: str | None = None
    question_closed: bool = False
    correct: str = "no"
    hint_count: int = 0
    turn_count: int = 0
    hedging_count: int = 0
    explicit_rating: str | None = None
    reward: float | None = None
    new_difficulty: float | None = None
    inconsistency_flag: bool = False
    flag_reason: str | None = None


class SessionStateResponse(BaseModel):
    session_id: str
    title: str
    scalar: float
    question_count: int
    mastery: dict[str, float]
    knowledge_source: str
    focus_mode: str
    max_questions: int
    questions_remaining: int
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
    knowledge_source: str
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


class QuestionBankEntry(BaseModel):
    id: str
    concept_id: str
    type: str
    intended_difficulty: float = Field(ge=0.1, le=0.9)
    text: str


class QuestionBankEntryView(QuestionBankEntry):
    depth: int


class QuestionBankResponse(BaseModel):
    version: int
    questions: list[QuestionBankEntryView]
    path: str


class QuestionBankReplaceRequest(BaseModel):
    version: int = 1
    questions: list[QuestionBankEntry]


class QuestionBankGenerateStatus(BaseModel):
    status: Literal["idle", "running", "completed", "failed"]
    concepts_total: int = 0
    concepts_done: int = 0
    questions: int | None = None
    concepts: int | None = None
    path: str | None = None
    error: str | None = None
    started_at: str | None = None


class WorkspaceDomainCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    objective: str = ""
    teaching_style: str = "socratic"
    teaching_prompt: str = ""
    model_preference: str = "auto"


class WorkspaceChapterSummary(BaseModel):
    id: str
    has_concept_graph: bool
    wiki_count: int
    has_question_bank: bool


class WorkspaceDomainSummary(BaseModel):
    id: str
    name: str
    objective: str
    teaching_style: str
    teaching_prompt: str
    model_preference: str
    created_at: str
    status: Literal["ready", "empty", "invalid"]
    reason: str | None = None
    chapters: list[WorkspaceChapterSummary] = []
    session_count: int = 0
    source_files: list[str] = []


class WorkspaceDomainListResponse(BaseModel):
    domains: list[WorkspaceDomainSummary]
