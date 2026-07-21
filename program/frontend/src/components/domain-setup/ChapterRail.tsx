import { useEffect, useRef, useState } from 'react';
import { createChapter, deleteChapter, renameChapter } from '../../api/client';
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

export function ChapterRail() {
  const { activeDomain, activeChapterId, setActiveChapterId, refreshCatalog } = useActiveDomain();
  const [creating, setCreating] = useState(false);
  const [newId, setNewId] = useState('');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rowError, setRowError] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const renameInputRef = useRef<HTMLInputElement>(null);
  const deleteCancelRef = useRef<HTMLButtonElement>(null);

  const chapters = activeDomain?.chapters ?? [];

  useEffect(() => {
    if (editingId) renameInputRef.current?.focus();
  }, [editingId]);

  useEffect(() => {
    if (!pendingDeleteId) return;
    deleteCancelRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !busy) {
        setPendingDeleteId(null);
        setDeleteError(null);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [pendingDeleteId, busy]);

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

  const startRename = (chapterId: string) => {
    setEditingId(chapterId);
    setEditValue(chapterId);
    setRowError(null);
    setError(null);
    setCreating(false);
  };

  const cancelRename = () => {
    setEditingId(null);
    setEditValue('');
    setRowError(null);
  };

  const handleRename = async (chapterId: string) => {
    const nextId = editValue.trim();
    if (!nextId || !activeDomain) return;
    if (nextId === chapterId) {
      cancelRename();
      return;
    }
    setBusy(true);
    setRowError(null);
    try {
      await renameChapter(activeDomain.id, chapterId, nextId);
      await refreshCatalog();
      setActiveChapterId(nextId);
      cancelRename();
    } catch (err) {
      setRowError(err instanceof Error ? err.message : 'Could not rename chapter');
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async () => {
    if (!pendingDeleteId || !activeDomain) return;
    setBusy(true);
    setDeleteError(null);
    try {
      await deleteChapter(activeDomain.id, pendingDeleteId);
      setPendingDeleteId(null);
      if (editingId === pendingDeleteId) cancelRename();
      await refreshCatalog();
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : 'Could not delete chapter');
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
          onClick={() => {
            setCreating((v) => !v);
            cancelRename();
          }}
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
          const isEditing = editingId === c.id;

          if (isEditing) {
            return (
              <li key={c.id} className="wb-rail__row wb-rail__row--editing">
                <form
                  className="wb-rail__rename"
                  onSubmit={(e) => {
                    e.preventDefault();
                    handleRename(c.id);
                  }}
                >
                  <input
                    ref={renameInputRef}
                    className="wb-input"
                    value={editValue}
                    disabled={busy}
                    onChange={(e) => setEditValue(e.target.value)}
                    aria-label={`Rename chapter ${c.id}`}
                  />
                  <div className="wb-rail__rename-actions">
                    <button
                      type="button"
                      className="btn btn--ghost"
                      disabled={busy}
                      onClick={cancelRename}
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      className="btn btn--primary"
                      disabled={busy || !editValue.trim()}
                    >
                      Save
                    </button>
                  </div>
                  {rowError && <p className="wb-status wb-status--error wb-rail__error">{rowError}</p>}
                </form>
              </li>
            );
          }

          return (
            <li
              key={c.id}
              className={`wb-rail__row${selected ? ' wb-rail__row--active' : ''}`}
            >
              <button
                type="button"
                className={`wb-rail__item${selected ? ' wb-rail__item--active' : ''}`}
                aria-current={selected ? 'true' : undefined}
                onClick={() => setActiveChapterId(c.id)}
              >
                <span className="wb-rail__item-name">{c.id}</span>
                <span className={`wb-badge wb-badge--${badge.tone}`}>{badge.label}</span>
              </button>
              <div className="wb-rail__actions">
                <button
                  type="button"
                  className="wb-icon-btn"
                  aria-label={`Rename chapter ${c.id}`}
                  title="Rename chapter"
                  disabled={busy}
                  onClick={() => startRename(c.id)}
                >
                  <EditIcon />
                </button>
                <button
                  type="button"
                  className="wb-icon-btn wb-icon-btn--danger"
                  aria-label={`Delete chapter ${c.id}`}
                  title="Delete chapter"
                  disabled={busy}
                  onClick={() => {
                    setPendingDeleteId(c.id);
                    setDeleteError(null);
                  }}
                >
                  <DeleteIcon />
                </button>
              </div>
            </li>
          );
        })}
      </ul>

      {pendingDeleteId && (
        <div
          className="wb-modal"
          role="presentation"
          onClick={(e) => {
            if (e.target === e.currentTarget && !busy) {
              setPendingDeleteId(null);
              setDeleteError(null);
            }
          }}
        >
          <div
            className="wb-modal__dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="chapter-delete-title"
          >
            <h3 id="chapter-delete-title" className="wb-modal__title">
              Delete chapter?
            </h3>
            <p className="wb-modal__body">
              Deleting <strong>{pendingDeleteId}</strong> permanently removes everything inside
              it: sources, compiled wiki, concept graph, compile state, approval metadata, and
              the question bank.
            </p>
            {deleteError && <p className="wb-modal__error">{deleteError}</p>}
            <div className="wb-modal__actions">
              <button
                ref={deleteCancelRef}
                type="button"
                className="btn btn--ghost"
                disabled={busy}
                onClick={() => {
                  setPendingDeleteId(null);
                  setDeleteError(null);
                }}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn btn--danger"
                disabled={busy}
                onClick={handleDelete}
              >
                {busy ? 'Deleting…' : 'Delete chapter'}
              </button>
            </div>
          </div>
        </div>
      )}
    </nav>
  );
}
