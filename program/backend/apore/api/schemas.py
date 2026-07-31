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
    concept_ids: list[str] | None = Field(
        default=None,
        description=(
            "Optional subset of compiled concept ids to practice. "
            "When omitted, all concepts with bank questions are included."
        ),
    )


class CreateSessionResponse(BaseModel):
    session_id: str
    title: str
    scalar: float
    created_at: str
    knowledge_source: str
    focus_mode: str
    max_questions: int
    concept_ids: list[str] = Field(default_factory=list)
    title_pending: bool = False


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
    mode: Literal["answer", "tutor"] = Field(
        default="answer",
        description='"tutor" while Socratic help is active; otherwise "answer"',
    )
    correct: str = "no"
    hint_count: int = 0
    turn_count: int = 0
    hedging_count: int = 0
    explicit_rating: str | None = None
    reward: float | None = None
    new_difficulty: float | None = None
    inconsistency_flag: bool = False
    flag_reason: str | None = None
    assisted: bool = Field(
        default=False,
        description="True when the closed question used tutor mode at any point",
    )


class ConceptMasteryDeltaView(BaseModel):
    """Per-concept mastery movement for the current session."""

    band_before: Literal["new", "struggling", "learning", "proficient"]
    band_after: Literal["new", "struggling", "learning", "proficient"]
    pct_before: int | None
    pct_after: int | None
    n_observed_session: int


class SessionStateResponse(BaseModel):
    session_id: str
    title: str
    scalar: float
    question_count: int
    mastery: dict[str, float] = Field(
        description=(
            "BKT-derived P(L) per concept with observations for this "
            "knowledge_source (cross-session). Unobserved concepts omitted."
        ),
    )
    mastery_delta: dict[str, ConceptMasteryDeltaView] = Field(
        default_factory=dict,
        description=(
            "BKT mastery before→after for concepts observed in this session. "
            "Empty when no graded answers yet."
        ),
    )
    knowledge_source: str
    focus_mode: str
    max_questions: int
    questions_remaining: int
    active_concept_id: str | None = None
    concept_ids: list[str] = Field(default_factory=list)
    title_pending: bool = False
    status: Literal["active", "completed", "ended_early"] = "active"
    ended_at: str | None = None


class BKTParamsView(BaseModel):
    p_L0: float
    p_T: float
    p_G: float
    p_S: float
    p_F: float


class ConceptMasteryView(BaseModel):
    p_mastery: float | None
    band: Literal["new", "struggling", "learning", "proficient"]
    n_observed: int
    display_pct: int | None


class LearnerMasteryResponse(BaseModel):
    knowledge_source: str
    params: BKTParamsView
    concepts: dict[str, ConceptMasteryView]


class GraphConceptView(BaseModel):
    id: str
    label: str
    depth: int
    p_mastery: float | None
    band: Literal["new", "struggling", "learning", "proficient"]
    n_observed: int
    display_pct: int | None
    has_wiki: bool


class GraphChapterView(BaseModel):
    id: str
    knowledge_source: str
    has_concept_graph: bool
    mastery_pct: int
    concepts_proficient: int
    concepts_total: int
    concepts: list[GraphConceptView]
    edges: list[dict]


class DomainGraphResponse(BaseModel):
    domain_id: str
    chapters: list[GraphChapterView]


class EndSessionResponse(BaseModel):
    session_id: str
    status: Literal["ended_early"]
    ended_at: str
    title: str
    knowledge_source: str
    question_count: int
    max_questions: int
    scalar: float
    mastery_delta: dict[str, ConceptMasteryDeltaView] = Field(default_factory=dict)

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
    name: str | None = None
    scope: str | None = None
    goal: str | None = None
    tutor_style: str | None = None


class RenameDomainRequest(BaseModel):
    domain_id: str


class CreateChapterRequest(BaseModel):
    chapter_id: str


class RenameChapterRequest(BaseModel):
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


class SessionSummary(BaseModel):
    session_id: str
    title: str
    created_at: str
    knowledge_source: str
    status: Literal["active", "completed", "ended_early"] = "active"
    ended_at: str | None = None


class SessionListResponse(BaseModel):
    sessions: list[SessionSummary]


class SessionTranscriptResponse(BaseModel):
    session_id: str
    title: str
    created_at: str
    knowledge_source: str
    focus_mode: str
    max_questions: int
    status: Literal["active", "completed", "ended_early"] = "active"
    ended_at: str | None = None
    body: str


# --- Source ingestion --------------------------------------------------------


class SourceEntryView(BaseModel):
    id: str
    kind: str
    display_name: str | None = None
    media_type: str | None = None
    size: int | None = None
    ingested_at: str | None = None
    normalize_status: str
    normalize_error: str | None = None


class SourceListResponse(BaseModel):
    sources: list[SourceEntryView]


class AddUrlSourceRequest(BaseModel):
    url: str


# --- Compile pipeline --------------------------------------------------------


class CompileProgress(BaseModel):
    done: int = 0
    total: int = 0


class CompileStatus(BaseModel):
    stage: Literal[
        "idle", "normalizing", "compiling", "validating", "ready", "failed", "interrupted"
    ]
    version: int = 0
    source_hash: str | None = None
    progress: CompileProgress = Field(default_factory=CompileProgress)
    error_code: str | None = None
    error_message: str | None = None
    started_at: str | None = None
    updated_at: str | None = None


class ApprovalView(BaseModel):
    version: int
    source_hash: str | None = None
    approved_at: str | None = None
    legacy: bool = False


class ChapterArtifactStatus(BaseModel):
    source_hash: str | None = None
    compile: CompileStatus
    approved: ApprovalView | None = None
    is_approved: bool = False
    is_stale: bool = False
    has_unapproved_compile: bool = False
    wiki_count: int = 0
    concept_count: int = 0


class WikiPageView(BaseModel):
    concept_id: str
    label: str
    depth: int
    order: int = 0
    body: str


class WikiPreviewResponse(BaseModel):
    source: Literal["staging", "published"]
    version: int = 0
    pages: list[WikiPageView]
    edges: list[dict]


class ConceptOrderRequest(BaseModel):
    order: list[str] = Field(
        description="Concept ids in teaching order; must be an exact permutation.",
    )
