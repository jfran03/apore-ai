// Types mirror the backend Pydantic models in apore/api/schemas.py and the
// catalog shape in apore/setup/catalog.py. Kept to the subset the product shell
// currently consumes; extend as new views come online.

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
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
