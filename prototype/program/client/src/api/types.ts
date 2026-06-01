export interface CreateSessionRequest {
  provider: string;
  model: string;
  fixture: string;
}

export interface CreateSessionResponse {
  session_id: string;
  scalar: number;
  created_at: string;
}

export interface TurnRequest {
  learner_response: string;
  concept_id: string;
  explicit_rating?: string;
  correct?: string;
}

export interface TurnResponse {
  question_number: number;
  question_text: string;
  explicit_rating: string;
  correct: string;
  hint_count: number;
  turn_count: number;
  reward: number;
  new_difficulty: number;
  inconsistency_flag: boolean;
}

export interface SessionStateResponse {
  session_id: string;
  scalar: number;
  question_count: number;
  mastery: Record<string, number>;
}

export interface ProviderConfig {
  provider: string;
  model: string;
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
