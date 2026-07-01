import { API_BASE_URL } from '../config';
import type {
  CreateSessionResponse,
  HealthResponse,
  KnowledgeCatalog,
  ProviderConfig,
  SessionStateResponse,
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
