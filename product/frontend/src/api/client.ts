import { API_BASE_URL } from '../config';
import type {
  CreateDomainPayload,
  CreateSessionResponse,
  HealthResponse,
  KnowledgeCatalog,
  ProviderConfig,
  ProviderConfigUpdate,
  QuestionResponse,
  SessionStateResponse,
  TurnResponse,
  WorkspaceDomain,
  WorkspaceSessionDetail,
  WorkspaceSessionSummary,
} from './types';

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, init);
  if (!res.ok) {
    const body = await res.text();
    try {
      const parsed = JSON.parse(body) as { detail?: string };
      if (typeof parsed.detail === 'string') {
        throw new Error(parsed.detail);
      }
    } catch (err) {
      if (err instanceof Error && err.name !== 'SyntaxError') {
        throw err;
      }
    }
    throw new Error(`HTTP ${res.status}: ${body}`);
  }
  return res.json() as Promise<T>;
}

export function getHealth(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>('/health');
}

export function getKnowledgeCatalog(): Promise<KnowledgeCatalog> {
  return apiFetch<KnowledgeCatalog>('/setup/knowledge');
}

export function getProviderConfig(): Promise<ProviderConfig> {
  return apiFetch<ProviderConfig>('/config/provider');
}

export function createSession(knowledgeSource: string): Promise<CreateSessionResponse> {
  return apiFetch<CreateSessionResponse>('/sessions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ knowledge_source: knowledgeSource }),
  });
}

export function getSessionState(sessionId: string): Promise<SessionStateResponse> {
  return apiFetch<SessionStateResponse>(`/sessions/${sessionId}/state`);
}

export function listDomains(): Promise<{ domains: WorkspaceDomain[] }> {
  return apiFetch('/domains');
}

export function createDomain(payload: CreateDomainPayload): Promise<WorkspaceDomain> {
  return apiFetch('/domains', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export function getDomain(domainId: string): Promise<WorkspaceDomain> {
  return apiFetch(`/domains/${domainId}`);
}

export function seedDomain(domainId: string): Promise<{ chapters: string[] }> {
  return apiFetch(`/domains/${domainId}/seed`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
}

export function listDomainSessions(
  domainId: string,
): Promise<{ sessions: WorkspaceSessionSummary[] }> {
  return apiFetch(`/domains/${domainId}/sessions`);
}

export function createDomainSession(
  domainId: string,
  body: { chapter_id?: string; max_questions?: number },
): Promise<CreateSessionResponse> {
  return apiFetch(`/domains/${domainId}/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export function getDomainSession(
  domainId: string,
  sessionId: string,
): Promise<WorkspaceSessionDetail> {
  return apiFetch(`/domains/${domainId}/sessions/${sessionId}`);
}

export function postDomainQuestion(
  domainId: string,
  sessionId: string,
): Promise<QuestionResponse> {
  return apiFetch(`/domains/${domainId}/sessions/${sessionId}/question`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
}

export function postDomainTurn(
  domainId: string,
  sessionId: string,
  body: {
    learner_message?: string;
    explicit_rating?: string;
    skip?: boolean;
    skip_reason?: string;
    continue?: boolean;
  },
): Promise<TurnResponse> {
  return apiFetch(`/domains/${domainId}/sessions/${sessionId}/turn`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export function updateProviderConfig(update: ProviderConfigUpdate): Promise<ProviderConfig> {
  return apiFetch('/config/provider', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(update),
  });
}
