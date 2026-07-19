import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  addQuestionBankEntry,
  deleteQuestionBankEntry,
  generateQuestionBank,
  getQuestionBank,
  getQuestionBankGenerateStatus,
  getWikiPreview,
  updateQuestionBankEntry,
} from '../../api/client';
import type { QuestionBankEntry, QuestionBankGenerateStatus } from '../../api/types';

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

function humanizeConceptId(conceptId: string): string {
  const words = conceptId.replace(/[_-]+/g, ' ').trim();
  if (!words) return conceptId;
  return words.charAt(0).toUpperCase() + words.slice(1);
}

interface ConceptMeta {
  label: string;
  depth: number | null;
  order: number;
}

interface ConceptGroup {
  conceptId: string;
  label: string;
  depth: number | null;
  order: number;
  questions: QuestionBankEntry[];
}

function buildConceptGroups(
  questions: QuestionBankEntry[],
  metaById: Map<string, ConceptMeta>,
): ConceptGroup[] {
  const groups = new Map<string, ConceptGroup>();
  for (const q of questions) {
    let group = groups.get(q.concept_id);
    if (!group) {
      const meta = metaById.get(q.concept_id);
      group = {
        conceptId: q.concept_id,
        label: meta?.label ?? humanizeConceptId(q.concept_id),
        depth: meta?.depth ?? q.depth ?? null,
        order: meta?.order ?? Number.POSITIVE_INFINITY,
        questions: [],
      };
      groups.set(q.concept_id, group);
    }
    group.questions.push(q);
  }
  return [...groups.values()].sort((a, b) => {
    if (a.order !== b.order) return a.order - b.order;
    const da = a.depth ?? Number.POSITIVE_INFINITY;
    const db = b.depth ?? Number.POSITIVE_INFINITY;
    if (da !== db) return da - db;
    return a.label.localeCompare(b.label);
  });
}

function EditIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M12 20h9" />
      <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4Z" />
    </svg>
  );
}

function DeleteIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M3 6h18" />
      <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
      <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
      <path d="M10 11v6" />
      <path d="M14 11v6" />
    </svg>
  );
}

interface QuestionBankPanelProps {
  knowledgeSource: string;
  canGenerate: boolean;
  generateBlockedReason: string | null;
  onGenerated?: () => void;
}

export function QuestionBankPanel({
  knowledgeSource,
  canGenerate,
  generateBlockedReason,
  onGenerated,
}: QuestionBankPanelProps) {
  const [questions, setQuestions] = useState<QuestionBankEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [generateStatus, setGenerateStatus] = useState<QuestionBankGenerateStatus | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<QuestionBankEntry>({ ...EMPTY_ENTRY });
  const [showForm, setShowForm] = useState(false);
  const [conceptMeta, setConceptMeta] = useState<Map<string, ConceptMeta>>(new Map());
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
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
    } catch (err) {
      setQuestions([]);
      setError(err instanceof Error ? err.message : 'Failed to load question bank');
    } finally {
      setLoading(false);
    }
  }, []);

  const loadConceptMeta = useCallback(async (source: string) => {
    try {
      const wiki = await getWikiPreview('published', source);
      const map = new Map<string, ConceptMeta>();
      wiki.pages.forEach((page, index) => {
        map.set(page.concept_id, {
          label: page.label,
          depth: page.depth,
          order: page.order ?? index,
        });
      });
      setConceptMeta(map);
    } catch {
      setConceptMeta(new Map());
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
        await loadConceptMeta(source);
        onGenerated?.();
        return;
      }
      if (status.status === 'failed') {
        setError(status.error ?? 'Question bank generation failed');
      }
    },
    [loadBank, loadConceptMeta, stopPolling, onGenerated],
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

  useEffect(() => {
    setMessage(null);
    setError(null);
    loadBank(knowledgeSource);
    loadConceptMeta(knowledgeSource);
    resumeGenerationIfRunning(knowledgeSource);
    return () => stopPolling();
  }, [knowledgeSource, loadBank, loadConceptMeta, resumeGenerationIfRunning, stopPolling]);

  const conceptGroups = useMemo(
    () => buildConceptGroups(questions, conceptMeta),
    [questions, conceptMeta],
  );

  const resetForm = () => {
    setEditingId(null);
    setForm({ ...EMPTY_ENTRY });
    setShowForm(false);
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
    setShowForm(true);
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
    <section className="wb-panel" aria-label="Question bank">
      <div className="wb-panel__head">
        <div>
          <h2 className="wb-panel__title">Question bank</h2>
          <p className="wb-panel__sub">
            {questions.length} question{questions.length === 1 ? '' : 's'}. Study selects by
            difficulty and type; depth comes from the concept graph.
          </p>
        </div>
        <div className="wb-actions">
          <button
            type="button"
            className="btn btn--ghost"
            disabled={busy}
            onClick={() => loadBank(knowledgeSource)}
          >
            Reload
          </button>
          <button
            type="button"
            className="btn btn--primary"
            disabled={busy || !canGenerate}
            title={!canGenerate && generateBlockedReason ? generateBlockedReason : undefined}
            onClick={handleGenerate}
          >
            {generating ? 'Generating…' : 'Generate bank'}
          </button>
        </div>
      </div>

      {!canGenerate && generateBlockedReason && (
        <p className="wb-note" role="status">
          {generateBlockedReason}
        </p>
      )}

      {generating && (
        <div className="wb-progress" role="status" aria-live="polite">
          <span className="wb-progress__label">Generating question bank — {progressLabel}</span>
          <span className="wb-progress__dots" aria-hidden="true">
            <span />
            <span />
            <span />
          </span>
        </div>
      )}

      {questions.length === 0 ? (
        <div className="wb-empty">
          <p>
            {generating
              ? 'Generating questions…'
              : 'No questions yet. Generate a bank or add one manually.'}
          </p>
        </div>
      ) : (
        <div className="wb-qbank">
          {conceptGroups.map((group) => {
            const open = expanded[group.conceptId] ?? false;
            const panelId = `qbank-${group.conceptId}`;
            return (
              <section key={group.conceptId} className="wb-qbank__group">
                <button
                  type="button"
                  className="wb-wiki__toggle"
                  aria-expanded={open}
                  aria-controls={panelId}
                  onClick={() =>
                    setExpanded((prev) => ({
                      ...prev,
                      [group.conceptId]: !open,
                    }))
                  }
                >
                  <span className="wb-wiki__page-label">{group.label}</span>
                  {group.depth !== null && (
                    <span className="wb-wiki__page-depth">depth {group.depth}</span>
                  )}
                  <span className="wb-qbank__count">
                    {group.questions.length} question{group.questions.length === 1 ? '' : 's'}
                  </span>
                  <span className="wb-wiki__chevron" aria-hidden="true">
                    {open ? '▾' : '▸'}
                  </span>
                </button>
                {open && (
                  <div id={panelId} className="wb-table-wrap">
                    <table className="wb-table">
                      <thead>
                        <tr>
                          <th>ID</th>
                          <th>Depth</th>
                          <th>Type</th>
                          <th>Difficulty</th>
                          <th>Question</th>
                          <th aria-label="Actions" />
                        </tr>
                      </thead>
                      <tbody>
                        {group.questions.map((q) => (
                          <tr key={q.id}>
                            <td>{q.id}</td>
                            <td>{q.depth ?? '—'}</td>
                            <td>{q.type}</td>
                            <td>{q.intended_difficulty.toFixed(2)}</td>
                            <td className="wb-table__text">{q.text}</td>
                            <td className="wb-table__actions">
                              <button
                                type="button"
                                className="wb-icon-btn"
                                disabled={generating}
                                aria-label={`Edit question ${q.id}`}
                                title="Edit question"
                                onClick={() => handleEdit(q)}
                              >
                                <EditIcon />
                              </button>
                              <button
                                type="button"
                                className="wb-icon-btn wb-icon-btn--danger"
                                disabled={generating}
                                aria-label={`Delete question ${q.id}`}
                                title="Delete question"
                                onClick={() => handleDelete(q.id)}
                              >
                                <DeleteIcon />
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>
            );
          })}
        </div>
      )}

      {!showForm ? (
        <button
          type="button"
          className="btn btn--ghost wb-add-toggle"
          disabled={generating}
          onClick={() => {
            resetForm();
            setShowForm(true);
          }}
        >
          + Add question manually
        </button>
      ) : (
        <form
          className="wb-form"
          onSubmit={(e) => {
            e.preventDefault();
            handleSubmit();
          }}
        >
          <h3 className="wb-form__title">{editingId ? `Edit ${editingId}` : 'Add question'}</h3>
          <div className="wb-form__grid">
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
            <label className="wb-form__full">
              Question text
              <textarea
                value={form.text}
                disabled={generating}
                onChange={(e) => setForm({ ...form, text: e.target.value })}
                required
              />
            </label>
          </div>
          <div className="wb-actions">
            <button type="submit" className="btn btn--primary" disabled={busy}>
              {editingId ? 'Save changes' : 'Add question'}
            </button>
            <button
              type="button"
              className="btn btn--ghost"
              disabled={generating}
              onClick={resetForm}
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      {error && <p className="wb-status wb-status--error">{error}</p>}
      {message && <p className="wb-status wb-status--ok">{message}</p>}
    </section>
  );
}
