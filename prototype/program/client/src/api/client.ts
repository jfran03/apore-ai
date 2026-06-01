import { API_BASE_URL } from '../config';
import type {
  CreateSessionRequest,
  CreateSessionResponse,
  TurnRequest,
  TurnResponse,
  SessionStateResponse,
  ProviderConfig,
  BatchRunRequest,
  BatchRunResponse,
} from './types';

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, init);
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
  return res.json() as Promise<T>;
}

export async function createSession(req: CreateSessionRequest): Promise<CreateSessionResponse> {
  return apiFetch<CreateSessionResponse>('/sessions', {
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

export async function setProviderConfig(config: ProviderConfig): Promise<ProviderConfig> {
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
