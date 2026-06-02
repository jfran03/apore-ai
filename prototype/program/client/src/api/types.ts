export interface CreateSessionRequest {
  knowledge_source?: string;
  fixture?: string;
}

export interface CreateSessionResponse {
  session_id: string;
  scalar: number;
  created_at: string;
  knowledge_source: string;
}

export interface QuestionRequest {
  concept_id?: string;
}

export interface QuestionResponse {
  question_number: number;
  concept_id: string;
  concept_label: string;
  concept: string;
  question_type: string;
  intended_difficulty: number;
  question_text: string;
}

export interface TurnRequest {
  learner_response?: string;
  concept_id?: string;
  explicit_rating?: string;
  /** @deprecated Correctness is LLM-assessed on the grade step */
  correct?: string;
}

export interface TurnResponse {
  phase: 'graded' | 'completed';
  question_number: number;
  correct: string;
  hint_count: number;
  turn_count: number;
  hedging_count: number;
  explicit_rating?: string | null;
  reward?: number | null;
  new_difficulty?: number | null;
  inconsistency_flag: boolean;
  flag_reason?: string | null;
}

export interface SessionStateResponse {
  session_id: string;
  scalar: number;
  question_count: number;
  mastery: Record<string, number>;
  knowledge_source: string;
  active_concept_id?: string | null;
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

export interface KnowledgeChapter {
  id: string;
  knowledge_source: string;
  sources_present: boolean;
  source_count: number;
  source_files: string[];
  has_concept_graph: boolean;
  wiki_count: number;
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
