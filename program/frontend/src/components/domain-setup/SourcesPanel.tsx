import { useCallback, useEffect, useRef, useState } from 'react';
import {
  addUrlSource,
  deleteSource,
  getChapterSources,
  uploadSources,
} from '../../api/client';
import type { CompileStage, SourceEntry } from '../../api/types';
import { parseKnowledgeSource } from '../../shell/ActiveDomainContext';

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
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [url, setUrl] = useState('');
  const [urlModalOpen, setUrlModalOpen] = useState(false);
  const [urlError, setUrlError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const urlInputRef = useRef<HTMLInputElement>(null);

  const parsed = parseKnowledgeSource(knowledgeSource);

  const load = useCallback(async (source: string) => {
    setLoading(true);
    try {
      const res = await getChapterSources(source);
      setSources(res.sources);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load sources');
    } finally {
      setLoading(false);
    }
  }, []);

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
    async (files: File[]) => {
      if (!files.length || !parsed) return;
      setBusy(true);
      setError(null);
      setMessage(null);
      try {
        const res = await uploadSources(parsed.domainId, parsed.chapterId, files);
        setMessage(`Added ${res.uploaded.length} source${res.uploaded.length === 1 ? '' : 's'}.`);
        await load(knowledgeSource);
        onSourcesChanged();
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Upload failed');
      } finally {
        setBusy(false);
      }
    },
    [parsed, knowledgeSource, load, onSourcesChanged],
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
    if (busy) return;
    fileInputRef.current?.click();
  };

  const handleAddUrl = async () => {
    if (!url.trim()) return;
    setBusy(true);
    setUrlError(null);
    setError(null);
    setMessage(null);
    try {
      const entry = await addUrlSource(url.trim(), knowledgeSource);
      if (entry.normalize_status === 'failed') {
        setUrlError(entry.normalize_error ?? 'The URL could not be converted.');
        await load(knowledgeSource);
        onSourcesChanged();
        return;
      }
      setMessage('URL added.');
      await load(knowledgeSource);
      onSourcesChanged();
      closeUrlModal();
    } catch (err) {
      setUrlError(err instanceof Error ? err.message : 'Could not add URL');
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async (sourceId: string) => {
    setBusy(true);
    setError(null);
    try {
      const res = await deleteSource(sourceId, knowledgeSource);
      setSources(res.sources);
      onSourcesChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Delete failed');
    } finally {
      setBusy(false);
    }
  };

  const compiling = compileStage === 'normalizing' || compileStage === 'compiling' || compileStage === 'validating';
  const usableSources = sources.filter((s) => s.normalize_status === 'ok' || s.normalize_status === 'legacy');
  const canCompile = usableSources.length > 0 && !compiling && !busy;

  const handleCompileClick = async () => {
    setBusy(true);
    setError(null);
    try {
      await onCompile();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Compile failed to start');
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="wb-panel" aria-label="Sources">
      <div className="wb-panel__head">
        <div>
          <h2 className="wb-panel__title">Sources</h2>
          <p className="wb-panel__sub">
            Upload documents or add a YouTube link. Each source is converted to markdown for the
            compiler.
          </p>
        </div>
        <button
          type="button"
          className="btn btn--primary"
          disabled={!canCompile}
          title={usableSources.length === 0 ? 'Add at least one source that converts successfully' : undefined}
          onClick={handleCompileClick}
        >
          {compiling ? 'Compiling…' : 'Compile wiki'}
        </button>
      </div>

      <div
        className={`wb-dropzone${dragOver ? ' wb-dropzone--over' : ''}${busy ? ' wb-dropzone--busy' : ''}`}
        role="button"
        tabIndex={0}
        aria-label="Upload sources: drop files here or click to browse"
        aria-disabled={busy}
        onClick={openFilePicker}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            openFilePicker();
          }
        }}
        onDragOver={(e) => {
          e.preventDefault();
          if (!busy) setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          if (!busy) handleFiles(Array.from(e.dataTransfer.files));
        }}
      >
        <p className="wb-dropzone__text">Drop files here, or click to upload</p>
        <p className="wb-dropzone__hint">PDF, DOCX, PPTX, HTML, Markdown, CSV, and more.</p>
        <div className="wb-dropzone__actions">
          <button
            type="button"
            className="btn btn--secondary"
            disabled={busy}
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
            disabled={busy}
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
          onChange={(e) => {
            handleFiles(Array.from(e.target.files ?? []));
            e.target.value = '';
          }}
        />
      </div>

      <ul className="wb-source-list">
        {loading && <li className="wb-source-list__empty">Loading sources…</li>}
        {!loading && sources.length === 0 && (
          <li className="wb-source-list__empty">No sources yet.</li>
        )}
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
              disabled={busy}
              onClick={() => handleDelete(s.id)}
              aria-label={`Remove ${s.display_name ?? s.id}`}
            >
              Remove
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
            if (e.target === e.currentTarget && !busy) closeUrlModal();
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
              disabled={busy}
              onChange={(e) => {
                setUrl(e.target.value);
                if (urlError) setUrlError(null);
              }}
              aria-label="YouTube URL"
            />
            {urlError && <p className="wb-modal__error">{urlError}</p>}
            <div className="wb-modal__actions">
              <button
                type="button"
                className="btn btn--ghost"
                disabled={busy}
                onClick={closeUrlModal}
              >
                Cancel
              </button>
              <button type="submit" className="btn btn--primary" disabled={busy || !url.trim()}>
                {busy ? 'Adding…' : 'Add link'}
              </button>
            </div>
          </form>
        </div>
      )}
    </section>
  );
}
