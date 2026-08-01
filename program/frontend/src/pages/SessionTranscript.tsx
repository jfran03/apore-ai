import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { getSessionTranscript } from '../api/client';
import type { SessionTranscript } from '../api/types';
import { SessionHistory } from '../components/SessionHistory';

function statusLabel(status: SessionTranscript['status']): string | null {
  if (status === 'active') return 'In progress';
  if (status === 'ended_early') return 'Ended early';
  if (status === 'completed') return 'Completed';
  return null;
}

export function SessionTranscriptPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
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
  const canResume =
    transcript.status === 'active' || transcript.status === 'ended_early';

  return (
    <main className="page">
      <header className="transcript-header">
        <div className="transcript-header__text">
          <h1 className="page__title">{transcript.title}</h1>
          <p className="page__subtitle">
            {transcript.knowledge_source} · {new Date(transcript.created_at).toLocaleString()} ·{' '}
            {transcript.focus_mode} · {transcript.max_questions} questions
            {lifecycle ? ` · ${lifecycle}` : ''}
          </p>
        </div>
        {canResume && (
          <button
            type="button"
            className="btn btn--primary"
            onClick={() => {
              navigate(`/study?session=${encodeURIComponent(transcript.session_id)}`);
            }}
          >
            Resume session
          </button>
        )}
      </header>
      <SessionHistory questions={transcript.questions ?? []} />
    </main>
  );
}
