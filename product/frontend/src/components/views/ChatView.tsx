import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { createDomainSession, seedDomain } from '../../api/client';
import type { TranscriptEvent, WorkspaceDomain } from '../../api/types';
import type { BackendState } from '../../hooks/useBackend';
import { useTutorSession } from '../../hooks/useTutorSession';

interface ChatViewProps {
  domain: WorkspaceDomain;
  sessionId: string | null;
  backend: BackendState;
  onSessionCreated: (sessionId: string) => void;
}

export function ChatView(props: ChatViewProps) {
  if (props.sessionId === null) {
    return <NewSessionStarter {...props} />;
  }

  return <LiveSession {...props} sessionId={props.sessionId} />;
}

function NewSessionStarter({ domain, backend, onSessionCreated }: ChatViewProps) {
  const readyChapters = useMemo(
    () => domain.chapters.filter((chapter) => chapter.has_concept_graph),
    [domain.chapters],
  );
  const [chapterId, setChapterId] = useState(readyChapters[0]?.id ?? '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const selectedChapterId = readyChapters.some((chapter) => chapter.id === chapterId)
    ? chapterId
    : readyChapters[0]?.id ?? '';

  useEffect(() => {
    setChapterId(readyChapters[0]?.id ?? '');
    setBusy(false);
    setError(null);
  }, [domain.id, readyChapters]);

  if (readyChapters.length === 0) {
    return (
      <section className="view">
        <article className="panel empty-state">
          <p className="eyebrow">Tutor chat</p>
          <h1>No curriculum compiled yet</h1>
          <p>This domain has no teachable chapters. Source intake ships in a later milestone.</p>
          {backend.health?.testbed && <TestbedSeed domain={domain} />}
        </article>
      </section>
    );
  }

  async function start() {
    setBusy(true);
    setError(null);

    try {
      const created = await createDomainSession(domain.id, {
        chapter_id: selectedChapterId || undefined,
      });
      onSessionCreated(created.session_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setBusy(false);
    }
  }

  return (
    <section className="view">
      <article className="panel empty-state">
        <p className="eyebrow">Tutor chat</p>
        <h1>Start a tutoring session</h1>
        {readyChapters.length > 1 && (
          <label className="field">
            <span className="label">Chapter</span>
            <select
              className="select"
              value={selectedChapterId}
              onChange={(e) => setChapterId(e.target.value)}
            >
              {readyChapters.map((chapter) => (
                <option key={chapter.id} value={chapter.id}>
                  {chapter.id}
                </option>
              ))}
            </select>
          </label>
        )}
        {error && <div className="alert is-error">{error}</div>}
        <button
          className="button-primary"
          onClick={start}
          disabled={busy || backend.status !== 'online'}
        >
          {busy ? 'Starting...' : 'Start session'}
        </button>
      </article>
    </section>
  );
}

function TestbedSeed({ domain }: { domain: WorkspaceDomain }) {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  return (
    <div className="testbed-hint">
      <p className="help">
        Testbed mode: seed this domain with the compiled discrete-math curriculum, or run{' '}
        <span className="inline-code">python scripts/seed_domain.py {domain.id}</span>.
      </p>
      <button
        className="button-secondary"
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          try {
            const seeded = await seedDomain(domain.id);
            setResult(
              `Seeded chapters: ${seeded.chapters.join(', ') || 'none'} - refresh to continue.`,
            );
          } catch (err) {
            setResult(err instanceof Error ? err.message : String(err));
          } finally {
            setBusy(false);
          }
        }}
      >
        {busy ? 'Seeding...' : 'Seed testbed curriculum'}
      </button>
      {result && <p className="help">{result}</p>}
    </div>
  );
}

function LiveSession({
  domain,
  sessionId,
  backend,
}: ChatViewProps & { sessionId: string }) {
  const tutor = useTutorSession(domain.id, sessionId);
  const [draft, setDraft] = useState('');
  const { state } = tutor;

  const providerMissing = !backend.provider?.active_provider;
  const composerEnabled =
    !providerMissing && (state.status === 'awaiting_answer' || state.status === 'reflection');

  function submit(e: FormEvent) {
    e.preventDefault();
    const text = draft.trim();
    if (!text || !composerEnabled) return;

    setDraft('');
    tutor.sendMessage(text);
  }

  return (
    <section className="view">
      <section className="chat-layout panel">
        <article className="chat-transcript">
          <div className="chat-path">
            {domain.name} / Session History / difficulty {state.scalar.toFixed(2)} -{' '}
            {state.questionsAsked}/{state.maxQuestions} questions
          </div>

          {state.transcript.map((event, index) => (
            <TranscriptBlock key={index} event={event} />
          ))}

          {state.status === 'loading_question' && (
            <div className="run-card">
              <div className="run-card-body">
                <span className="run-spinner" />
                <span>Preparing the next question...</span>
              </div>
            </div>
          )}

          {state.status === 'working' && (
            <div className="run-card">
              <div className="run-card-body">
                <span className="run-spinner" />
                <span>Tutor is working...</span>
              </div>
            </div>
          )}

          {state.status === 'awaiting_rating' && (
            <div className="rating-row">
              <span>How did that question feel?</span>
              <button className="rating-chip" onClick={() => tutor.rate('easy')}>
                Easy
              </button>
              <button className="rating-chip" onClick={() => tutor.rate('ok')}>
                Okay
              </button>
              <button className="rating-chip" onClick={() => tutor.rate('hard')}>
                Hard
              </button>
            </div>
          )}

          {state.status === 'reflection' && (
            <div className="rating-row">
              <span>Ask a follow-up about this question, or move on.</span>
              <button className="button-secondary" onClick={tutor.continueNext}>
                Continue to next question
              </button>
            </div>
          )}

          {state.status === 'complete' && (
            <div className="assistant-block">
              <p>
                <strong>Session complete.</strong>
              </p>
              <p>
                {state.questionsAsked} questions - final difficulty{' '}
                <span className="inline-code">{state.scalar.toFixed(2)}</span>. Start a new session
                from the sidebar to keep going.
              </p>
            </div>
          )}

          {state.status === 'error' && (
            <div className="alert is-error">
              {state.error}
              <div className="error-action">
                <button className="button-secondary" onClick={tutor.dismissError}>
                  Dismiss
                </button>
              </div>
            </div>
          )}
        </article>

        <div className="chat-composer-wrap">
          {providerMissing ? (
            <div className="alert is-error">
              No LLM provider configured. Add an API key in Settings to start tutoring.
            </div>
          ) : (
            <form className="chat-composer" onSubmit={submit}>
              <button
                type="button"
                className="composer-icon"
                title="Skip this question"
                onClick={tutor.skip}
                disabled={state.status !== 'awaiting_answer'}
              >
                &gt;
              </button>
              <input
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                placeholder={
                  state.status === 'awaiting_answer'
                    ? 'Answer, or ask for help...'
                    : state.status === 'reflection'
                      ? 'Ask a follow-up about this question...'
                      : state.status === 'awaiting_rating'
                        ? 'Rate the question to continue'
                        : 'Waiting...'
                }
                disabled={!composerEnabled}
              />
              <button type="submit" className="composer-icon" disabled={!composerEnabled}>
                -&gt;
              </button>
            </form>
          )}
        </div>
      </section>
    </section>
  );
}

function TranscriptBlock({ event }: { event: TranscriptEvent }) {
  switch (event.type) {
    case 'question':
      return (
        <div className="assistant-block">
          <p>
            <strong>Q{event.question_number}</strong> -{' '}
            <span className="inline-code">{event.concept_label}</span>
          </p>
          <p>{event.question_text}</p>
        </div>
      );
    case 'learner_message':
      return <div className="prompt-card">{event.text}</div>;
    case 'tutor_message':
      return (
        <div className="assistant-block">
          <p>{event.text}</p>
        </div>
      );
    case 'graded':
      return <div className="system-line">assessment recorded - correct: {event.correct}</div>;
    case 'rating':
      return (
        <div className="system-line">
          rated {event.rating}
          {typeof event.new_difficulty === 'number'
            ? ` - difficulty ${event.new_difficulty.toFixed(2)}`
            : ''}
        </div>
      );
    case 'system':
      return <div className="system-line">{event.text}</div>;
    default:
      return null;
  }
}
