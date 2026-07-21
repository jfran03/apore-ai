import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { getSessionTranscript } from '../api/client';
import type { SessionTranscript } from '../api/types';

function statusLabel(status: SessionTranscript['status']): string | null {
  if (status === 'ended_early') return 'Ended early';
  if (status === 'completed') return 'Completed';
  return null;
}

export function SessionTranscriptPage() {
  const { id } = useParams<{ id: string }>();
  const [transcript, setTranscript] = useState<SessionTranscript | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    setTranscript(null);
    setError(null);
    getSessionTranscript(id)
      .then(setTranscript)
      .catch((err) =>
        setError(err instanceof Error ? err.message : 'Failed to load session'),
      );
  }, [id]);

  if (error) {
    return (
      <main className="page">
        <h1 className="page__title">Session</h1>
        <p className="page__subtitle">{error}</p>
      </main>
    );
  }

  if (!transcript) {
    return (
      <main className="page">
        <p className="page__subtitle">Loading session…</p>
      </main>
    );
  }

  const lifecycle = statusLabel(transcript.status);

  return (
    <main className="page">
      <h1 className="page__title">{transcript.title}</h1>
      <p className="page__subtitle">
        {transcript.knowledge_source} · {new Date(transcript.created_at).toLocaleString()} ·{' '}
        {transcript.focus_mode} · {transcript.max_questions} questions
        {lifecycle ? ` · ${lifecycle}` : ''}
      </p>
      <div className="card transcript">
        <pre className="transcript__pre">{transcript.body}</pre>
      </div>
    </main>
  );
}
