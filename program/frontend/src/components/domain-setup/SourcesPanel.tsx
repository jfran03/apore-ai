import { useCallback, useEffect, useRef, useState } from 'react';
import {
  deleteSource,
  getChapterSources,
} from '../../api/client';
import type { CompileStage, SourceEntry } from '../../api/types';
import { parseKnowledgeSource } from '../../shell/ActiveDomainContext';
import {
  dismiss,
  enqueueFiles,
  enqueueUrl,
  getPending,
  hasInFlight,
  subscribe,
  subscribeSettled,
  type PendingUpload,
} from './sourceUploadStore';

interface SourcesPanelProps {
  knowledgeSource: string;
  compileStage: CompileStage;
  onSourcesChanged: () => void;
  onCompile: () => Promise<void>;
}

function formatBytes(size: number | null): string {
  if (!size) return '—';
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

export function SourcesPanel({
  knowledgeSource,
  compileStage,
  onSourcesChanged,
  onCompile,
}: SourcesPanelProps) {
  const [sources, setSources] = useState<SourceEntry[]>([]);
  const [pending, setPending] = useState<PendingUpload[]>(() =>
    getPending(knowledgeSource),
  );
  const [loading, setLoading] = useState(false);
  const [compilingStart, setCompilingStart] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [url, setUrl] = useState('');
  const [urlModalOpen, setUrlModalOpen] = useState(false);
  const [urlError, setUrlError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const urlInputRef = useRef<HTMLInputElement>(null);
  const knowledgeSourceRef = useRef(knowledgeSource);
  const onSourcesChangedRef = useRef(onSourcesChanged);

  const parsed = parseKnowledgeSource(knowledgeSource);

  useEffect(() => {
    knowledgeSourceRef.current = knowledgeSource;
  }, [knowledgeSource]);

  useEffect(() => {
    onSourcesChangedRef.current = onSourcesChanged;
  }, [onSourcesChanged]);

  const refreshSources = useCallback(async (source: string) => {
    const res = await getChapterSources(source);
    if (knowledgeSourceRef.current !== source) return;
    setSources(res.sources);
  }, []);

  const load = useCallback(
    async (source: string) => {
      setLoading(true);
      try {
        await refreshSources(source);
      } catch (err) {
        if (knowledgeSourceRef.current === source) {
          setError(err instanceof Error ? err.message : 'Failed to load sources');
        }
      } finally {
        if (knowledgeSourceRef.current === source) {
          setLoading(false);
        }
      }
    },
    [refreshSources],
  );

  // Subscribe to this chapter's pending rows only; do not clear the store.
  useEffect(() => {
    setPending(getPending(knowledgeSource));
    return subscribe(knowledgeSource, () => {
      setPending(getPending(knowledgeSource));
    });
  }, [knowledgeSource]);

  // Soft-refresh when an upload for the active chapter settles (works after remount).
  useEffect(() => {
    return subscribeSettled((settledSource) => {
      if (settledSource !== knowledgeSourceRef.current) return;
      void refreshSources(settledSource)
        .then(() => {
          onSourcesChangedRef.current();
          setError(null);
        })
        .catch((err) => {
          setError(err instanceof Error ? err.message : 'Failed to refresh sources');
        });
    });
  }, [refreshSources]);

  useEffect(() => {
    setError(null);
    setMessage(null);
    load(knowledgeSource);
  }, [knowledgeSource, load]);

  useEffect(() => {
    if (!urlModalOpen) return;
    urlInputRef.current?.focus();
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setUrlModalOpen(false);
        setUrl('');
        setUrlError(null);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [urlModalOpen]);

  const handleFiles = useCallback(
    (files: File[]) => {
      if (!files.length || !parsed) return;
      setError(null);
      setMessage(null);
      enqueueFiles(knowledgeSource, files);
    },
    [parsed, knowledgeSource],
  );

  const openUrlModal = () => {
    setUrlError(null);
    setUrlModalOpen(true);
  };

  const closeUrlModal = () => {
    setUrlModalOpen(false);
    setUrl('');
    setUrlError(null);
  };

  const openFilePicker = () => {
    fileInputRef.current?.click();
  };

  const handleAddUrl = () => {
    const trimmed = url.trim();
    if (!trimmed || !parsed) return;
    setUrlError(null);
    setError(null);
    setMessage(null);
    enqueueUrl(knowledgeSource, trimmed);
    closeUrlModal();
  };

  const dismissPending = (localId: string) => {
    dismiss(knowledgeSource, localId);
  };

  const handleDelete = async (sourceId: string) => {
    setDeletingId(sourceId);
    setError(null);
    try {
      const res = await deleteSource(sourceId, knowledgeSource);
      setSources(res.sources);
      onSourcesChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Delete failed');
    } finally {
      setDeletingId(null);
    }
  };

  const uploadsInFlight = hasInFlight(knowledgeSource);
  const compiling =
    compileStage === 'normalizing' ||
    compileStage === 'compiling' ||
    compileStage === 'validating';
  const usableSources = sources.filter(
    (s) => s.normalize_status === 'ok' || s.normalize_status === 'legacy',
  );
  const canCompile =
    usableSources.length > 0 && !compiling && !compilingStart && !uploadsInFlight;

  const handleCompileClick = async () => {
    setCompilingStart(true);
    setError(null);
    try {
      await onCompile();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Compile failed to start');
    } finally {
      setCompilingStart(false);
    }
  };

  const showEmpty = !loading && sources.length === 0 && pending.length === 0;

  return (
    <section className="wb-panel" aria-label="Sources">
      <div className="wb-panel__head">
        <div>
          <h2 className="wb-panel__title">Sources</h2>
          <p className="wb-panel__sub">
            Upload documents, JSON, JPEG/PNG images, or add a YouTube link. Each source is
            converted to markdown for the compiler.
          </p>
        </div>
        <button
          type="button"
          className="btn btn--primary"
          disabled={!canCompile}
          title={
            uploadsInFlight
              ? 'Wait for uploads to finish'
              : usableSources.length === 0
                ? 'Add at least one source that converts successfully'
                : undefined
          }
          onClick={handleCompileClick}
        >
          {compiling ? 'Compiling…' : 'Compile wiki'}
        </button>
      </div>

      <div
        className={`wb-dropzone${dragOver ? ' wb-dropzone--over' : ''}`}
        role="button"
        tabIndex={0}
        aria-label="Upload sources: drop files here or click to browse"
        onClick={openFilePicker}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            openFilePicker();
          }
        }}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          handleFiles(Array.from(e.dataTransfer.files));
        }}
      >
        <p className="wb-dropzone__text">Drop files here, or click to upload</p>
        <p className="wb-dropzone__hint">
          PDF, DOCX, PPTX, HTML, Markdown, CSV, JSON, JPEG, PNG, and more. Images are
          analyzed by your configured vision model.
        </p>
        <div className="wb-dropzone__actions">
          <button
            type="button"
            className="btn btn--secondary"
            onClick={(e) => {
              e.stopPropagation();
              openFilePicker();
            }}
          >
            Upload files
          </button>
          <button
            type="button"
            className="btn btn--secondary"
            onClick={(e) => {
              e.stopPropagation();
              openUrlModal();
            }}
          >
            YouTube
          </button>
        </div>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          hidden
          accept=".pdf,.html,.htm,.md,.markdown,.txt,.docx,.pptx,.xlsx,.csv,.json,.xml,.epub,.jpg,.jpeg,.png,application/pdf,text/html,text/markdown,text/plain,text/csv,application/json,image/jpeg,image/png"
          onChange={(e) => {
            handleFiles(Array.from(e.target.files ?? []));
            e.target.value = '';
          }}
        />
      </div>

      <ul className="wb-source-list">
        {loading && pending.length === 0 && (
          <li className="wb-source-list__empty">Loading sources…</li>
        )}
        {showEmpty && <li className="wb-source-list__empty">No sources yet.</li>}
        {pending.map((p) => (
          <li
            key={p.localId}
            className="wb-source wb-source--pending"
            aria-busy={p.status !== 'failed'}
          >
            <span className="wb-source__icon" aria-hidden="true">
              {p.status === 'failed' ? (
                p.kind === 'url' ? (
                  '🔗'
                ) : (
                  '📄'
                )
              ) : (
                <span className="wb-source__spinner" />
              )}
            </span>
            <span className="wb-source__main">
              <span className="wb-source__name" title={p.name}>
                {p.name}
              </span>
              <span className="wb-source__meta">
                {p.kind === 'file' ? formatBytes(p.size) : 'link'}
                {p.status === 'uploading' && (
                  <span className="wb-source__badge">Uploading…</span>
                )}
                {p.status === 'queued' && (
                  <span className="wb-source__badge">Queued</span>
                )}
                {p.status === 'failed' && (
                  <span className="wb-source__badge wb-source__badge--error">
                    upload failed
                  </span>
                )}
              </span>
              {p.status === 'failed' && p.error && (
                <span className="wb-source__error">{p.error}</span>
              )}
            </span>
            {p.status === 'failed' ? (
              <button
                type="button"
                className="btn btn--ghost wb-source__delete"
                onClick={() => dismissPending(p.localId)}
                aria-label={`Dismiss ${p.name}`}
              >
                Dismiss
              </button>
            ) : (
              <span className="wb-source__pending-slot" aria-hidden="true" />
            )}
          </li>
        ))}
        {sources.map((s) => (
          <li key={s.id} className="wb-source">
            <span className="wb-source__icon" aria-hidden="true">
              {s.kind === 'url' ? '🔗' : '📄'}
            </span>
            <span className="wb-source__main">
              <span className="wb-source__name" title={s.display_name ?? s.id}>
                {s.display_name ?? s.id}
              </span>
              <span className="wb-source__meta">
                {s.kind === 'file' ? formatBytes(s.size) : 'link'}
                {s.normalize_status === 'failed' && (
                  <span className="wb-source__badge wb-source__badge--error">
                    conversion failed
                  </span>
                )}
                {s.normalize_status === 'pending' && (
                  <span className="wb-source__badge">pending</span>
                )}
                {s.normalize_status === 'legacy' && (
                  <span className="wb-source__badge">legacy</span>
                )}
              </span>
              {s.normalize_status === 'failed' && s.normalize_error && (
                <span className="wb-source__error">{s.normalize_error}</span>
              )}
            </span>
            <button
              type="button"
              className="btn btn--ghost wb-source__delete"
              disabled={deletingId === s.id}
              onClick={() => handleDelete(s.id)}
              aria-label={`Remove ${s.display_name ?? s.id}`}
            >
              {deletingId === s.id ? 'Removing…' : 'Remove'}
            </button>
          </li>
        ))}
      </ul>

      {error && <p className="wb-status wb-status--error">{error}</p>}
      {message && <p className="wb-status wb-status--ok">{message}</p>}

      {urlModalOpen && (
        <div
          className="wb-modal"
          role="presentation"
          onClick={(e) => {
            if (e.target === e.currentTarget) closeUrlModal();
          }}
        >
          <form
            className="wb-modal__dialog"
            role="dialog"
            aria-modal="true"
            aria-label="Add YouTube link"
            onSubmit={(e) => {
              e.preventDefault();
              handleAddUrl();
            }}
          >
            <h3 className="wb-modal__title">Add YouTube link</h3>
            <p className="wb-modal__body">
              Paste a YouTube URL. The transcript is converted to markdown for the compiler.
            </p>
            <input
              ref={urlInputRef}
              className="wb-input"
              type="url"
              placeholder="https://www.youtube.com/watch?v=…"
              value={url}
              onChange={(e) => {
                setUrl(e.target.value);
                if (urlError) setUrlError(null);
              }}
              aria-label="YouTube URL"
            />
            {urlError && <p className="wb-modal__error">{urlError}</p>}
            <div className="wb-modal__actions">
              <button type="button" className="btn btn--ghost" onClick={closeUrlModal}>
                Cancel
              </button>
              <button type="submit" className="btn btn--primary" disabled={!url.trim()}>
                Add link
              </button>
            </div>
          </form>
        </div>
      )}
    </section>
  );
}
