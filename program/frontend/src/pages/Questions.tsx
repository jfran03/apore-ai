import { useCallback, useEffect, useRef, useState } from 'react';
import {
  addQuestionBankEntry,
  deleteQuestionBankEntry,
  generateQuestionBank,
  getQuestionBank,
  getQuestionBankGenerateStatus,
  getStoredKnowledgeSource,
  setStoredKnowledgeSource,
  updateQuestionBankEntry,
} from '../api/client';
import type { QuestionBankEntry, QuestionBankGenerateStatus } from '../api/types';
import { parseKnowledgeSource, useActiveDomain } from '../shell/ActiveDomainContext';
import '../styles/questions.css';

const EMPTY_ENTRY: QuestionBankEntry = {
  id: '',
  concept_id: '',
  type: 'recall',
  intended_difficulty: 0.25,
  text: '',
};

const POLL_INTERVAL_MS = 1500;

function isActiveGeneration(status: QuestionBankGenerateStatus): boolean {
  return status.status === 'running';
}

export function Questions() {
  const { activeDomain, catalogError } = useActiveDomain();
  const [knowledgeSource, setKnowledgeSource] = useState(getStoredKnowledgeSource());
  const [questions, setQuestions] = useState<QuestionBankEntry[]>([]);
  const [bankPath, setBankPath] = useState('');
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [generateStatus, setGenerateStatus] = useState<QuestionBankGenerateStatus | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<QuestionBankEntry>({ ...EMPTY_ENTRY });
  const pollTimerRef = useRef<number | null>(null);

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current !== null) {
      window.clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }, []);

  const loadBank = useCallback(async (source: string) => {
    setLoading(true);
    setError(null);
    try {
      const bank = await getQuestionBank(source);
      setQuestions(bank.questions);
      setBankPath(bank.path);
    } catch (err) {
      setQuestions([]);
      setBankPath('');
      setError(err instanceof Error ? err.message : 'Failed to load question bank');
    } finally {
      setLoading(false);
    }
  }, []);

  const handleGenerationFinished = useCallback(
    async (status: QuestionBankGenerateStatus, source: string) => {
      stopPolling();
      setGenerating(false);
      setGenerateStatus(status);

      if (status.status === 'completed') {
        setMessage(
          `Generated ${status.questions ?? 0} questions across ${status.concepts ?? 0} concepts.`,
        );
        await loadBank(source);
        return;
      }

      if (status.status === 'failed') {
        setError(status.error ?? 'Question bank generation failed');
      }
    },
    [loadBank, stopPolling],
  );

  const pollGenerationStatus = useCallback(
    (source: string) => {
      stopPolling();
      pollTimerRef.current = window.setInterval(async () => {
        try {
          const status = await getQuestionBankGenerateStatus(source);
          setGenerateStatus(status);
          if (!isActiveGeneration(status)) {
            await handleGenerationFinished(status, source);
          }
        } catch (err) {
          stopPolling();
          setGenerating(false);
          setError(err instanceof Error ? err.message : 'Failed to check generation status');
        }
      }, POLL_INTERVAL_MS);
    },
    [handleGenerationFinished, stopPolling],
  );

  const resumeGenerationIfRunning = useCallback(
    async (source: string) => {
      try {
        const status = await getQuestionBankGenerateStatus(source);
        setGenerateStatus(status);
        if (isActiveGeneration(status)) {
          setGenerating(true);
          pollGenerationStatus(source);
        } else {
          setGenerating(false);
        }
      } catch {
        setGenerating(false);
        setGenerateStatus(null);
      }
    },
    [pollGenerationStatus],
  );

  // Keep the selected chapter inside the active domain (workspace). When the
  // sidebar switches domains, snap to the first chapter of the new domain
  // unless the current selection already belongs to it.
  useEffect(() => {
    if (!activeDomain?.chapters.length) return;
    const parsed = parseKnowledgeSource(knowledgeSource);
    const stillValid =
      parsed?.domainId === activeDomain.id &&
      activeDomain.chapters.some((c) => c.id === parsed.chapterId);
    if (!stillValid) {
      const next = activeDomain.chapters[0].knowledge_source;
      setKnowledgeSource(next);
      setStoredKnowledgeSource(next);
    }
  }, [activeDomain, knowledgeSource]);

  useEffect(() => {
    loadBank(knowledgeSource);
    resumeGenerationIfRunning(knowledgeSource);
    return () => stopPolling();
  }, [knowledgeSource, loadBank, resumeGenerationIfRunning, stopPolling]);

  const chapterOptions = activeDomain?.chapters ?? [];

  const resetForm = () => {
    setEditingId(null);
    setForm({ ...EMPTY_ENTRY });
  };

  const handleEdit = (q: QuestionBankEntry) => {
    setEditingId(q.id);
    setForm({
      id: q.id,
      concept_id: q.concept_id,
      type: q.type,
      intended_difficulty: q.intended_difficulty,
      text: q.text,
    });
  };

  const handleSubmit = async () => {
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      if (editingId) {
        await updateQuestionBankEntry(editingId, form, knowledgeSource);
        setMessage(`Updated question ${editingId}`);
      } else {
        await addQuestionBankEntry(form, knowledgeSource);
        setMessage(`Added question ${form.id}`);
      }
      resetForm();
      await loadBank(knowledgeSource);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (questionId: string) => {
    if (!window.confirm(`Delete question ${questionId}?`)) return;
    setLoading(true);
    setError(null);
    try {
      await deleteQuestionBankEntry(questionId, knowledgeSource);
      setMessage(`Deleted ${questionId}`);
      if (editingId === questionId) resetForm();
      await loadBank(knowledgeSource);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Delete failed');
    } finally {
      setLoading(false);
    }
  };

  const handleGenerate = async () => {
    setGenerating(true);
    setError(null);
    setMessage(null);
    try {
      const status = await generateQuestionBank(knowledgeSource);
      setGenerateStatus(status);
      if (isActiveGeneration(status)) {
        pollGenerationStatus(knowledgeSource);
        return;
      }
      await handleGenerationFinished(status, knowledgeSource);
    } catch (err) {
      setGenerating(false);
      setError(err instanceof Error ? err.message : 'Generate failed');
    }
  };

  const busy = loading || generating;
  const progressLabel =
    generateStatus && generateStatus.concepts_total > 0
      ? `${generateStatus.concepts_done} of ${generateStatus.concepts_total} concepts`
      : 'starting';

  return (
    <main className="questions-page">
      <h1 className="questions-page__title">Question bank</h1>
      <p className="questions-page__lead">
        Questions for <strong>{activeDomain?.id ?? '…'}</strong>. Pre-authored questions are
        selected during Study by difficulty and type; depth comes from the concept graph,
        not from each question row.
      </p>
      {catalogError && (
        <p className="questions-status questions-status--error">{catalogError}</p>
      )}

      <div className="questions-toolbar">
        <label>
          Chapter
          <select
            value={knowledgeSource}
            disabled={generating}
            onChange={(e) => {
              const v = e.target.value;
              setKnowledgeSource(v);
              setStoredKnowledgeSource(v);
            }}
          >
            {chapterOptions.map((c) => (
              <option key={c.id} value={c.knowledge_source}>
                {c.id}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          className="btn btn--secondary"
          disabled={busy}
          onClick={() => loadBank(knowledgeSource)}
        >
          Reload
        </button>
        <button
          type="button"
          className="btn btn--primary"
          disabled={busy}
          onClick={handleGenerate}
        >
          {generating ? 'Generating…' : 'Generate bank'}
        </button>
      </div>

      {generating && (
        <div
          className="questions-generating"
          role="status"
          aria-live="polite"
          aria-label="Generating question bank"
        >
          <span className="questions-generating__label">
            Generating question bank — {progressLabel}
          </span>
          <span className="questions-generating__dots" aria-hidden="true">
            <span />
            <span />
            <span />
          </span>
        </div>
      )}

      {bankPath && (
        <p className="questions-page__lead" style={{ marginTop: 0 }}>
          Bank file: {bankPath} ({questions.length} questions)
        </p>
      )}

      <div className="questions-table-wrap">
        <table className="questions-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Concept</th>
              <th>Depth</th>
              <th>Type</th>
              <th>Difficulty</th>
              <th>Question</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {questions.length === 0 && (
              <tr>
                <td colSpan={7}>
                  {generating
                    ? 'Generating questions…'
                    : 'No questions yet. Generate a bank or add one below.'}
                </td>
              </tr>
            )}
            {questions.map((q) => (
              <tr key={q.id}>
                <td>{q.id}</td>
                <td>{q.concept_id}</td>
                <td>{q.depth ?? '—'}</td>
                <td>{q.type}</td>
                <td>{q.intended_difficulty.toFixed(2)}</td>
                <td className="questions-table__text">{q.text}</td>
                <td className="questions-table__actions">
                  <button
                    type="button"
                    className="btn btn--ghost"
                    disabled={generating}
                    onClick={() => handleEdit(q)}
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    className="btn btn--ghost"
                    disabled={generating}
                    onClick={() => handleDelete(q.id)}
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <form
        className="questions-form"
        onSubmit={(e) => {
          e.preventDefault();
          handleSubmit();
        }}
      >
        <h2>{editingId ? `Edit ${editingId}` : 'Add question'}</h2>
        <div className="questions-form__grid">
          <label>
            ID
            <input
              value={form.id}
              disabled={!!editingId || generating}
              onChange={(e) => setForm({ ...form, id: e.target.value })}
              required
            />
          </label>
          <label>
            Concept ID
            <input
              value={form.concept_id}
              disabled={generating}
              onChange={(e) => setForm({ ...form, concept_id: e.target.value })}
              required
            />
          </label>
          <label>
            Type
            <select
              value={form.type}
              disabled={generating}
              onChange={(e) => setForm({ ...form, type: e.target.value })}
            >
              <option value="recall">recall</option>
              <option value="apply">apply</option>
              <option value="synthesis">synthesis</option>
            </select>
          </label>
          <label>
            Intended difficulty
            <input
              type="number"
              min={0.1}
              max={0.9}
              step={0.01}
              value={form.intended_difficulty}
              disabled={generating}
              onChange={(e) =>
                setForm({ ...form, intended_difficulty: parseFloat(e.target.value) })
              }
            />
          </label>
          <label className="questions-form__full">
            Question text
            <textarea
              value={form.text}
              disabled={generating}
              onChange={(e) => setForm({ ...form, text: e.target.value })}
              required
            />
          </label>
        </div>
        <button type="submit" className="btn btn--primary" disabled={busy}>
          {editingId ? 'Save changes' : 'Add question'}
        </button>
        {editingId && (
          <button
            type="button"
            className="btn btn--ghost"
            style={{ marginLeft: '0.5rem' }}
            disabled={generating}
            onClick={resetForm}
          >
            Cancel
          </button>
        )}
      </form>

      {error && <p className="questions-status questions-status--error">{error}</p>}
      {message && <p className="questions-status questions-status--ok">{message}</p>}
    </main>
  );
}
