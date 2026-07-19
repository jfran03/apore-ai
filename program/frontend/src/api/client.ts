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
  QuestionBankEntry,
  QuestionBankResponse,
  QuestionBankGenerateStatus,
  SessionListResponse,
  SessionTranscript,
  SourceEntry,
  SourceListResult,
  ChapterArtifactStatus,
  CompileStatus,
  WikiPreview,
} from './types';

function domainChapterBase(knowledgeSource: string): string {
  if (knowledgeSource.startsWith('fixture:')) {
    if (knowledgeSource === 'fixture:apore-lite') {
      return '/setup/domains/discrete-math/chapters/01-set-theory';
    }
    throw new Error(`Unsupported fixture knowledge source: ${knowledgeSource}`);
  }
  if (knowledgeSource.startsWith('domain:')) {
    const rest = knowledgeSource.split(':', 2)[1];
    const [domainId, chapterId] = rest.split('/', 2);
    return `/setup/domains/${encodeURIComponent(domainId)}/chapters/${encodeURIComponent(chapterId)}`;
  }
  throw new Error(`Unsupported knowledge source: ${knowledgeSource}`);
}

const KNOWLEDGE_SOURCE_KEY = 'apore.knowledge_source';

export function getStoredKnowledgeSource(): string {
  return localStorage.getItem(KNOWLEDGE_SOURCE_KEY) ?? 'domain:discrete-math/01-set-theory';
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

function questionBankBasePath(knowledgeSource: string): string {
  if (knowledgeSource.startsWith('fixture:')) {
    if (knowledgeSource === 'fixture:apore-lite') {
      return '/setup/domains/discrete-math/chapters/01-set-theory/question-bank';
    }
    throw new Error(`Unsupported fixture knowledge source: ${knowledgeSource}`);
  }
  if (knowledgeSource.startsWith('domain:')) {
    const rest = knowledgeSource.split(':', 2)[1];
    const [domainId, chapterId] = rest.split('/', 2);
    return `/setup/domains/${encodeURIComponent(domainId)}/chapters/${encodeURIComponent(chapterId)}/question-bank`;
  }
  throw new Error(`Unsupported knowledge source: ${knowledgeSource}`);
}

function questionBankGeneratePath(knowledgeSource: string): string {
  return `${questionBankBasePath(knowledgeSource)}/generate`;
}

export async function getQuestionBank(
  knowledgeSource: string = getStoredKnowledgeSource(),
): Promise<QuestionBankResponse> {
  return apiFetch<QuestionBankResponse>(questionBankBasePath(knowledgeSource));
}

export async function generateQuestionBank(
  knowledgeSource: string = getStoredKnowledgeSource(),
): Promise<QuestionBankGenerateStatus> {
  return apiFetch<QuestionBankGenerateStatus>(
    questionBankGeneratePath(knowledgeSource),
    { method: 'POST' },
  );
}

export async function getQuestionBankGenerateStatus(
  knowledgeSource: string = getStoredKnowledgeSource(),
): Promise<QuestionBankGenerateStatus> {
  return apiFetch<QuestionBankGenerateStatus>(
    `${questionBankGeneratePath(knowledgeSource)}/status`,
  );
}

export async function addQuestionBankEntry(
  entry: QuestionBankEntry,
  knowledgeSource: string = getStoredKnowledgeSource(),
): Promise<QuestionBankResponse> {
  return apiFetch<QuestionBankResponse>(
    `${questionBankBasePath(knowledgeSource)}/questions`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(entry),
    },
  );
}

export async function updateQuestionBankEntry(
  questionId: string,
  entry: QuestionBankEntry,
  knowledgeSource: string = getStoredKnowledgeSource(),
): Promise<QuestionBankResponse> {
  return apiFetch<QuestionBankResponse>(
    `${questionBankBasePath(knowledgeSource)}/questions/${encodeURIComponent(questionId)}`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(entry),
    },
  );
}

export async function deleteQuestionBankEntry(
  questionId: string,
  knowledgeSource: string = getStoredKnowledgeSource(),
): Promise<QuestionBankResponse> {
  return apiFetch<QuestionBankResponse>(
    `${questionBankBasePath(knowledgeSource)}/questions/${encodeURIComponent(questionId)}`,
    { method: 'DELETE' },
  );
}

export async function listSessions(): Promise<SessionListResponse> {
  return apiFetch<SessionListResponse>('/sessions');
}

export async function getSessionTranscript(sessionId: string): Promise<SessionTranscript> {
  return apiFetch<SessionTranscript>(`/sessions/${encodeURIComponent(sessionId)}/transcript`);
}

export async function getChapterSources(
  knowledgeSource: string = getStoredKnowledgeSource(),
): Promise<SourceListResult> {
  return apiFetch<SourceListResult>(`${domainChapterBase(knowledgeSource)}/sources`);
}

export async function addUrlSource(
  url: string,
  knowledgeSource: string = getStoredKnowledgeSource(),
): Promise<SourceEntry> {
  return apiFetch<SourceEntry>(`${domainChapterBase(knowledgeSource)}/sources/url`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  });
}

export async function deleteSource(
  sourceId: string,
  knowledgeSource: string = getStoredKnowledgeSource(),
): Promise<SourceListResult> {
  return apiFetch<SourceListResult>(
    `${domainChapterBase(knowledgeSource)}/sources/${encodeURIComponent(sourceId)}`,
    { method: 'DELETE' },
  );
}

export async function getChapterArtifact(
  knowledgeSource: string = getStoredKnowledgeSource(),
): Promise<ChapterArtifactStatus> {
  return apiFetch<ChapterArtifactStatus>(`${domainChapterBase(knowledgeSource)}/artifact`);
}

export async function startCompile(
  knowledgeSource: string = getStoredKnowledgeSource(),
): Promise<CompileStatus> {
  return apiFetch<CompileStatus>(`${domainChapterBase(knowledgeSource)}/compile`, {
    method: 'POST',
  });
}

export async function getCompileStatus(
  knowledgeSource: string = getStoredKnowledgeSource(),
): Promise<CompileStatus> {
  return apiFetch<CompileStatus>(`${domainChapterBase(knowledgeSource)}/compile/status`);
}

export async function approveCompile(
  knowledgeSource: string = getStoredKnowledgeSource(),
): Promise<ChapterArtifactStatus> {
  return apiFetch<ChapterArtifactStatus>(
    `${domainChapterBase(knowledgeSource)}/compile/approve`,
    { method: 'POST' },
  );
}

export async function getWikiPreview(
  source: 'staging' | 'published',
  knowledgeSource: string = getStoredKnowledgeSource(),
): Promise<WikiPreview> {
  return apiFetch<WikiPreview>(
    `${domainChapterBase(knowledgeSource)}/wiki?source=${source}`,
  );
}

export async function setConceptOrder(
  order: string[],
  source: 'staging' | 'published',
  knowledgeSource: string = getStoredKnowledgeSource(),
): Promise<WikiPreview> {
  return apiFetch<WikiPreview>(
    `${domainChapterBase(knowledgeSource)}/concept-order?source=${source}`,
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ order }),
    },
  );
}
