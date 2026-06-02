import { API_BASE_URL } from '../config';
import type {
  CreateSessionRequest,
  CreateSessionResponse,
  QuestionRequest,
  QuestionResponse,
  TurnRequest,
  TurnResponse,
  SessionStateResponse,
  ProviderConfig,
  ProviderConfigUpdate,
  BatchRunRequest,
  BatchRunResponse,
  KnowledgeCatalog,
  FixtureFetchResult,
  StubCompileResult,
} from './types';

const KNOWLEDGE_SOURCE_KEY = 'apore.knowledge_source';

export function getStoredKnowledgeSource(): string {
  return localStorage.getItem(KNOWLEDGE_SOURCE_KEY) ?? 'fixture:apore-lite';
}

export function setStoredKnowledgeSource(source: string): void {
  localStorage.setItem(KNOWLEDGE_SOURCE_KEY, source);
}

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

export async function createSession(req: CreateSessionRequest = {}): Promise<CreateSessionResponse> {
  const knowledge_source = req.knowledge_source ?? getStoredKnowledgeSource();
  return apiFetch<CreateSessionResponse>('/sessions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...req, knowledge_source }),
  });
}

export async function fetchQuestion(
  sessionId: string,
  req: QuestionRequest = {},
): Promise<QuestionResponse> {
  return apiFetch<QuestionResponse>(`/sessions/${sessionId}/question`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
}

export async function postTurn(sessionId: string, req: TurnRequest): Promise<TurnResponse> {
  return apiFetch<TurnResponse>(`/sessions/${sessionId}/turn`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
}

export async function getSessionState(sessionId: string): Promise<SessionStateResponse> {
  return apiFetch<SessionStateResponse>(`/sessions/${sessionId}/state`);
}

export async function getProviderConfig(): Promise<ProviderConfig> {
  return apiFetch<ProviderConfig>('/config/provider');
}

export async function setProviderConfig(config: ProviderConfigUpdate): Promise<ProviderConfig> {
  return apiFetch<ProviderConfig>('/config/provider', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  });
}

export async function startBatchRun(req: BatchRunRequest): Promise<BatchRunResponse> {
  return apiFetch<BatchRunResponse>('/runs/batch', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
}

export async function getKnowledgeCatalog(): Promise<KnowledgeCatalog> {
  return apiFetch<KnowledgeCatalog>('/setup/knowledge');
}

export async function fetchFixture(name: string): Promise<FixtureFetchResult> {
  return apiFetch<FixtureFetchResult>(`/setup/fixtures/${name}/fetch`, { method: 'POST' });
}

export async function createDomain(domainId: string): Promise<{ domain_id: string; path: string }> {
  return apiFetch('/setup/domains', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ domain_id: domainId }),
  });
}

export async function createChapter(
  domainId: string,
  chapterId: string,
): Promise<{ knowledge_source: string }> {
  return apiFetch(`/setup/domains/${domainId}/chapters`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ chapter_id: chapterId }),
  });
}

export async function uploadSources(
  domainId: string,
  chapterId: string,
  files: File[],
): Promise<{ uploaded: string[] }> {
  const form = new FormData();
  for (const file of files) {
    form.append('files', file);
  }
  const res = await fetch(
    `${API_BASE_URL}/setup/domains/${domainId}/chapters/${chapterId}/sources`,
    { method: 'POST', body: form },
  );
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
  return res.json();
}

export async function stubCompileChapter(
  domainId: string,
  chapterId: string,
): Promise<StubCompileResult> {
  return apiFetch<StubCompileResult>(
    `/setup/domains/${domainId}/chapters/${chapterId}/compile-stub`,
    { method: 'POST' },
  );
}
