// Types mirror the backend Pydantic models in apore/api/schemas.py and the
// catalog shape in apore/setup/catalog.py. Kept to the subset the product shell
// currently consumes; extend as new views come online.

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  testbed: boolean;
}

export interface ChapterEntry {
  id: string;
  knowledge_source: string;
  sources_present: boolean;
  source_count: number;
  source_files: string[];
  has_concept_graph: boolean;
  wiki_count: number;
  has_question_bank: boolean;
  question_bank_count: number;
}

export interface DomainEntry {
  id: string;
  chapters: ChapterEntry[];
}

export interface FixtureEntry {
  name: string;
  knowledge_source: string;
  domain_id: string;
  description: string;
  commit: string;
  fetched: boolean;
  chapter_ready: boolean;
}

export interface KnowledgeCatalog {
  fixtures: FixtureEntry[];
  domains: DomainEntry[];
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

export interface CreateSessionResponse {
  session_id: string;
  title: string;
  scalar: number;
  created_at: string;
  knowledge_source: string;
  focus_mode: string;
  max_questions: number;
}

export interface SessionStateResponse {
  session_id: string;
  title: string;
  scalar: number;
  question_count: number;
  mastery: Record<string, number>;
  knowledge_source: string;
  focus_mode: string;
  max_questions: number;
  questions_remaining: number;
  active_concept_id: string | null;
}

// --- Domain workspaces (mirrors Workspace* models in apore/api/schemas.py) ---

export interface WorkspaceChapter {
  id: string;
  has_concept_graph: boolean;
  wiki_count: number;
  has_question_bank: boolean;
}

export type DomainStatus = 'ready' | 'empty' | 'invalid';

export interface WorkspaceDomain {
  id: string;
  name: string;
  objective: string;
  teaching_style: string;
  teaching_prompt: string;
  model_preference: string;
  created_at: string;
  status: DomainStatus;
  reason: string | null;
  chapters: WorkspaceChapter[];
  session_count: number;
  source_files: string[];
}

export interface CreateDomainPayload {
  name: string;
  objective: string;
  teaching_style: string;
  teaching_prompt: string;
  model_preference: string;
}

export type SessionStatus = 'active' | 'complete' | 'invalid';

export interface WorkspaceSessionSummary {
  session_id: string;
  title: string;
  chapter_id: string;
  created_at: string;
  updated_at: string;
  question_count: number;
  max_questions: number;
  status: SessionStatus;
}

export type SessionPhase =
  | 'idle'
  | 'awaiting_answer'
  | 'awaiting_rating'
  | 'reflection'
  | 'complete';

export interface TranscriptEvent {
  type: 'question' | 'learner_message' | 'tutor_message' | 'graded' | 'rating' | 'system';
  ts: string;
  question_number?: number;
  question_id?: string;
  concept_id?: string;
  concept_label?: string;
  question_text?: string;
  text?: string;
  correct?: string;
  rating?: string;
  reward?: number | null;
  new_difficulty?: number | null;
}

export interface WorkspaceSessionDetail {
  session_id: string;
  title: string;
  chapter_id: string;
  knowledge_source: string;
  created_at: string;
  updated_at: string;
  question_count: number;
  max_questions: number;
  scalar: number;
  phase: SessionPhase;
  transcript: TranscriptEvent[];
}

export interface QuestionResponse {
  question_number: number;
  question_id: string;
  concept_id: string;
  concept_label: string;
  question_type: string;
  intended_difficulty: number;
  question_text: string;
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
  tutor_message: string | null;
  question_closed: boolean;
  correct: string;
  explicit_rating: string | null;
  reward: number | null;
  new_difficulty: number | null;
  flag_reason: string | null;
}

export interface ProviderConfigUpdate {
  anthropic_api_key?: string;
  nim_api_key?: string;
  model?: string;
}
