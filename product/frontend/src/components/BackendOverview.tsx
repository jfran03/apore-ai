import { useMemo, useState } from 'react';
import { createSession, getSessionState } from '../api/client';
import type { CreateSessionResponse, SessionStateResponse } from '../api/types';
import type { BackendState } from '../hooks/useBackend';

export function BackendOverview({ backend }: { backend: BackendState }) {
  const { status, health, catalog, provider, error, refresh } = backend;

  const [busy, setBusy] = useState(false);
  const [session, setSession] = useState<CreateSessionResponse | null>(null);
  const [sessionState, setSessionState] = useState<SessionStateResponse | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  // First ready chapter is the natural target for a smoke-test session.
  const knowledgeSource = useMemo(() => {
    const chapter = catalog?.domains
      ?.flatMap((domain) => domain.chapters)
      .find((c) => c.has_concept_graph);
    return chapter?.knowledge_source ?? 'domain:discrete-math/01-set-theory';
  }, [catalog]);

  const domainCount = catalog?.domains.length ?? 0;
  const chapterCount = catalog?.domains.reduce((sum, d) => sum + d.chapters.length, 0) ?? 0;

  async function startSession() {
    setBusy(true);
    setActionError(null);
    setSessionState(null);
    try {
      const created = await createSession(knowledgeSource);
      setSession(created);
      const state = await getSessionState(created.session_id);
      setSessionState(state);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <article className="panel backend-card" style={{ padding: 24, marginBottom: 20 }}>
      <div className="screen-intro" style={{ marginBottom: 8 }}>
        <div>
          <p className="eyebrow">Local runtime</p>
          <h2>Desktop backend</h2>
          <p>
            The React shell talks to a local Python FastAPI runtime over localhost. This panel
            confirms the connection and runs a real round-trip against the tutor runtime.
          </p>
        </div>
        <button className="button-secondary" onClick={refresh} disabled={status === 'checking'}>
          {status === 'checking' ? 'Checking…' : 'Re-check'}
        </button>
      </div>

      {status === 'offline' && (
        <div className="alert is-error">
          Backend offline. Start it with{' '}
          <span className="inline-code">uvicorn apore.api.app:app --port 8000</span> from{' '}
          <span className="inline-code">product/backend</span>.
          {error ? <div style={{ marginTop: 6 }}>{error}</div> : null}
        </div>
      )}

      <div className="backend-grid">
        <StatTile
          label="Connection"
          value={status === 'online' ? 'Online' : status === 'checking' ? 'Checking' : 'Offline'}
          sub={health ? `${health.service} v${health.version}` : '—'}
        />
        <StatTile label="Domains" value={String(domainCount)} sub={`${chapterCount} chapters`} />
        <StatTile
          label="Provider"
          value={provider?.active_provider ?? 'Not set'}
          sub={provider?.active_model ?? 'Configure a key in Settings'}
        />
        <StatTile
          label="Target chapter"
          value={knowledgeSource.split('/').pop() ?? '—'}
          sub={knowledgeSource}
        />
      </div>

      <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginTop: 4 }}>
        <button
          className="button-primary"
          onClick={startSession}
          disabled={status !== 'online' || busy}
        >
          {busy ? 'Starting…' : 'Start tutoring session'}
        </button>
        <span className="help">Creates a real session via POST /sessions and reads its state.</span>
      </div>

      {actionError && <div className="alert is-error">{actionError}</div>}

      {session && sessionState && (
        <div className="code-card">
          {`session_id: ${session.session_id}
title: ${sessionState.title}
knowledge_source: ${sessionState.knowledge_source}
difficulty_scalar: ${sessionState.scalar}
questions_remaining: ${sessionState.questions_remaining}/${sessionState.max_questions}`}
        </div>
      )}
    </article>
  );
}

function StatTile({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="stat-tile">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      <div className="stat-sub">{sub}</div>
    </div>
  );
}
