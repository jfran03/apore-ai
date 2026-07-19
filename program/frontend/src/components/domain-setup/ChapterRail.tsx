import { useState } from 'react';
import { createChapter } from '../../api/client';
import type { KnowledgeChapter } from '../../api/types';
import { useActiveDomain } from '../../shell/ActiveDomainContext';

function chapterBadge(chapter: KnowledgeChapter): { label: string; tone: string } {
  const active =
    chapter.compile_stage === 'normalizing' ||
    chapter.compile_stage === 'compiling' ||
    chapter.compile_stage === 'validating';
  if (active) return { label: 'Compiling', tone: 'busy' };
  if (chapter.compile_stage === 'failed') return { label: 'Failed', tone: 'error' };
  if (chapter.has_unapproved_compile) return { label: 'Review', tone: 'review' };
  if (chapter.is_stale) return { label: 'Stale', tone: 'warn' };
  if (chapter.is_approved && chapter.question_bank_count > 0)
    return { label: 'Ready', tone: 'ok' };
  if (chapter.is_approved) return { label: 'Approved', tone: 'ok' };
  return { label: 'Empty', tone: 'muted' };
}

export function ChapterRail() {
  const { activeDomain, activeChapterId, setActiveChapterId, refreshCatalog } = useActiveDomain();
  const [creating, setCreating] = useState(false);
  const [newId, setNewId] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const chapters = activeDomain?.chapters ?? [];

  const handleCreate = async () => {
    const id = newId.trim();
    if (!id || !activeDomain) return;
    setBusy(true);
    setError(null);
    try {
      await createChapter(activeDomain.id, id);
      await refreshCatalog();
      setActiveChapterId(id);
      setNewId('');
      setCreating(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create chapter');
    } finally {
      setBusy(false);
    }
  };

  return (
    <nav className="wb-rail" aria-label="Chapters">
      <div className="wb-rail__head">
        <span className="wb-rail__title">Chapters</span>
        <button
          type="button"
          className="wb-rail__add"
          onClick={() => setCreating((v) => !v)}
          aria-expanded={creating}
          aria-label="New chapter"
        >
          +
        </button>
      </div>

      {creating && (
        <form
          className="wb-rail__create"
          onSubmit={(e) => {
            e.preventDefault();
            handleCreate();
          }}
        >
          <input
            className="wb-input"
            value={newId}
            autoFocus
            placeholder="02-topic"
            disabled={busy}
            onChange={(e) => setNewId(e.target.value)}
            aria-label="New chapter id"
          />
          <button type="submit" className="btn btn--primary" disabled={busy || !newId.trim()}>
            Add
          </button>
        </form>
      )}
      {error && <p className="wb-status wb-status--error wb-rail__error">{error}</p>}

      <ul className="wb-rail__list">
        {chapters.length === 0 && <li className="wb-rail__empty">No chapters yet.</li>}
        {chapters.map((c) => {
          const badge = chapterBadge(c);
          const selected = c.id === activeChapterId;
          return (
            <li key={c.id}>
              <button
                type="button"
                className={`wb-rail__item${selected ? ' wb-rail__item--active' : ''}`}
                aria-current={selected ? 'true' : undefined}
                onClick={() => setActiveChapterId(c.id)}
              >
                <span className="wb-rail__item-name">{c.id}</span>
                <span className={`wb-badge wb-badge--${badge.tone}`}>{badge.label}</span>
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
