export type StudyMode = 'chat' | 'scratchpad';

export interface CreateSessionRequest {
  knowledge_source?: string;
  fixture?: string;
  focus_mode?: 'adaptive' | 'weak_points';
  study_mode?: StudyMode;
  max_questions?: number;
  concept_ids?: string[];
}

export interface CreateSessionResponse {
  session_id: string;
  title: string;
  scalar: number;
  created_at: string;
  knowledge_source: string;
  focus_mode: 'adaptive' | 'weak_points';
  study_mode?: StudyMode;
  max_questions: number;
  concept_ids: string[];
  title_pending?: boolean;
}

export interface QuestionRequest {
  concept_id?: string;
}

export interface QuestionResponse {
  question_number: number;
  question_id: string;
  concept_id: string;
  concept_label: string;
  concept: string;
  question_type: string;
  intended_difficulty: number;
  question_text: string;
}

export interface FeedbackRegion {
  x: number;
  y: number;
  w: number;
  h: number;
  label?: string;
  explanation?: string;
}

export interface TurnRequest {
  learner_message?: string;
  /** @deprecated Use learner_message */
  learner_response?: string;
  concept_id?: string;
  skip?: boolean;
  skip_reason?: string;
  explicit_rating?: string;
  /** Leave post-rating reflection and advance to the next question */
  continue?: boolean;
  /** @deprecated Correctness is LLM-assessed on the grade step */
  correct?: string;
  /** Scratchpad selection action paired with learner_image */
  scratchpad_action?: 'ask' | 'submit';
  /** PNG/JPEG data URI of the selected scratchpad region */
  learner_image?: string;
}

export type TurnPhase =
  | 'dialogue'
  | 'skip_prompt'
  | 'graded'
  | 'reflection'
  | 'completed'
  | 'session_complete';

export interface TurnResponse {
  phase: TurnPhase;
  question_number: number;
  tutor_message?: string | null;
  question_closed?: boolean;
  /** "tutor" while Socratic help is active; otherwise "answer" */
  mode?: 'answer' | 'tutor';
  correct: string;
  hint_count: number;
  turn_count: number;
  hedging_count: number;
  explicit_rating?: string | null;
  reward?: number | null;
  new_difficulty?: number | null;
  inconsistency_flag: boolean;
  flag_reason?: string | null;
  /** True when the closed question used tutor mode at any point */
  assisted?: boolean;
  /** Crop-relative regions highlighting incorrect/relevant work */
  feedback_regions?: FeedbackRegion[];
}

/** Persisted tutor reply anchored to selected scratchpad nodes. */
export interface ScratchpadAnnotation {
  id: string;
  node_ids: string[];
  prompt: string;
  response: string;
  feedback_regions: FeedbackRegion[];
}

export interface ScratchpadScenePayload {
  question_number: number;
  schema_version: 1;
  engine: 'apore-konva';
  nodes: ScratchpadNode[];
  camera: ScratchpadCamera;
  last_export_bounds: ScratchpadExportBounds | null;
  feedback_regions: FeedbackRegion[];
  /** Completed Ask replies linked to canvas nodes; empty on legacy scenes. */
  annotations?: ScratchpadAnnotation[];
}

export interface ScratchpadCamera {
  x: number;
  y: number;
  scale: number;
}

export interface ScratchpadExportBounds {
  x: number;
  y: number;
  width: number;
  height: number;
  padding: number;
}

export type ScratchpadNode =
  | {
      id: string;
      type: 'stroke';
      x: number;
      y: number;
      points: number[];
      stroke: string;
      stroke_width: number;
      scale_x?: number;
      scale_y?: number;
      rotation?: number;
    }
  | {
      id: string;
      type: 'text';
      x: number;
      y: number;
      text: string;
      fill: string;
      font_size: number;
      width: number;
      height: number;
      scale_x?: number;
      scale_y?: number;
      rotation?: number;
    }
  | {
      id: string;
      type: 'rectangle' | 'ellipse' | 'line';
      x: number;
      y: number;
      width: number;
      height: number;
      stroke: string;
      stroke_width: number;
      scale_x?: number;
      scale_y?: number;
      rotation?: number;
    };

export interface ScratchpadSceneResponse {
  question_number: number;
  scene: ScratchpadScenePayload | null;
}

export interface SessionStateResponse {
  session_id: string;
  title: string;
  scalar: number;
  question_count: number;
  /** BKT-derived P(L); unobserved concepts omitted (not 0). */
  mastery: Record<string, number>;
  /** Mastery before→after for concepts observed in this session. */
  mastery_delta?: Record<string, ConceptMasteryDelta>;
  knowledge_source: string;
  focus_mode: 'adaptive' | 'weak_points';
  study_mode?: StudyMode;
  max_questions: number;
  questions_remaining: number;
  active_concept_id?: string | null;
  concept_ids: string[];
  title_pending?: boolean;
}

export type MasteryBand = 'new' | 'struggling' | 'learning' | 'proficient';

export interface ConceptMastery {
  p_mastery: number | null;
  band: MasteryBand;
  n_observed: number;
  display_pct: number | null;
}

export interface ConceptMasteryDelta {
  band_before: MasteryBand;
  band_after: MasteryBand;
  pct_before: number | null;
  pct_after: number | null;
  n_observed_session: number;
}

export interface LearnerMasteryResponse {
  knowledge_source: string;
  params: {
    p_L0: number;
    p_T: number;
    p_G: number;
    p_S: number;
    p_F: number;
  };
  concepts: Record<string, ConceptMastery>;
}

export interface GraphConcept {
  id: string;
  label: string;
  depth: number;
  p_mastery: number | null;
  band: MasteryBand;
  n_observed: number;
  display_pct: number | null;
  has_wiki: boolean;
}

export interface GraphEdge {
  source: string;
  target: string;
  relation: string;
}

export interface GraphChapter {
  id: string;
  knowledge_source: string;
  has_concept_graph: boolean;
  mastery_pct: number;
  concepts_proficient: number;
  concepts_total: number;
  concepts: GraphConcept[];
  edges: GraphEdge[];
}

export interface DomainGraph {
  domain_id: string;
  chapters: GraphChapter[];
}

export interface ProviderConfig {
  anthropic_api_key_set: boolean;
  anthropic_api_key_hint: string | null;
  nim_api_key_set: boolean;
  nim_api_key_hint: string | null;
  model: string;
  active_provider: string | null;
  active_model: string | null;
}

export interface ProviderConfigUpdate {
  anthropic_api_key?: string | null;
  nim_api_key?: string | null;
  model?: string | null;
}

export interface BatchRunRequest {
  sessions: number;
  profile: {
    ability: number;
    misconceptions: string[];
    seed: number;
  };
}

export interface BatchRunResponse {
  run_id: string;
  status: string;
}

export interface KnowledgeFixture {
  name: string;
  knowledge_source: string;
  description: string;
  commit: string;
  fetched: boolean;
  chapter_ready: boolean;
}

export type CompileStage =
  | 'idle'
  | 'normalizing'
  | 'compiling'
  | 'validating'
  | 'ready'
  | 'failed'
  | 'interrupted';

export interface KnowledgeChapter {
  id: string;
  knowledge_source: string;
  sources_present: boolean;
  source_count: number;
  source_files: string[];
  has_concept_graph: boolean;
  wiki_count: number;
  has_question_bank: boolean;
  question_bank_count: number;
  compile_stage: CompileStage;
  is_approved: boolean;
  is_stale: boolean;
  has_unapproved_compile: boolean;
}

export interface SourceEntry {
  id: string;
  kind: 'file' | 'url';
  display_name: string | null;
  media_type: string | null;
  size: number | null;
  ingested_at: string | null;
  normalize_status: 'ok' | 'failed' | 'pending' | 'legacy';
  normalize_error: string | null;
}

export interface SourceListResult {
  sources: SourceEntry[];
}

export interface CompileProgress {
  done: number;
  total: number;
}

export interface CompileStatus {
  stage: CompileStage;
  version: number;
  source_hash: string | null;
  progress: CompileProgress;
  error_code: string | null;
  error_message: string | null;
  started_at: string | null;
  updated_at: string | null;
}

export interface ChapterApproval {
  version: number;
  source_hash: string | null;
  approved_at: string | null;
  legacy: boolean;
}

export interface ChapterArtifactStatus {
  source_hash: string | null;
  compile: CompileStatus;
  approved: ChapterApproval | null;
  is_approved: boolean;
  is_stale: boolean;
  has_unapproved_compile: boolean;
  wiki_count: number;
  concept_count: number;
}

export interface WikiPageView {
  concept_id: string;
  label: string;
  depth: number;
  order: number;
  body: string;
}

export interface WikiPreview {
  source: 'staging' | 'published';
  version: number;
  pages: WikiPageView[];
  edges: Array<Record<string, unknown>>;
}

export interface KnowledgeDomain {
  id: string;
  chapters: KnowledgeChapter[];
}

export interface KnowledgeCatalog {
  fixtures: KnowledgeFixture[];
  domains: KnowledgeDomain[];
}

export interface FixtureFetchResult {
  name: string;
  commit: string;
  path: string;
  knowledge_source: string;
  status: string;
  chapter_ready: boolean;
  chapter_path?: string | null;
  nodes: number;
  bootstrap_status?: string | null;
}

export interface StubCompileResult {
  nodes: number;
  wiki_files: number;
  concept_graph: string;
}

export interface QuestionBankEntry {
  id: string;
  concept_id: string;
  type: string;
  intended_difficulty: number;
  text: string;
  scratchpad_eligible: boolean;
  depth?: number;
}

export interface QuestionBankResponse {
  version: number;
  questions: QuestionBankEntry[];
  path: string;
}

export interface QuestionBankGenerateStatus {
  status: 'idle' | 'running' | 'completed' | 'failed';
  concepts_total: number;
  concepts_done: number;
  questions: number | null;
  concepts: number | null;
  path: string | null;
  error: string | null;
  started_at: string | null;
}

export type SessionLifecycleStatus = 'active' | 'completed' | 'ended_early';

export interface SessionSummary {
  session_id: string;
  title: string;
  created_at: string;
  knowledge_source: string;
  status?: SessionLifecycleStatus;
  ended_at?: string | null;
}

export interface SessionListResponse {
  sessions: SessionSummary[];
}

export type SessionHistoryQuestionStatus =
  | 'completed'
  | 'in_progress'
  | 'awaiting_rating'
  | 'reflection';

export interface SessionHistoryMessage {
  role: string;
  content: string;
}

export interface SessionHistoryQuestion {
  question_number: number;
  question_id: string;
  question_text: string;
  concept_id: string;
  concept_label: string;
  correct?: string | null;
  explicit_rating?: string | null;
  assisted?: boolean;
  status: SessionHistoryQuestionStatus;
  messages: SessionHistoryMessage[];
}

export interface SessionTranscript {
  session_id: string;
  title: string;
  created_at: string;
  knowledge_source: string;
  focus_mode: string;
  max_questions: number;
  status?: SessionLifecycleStatus;
  ended_at?: string | null;
  body: string;
  questions?: SessionHistoryQuestion[];
}

export interface DialogueMessageView {
  role: string;
  content: string;
  attachment?: 'scratchpad_selection' | null;
}

export interface PendingQuestionView {
  question_number: number;
  question_id: string;
  concept_id: string;
  concept_label: string;
  concept: string;
  question_type: string;
  intended_difficulty: number;
  question_text: string;
}

export type ResumeSessionPhase =
  | 'idle'
  | 'dialogue'
  | 'skip_prompt'
  | 'graded'
  | 'reflection';

export interface ResumeHistoryItem {
  question_number: number;
  question_text: string;
  explicit_rating: string;
  correct: string;
  reward?: number | null;
}

export interface ResumeSessionResponse {
  session_id: string;
  title: string;
  scalar: number;
  question_count: number;
  mastery: Record<string, number>;
  mastery_delta?: Record<string, ConceptMasteryDelta>;
  knowledge_source: string;
  focus_mode: 'adaptive' | 'weak_points' | string;
  study_mode?: StudyMode;
  max_questions: number;
  questions_remaining: number;
  active_concept_id?: string | null;
  concept_ids: string[];
  title_pending?: boolean;
  status: SessionLifecycleStatus;
  ended_at?: string | null;
  phase: ResumeSessionPhase;
  pending_question: PendingQuestionView | null;
  dialogue_messages: DialogueMessageView[];
  awaiting_skip_reason: boolean;
  tutor_mode: boolean;
  scratchpad_scene?: ScratchpadScenePayload | null;
  history?: ResumeHistoryItem[];
  correct?: string | null;
  hint_count?: number | null;
  turn_count?: number | null;
  hedging_count?: number | null;
  flag_reason?: string | null;
  assisted?: boolean | null;
  explicit_rating?: string | null;
  reward?: number | null;
  new_difficulty?: number | null;
}

export interface EndSessionResponse {
  session_id: string;
  status: 'ended_early';
  ended_at: string;
  title: string;
  knowledge_source: string;
  question_count: number;
  max_questions: number;
  scalar: number;
  mastery_delta?: Record<string, ConceptMasteryDelta>;
}
