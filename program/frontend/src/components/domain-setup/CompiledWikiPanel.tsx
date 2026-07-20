import { useCallback, useEffect, useState } from 'react';
import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core';
import {
  SortableContext,
  arrayMove,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { getWikiPreview, setConceptOrder } from '../../api/client';
import type { ChapterArtifactStatus, WikiPageView, WikiPreview } from '../../api/types';
import { Markdown } from '../Markdown';

interface CompiledWikiPanelProps {
  knowledgeSource: string;
  artifact: ChapterArtifactStatus | null;
  onApprove: () => Promise<void>;
  onRetryCompile: () => Promise<void>;
}

const ACTIVE_STAGES = ['normalizing', 'compiling', 'validating'] as const;

function stageLabel(stage: string): string {
  switch (stage) {
    case 'normalizing':
      return 'Reading sources…';
    case 'compiling':
      return 'Synthesizing wiki with the model…';
    case 'validating':
      return 'Validating citations and graph…';
    default:
      return 'Working…';
  }
}

/**
 * Reorder the page list by moving `activeId` to `overId`'s position. Returns the
 * same array reference when the move is a no-op so callers can skip persistence.
 */
export function computeReorder(
  pages: WikiPageView[],
  activeId: string,
  overId: string,
): WikiPageView[] {
  if (activeId === overId) return pages;
  const oldIndex = pages.findIndex((p) => p.concept_id === activeId);
  const newIndex = pages.findIndex((p) => p.concept_id === overId);
  if (oldIndex === -1 || newIndex === -1) return pages;
  return arrayMove(pages, oldIndex, newIndex);
}

interface WikiPageRowProps {
  page: WikiPageView;
  open: boolean;
  reorderable: boolean;
  onToggle: () => void;
}

function WikiPageRow({ page, open, reorderable, onToggle }: WikiPageRowProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: page.concept_id,
    disabled: !reorderable,
  });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  return (
    <li
      ref={setNodeRef}
      style={style}
      className={`wb-wiki__page${isDragging ? ' wb-wiki__page--dragging' : ''}`}
    >
      <div className="wb-wiki__row">
        {reorderable && (
          <button
            type="button"
            className="wb-wiki__handle"
            aria-label={`Reorder ${page.label}`}
            {...attributes}
            {...listeners}
          >
            <span aria-hidden="true">⠿</span>
          </button>
        )}
        <button
          type="button"
          className="wb-wiki__toggle"
          aria-expanded={open}
          onClick={onToggle}
        >
          <span className="wb-wiki__page-label">{page.label}</span>
          <span className="wb-wiki__page-depth">depth {page.depth}</span>
          <span className="wb-wiki__chevron" aria-hidden="true">
            {open ? '▾' : '▸'}
          </span>
        </button>
      </div>
      {open && (
        <div className="wb-wiki__body">
          <Markdown>{page.body}</Markdown>
        </div>
      )}
    </li>
  );
}

export function CompiledWikiPanel({
  knowledgeSource,
  artifact,
  onApprove,
  onRetryCompile,
}: CompiledWikiPanelProps) {
  const [preview, setPreview] = useState<WikiPreview | null>(null);
  const [pages, setPages] = useState<WikiPageView[]>([]);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [reorderError, setReorderError] = useState<string | null>(null);
  const [savingOrder, setSavingOrder] = useState(false);

  const compile = artifact?.compile;
  const stage = compile?.stage ?? 'idle';
  const active = (ACTIVE_STAGES as readonly string[]).includes(stage);
  const hasStaged = stage === 'ready' && (artifact?.has_unapproved_compile ?? false);
  const previewSource: 'staging' | 'published' = hasStaged ? 'staging' : 'published';

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const loadPreview = useCallback(async () => {
    if (!artifact) return;
    if (!hasStaged && !artifact.is_approved) {
      setPreview(null);
      setPages([]);
      return;
    }
    setPreviewError(null);
    try {
      const data = await getWikiPreview(previewSource, knowledgeSource);
      setPreview(data);
      setPages(data.pages);
    } catch (err) {
      setPreview(null);
      setPages([]);
      setPreviewError(err instanceof Error ? err.message : 'Failed to load wiki');
    }
  }, [artifact, hasStaged, previewSource, knowledgeSource]);

  useEffect(() => {
    loadPreview();
  }, [loadPreview, stage, artifact?.approved?.version]);

  const handleApprove = async () => {
    setBusy(true);
    setActionError(null);
    try {
      await onApprove();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Approve failed');
    } finally {
      setBusy(false);
    }
  };

  const handleRetry = async () => {
    setBusy(true);
    setActionError(null);
    try {
      await onRetryCompile();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Could not restart compile');
    } finally {
      setBusy(false);
    }
  };

  const handleDragEnd = async (event: DragEndEvent) => {
    const { active: dragged, over } = event;
    if (!over) return;

    const previous = pages;
    const reordered = computeReorder(previous, String(dragged.id), String(over.id));
    if (reordered === previous) return;

    setPages(reordered);
    setReorderError(null);
    setSavingOrder(true);
    try {
      const updated = await setConceptOrder(
        reordered.map((p) => p.concept_id),
        previewSource,
        knowledgeSource,
      );
      setPreview(updated);
      setPages(updated.pages);
    } catch (err) {
      setPages(previous);
      setReorderError(err instanceof Error ? err.message : 'Could not save order');
    } finally {
      setSavingOrder(false);
    }
  };

  const reorderable = pages.length > 1 && !savingOrder;

  return (
    <section className="wb-panel" aria-label="Compiled wiki">
      <div className="wb-panel__head">
        <div>
          <h2 className="wb-panel__title">Compiled wiki</h2>
          <p className="wb-panel__sub">
            Review the model's concept pages and prerequisite graph, then approve to publish for
            Study and question generation.
          </p>
        </div>
        {hasStaged && (
          <button type="button" className="btn btn--primary" disabled={busy} onClick={handleApprove}>
            {busy ? 'Approving…' : 'Approve version'}
          </button>
        )}
      </div>

      {active && (
        <div className="wb-progress" role="status" aria-live="polite">
          <span className="wb-progress__label">{stageLabel(stage)}</span>
          <span className="wb-progress__dots" aria-hidden="true">
            <span />
            <span />
            <span />
          </span>
        </div>
      )}

      {(stage === 'failed' || stage === 'interrupted') && (
        <div className="wb-banner wb-banner--error" role="alert">
          <span>
            {stage === 'interrupted'
              ? 'Compilation was interrupted.'
              : compile?.error_message ?? 'Compilation failed.'}
          </span>
          <button type="button" className="btn btn--secondary" disabled={busy} onClick={handleRetry}>
            Retry compile
          </button>
        </div>
      )}

      {hasStaged && (
        <div className="wb-banner wb-banner--review" role="status">
          A new version is ready to review. Approve it to publish, or recompile from Sources.
        </div>
      )}

      {!active && artifact?.is_approved && !hasStaged && artifact.is_stale && (
        <div className="wb-banner" role="status">
          Sources changed since the approved version. Recompile from Sources to refresh.
        </div>
      )}

      {!active && !artifact?.is_approved && !hasStaged && stage !== 'failed' && (
        <div className="wb-empty">
          <p>No compiled wiki yet. Add sources and compile to generate concept pages.</p>
        </div>
      )}

      {previewError && <p className="wb-status wb-status--error">{previewError}</p>}
      {actionError && <p className="wb-status wb-status--error">{actionError}</p>}
      {reorderError && <p className="wb-status wb-status--error">{reorderError}</p>}

      {preview && pages.length > 0 && (
        <div className="wb-wiki">
          <p className="wb-wiki__meta">
            {preview.source === 'staging' ? 'Draft' : 'Published'} · {pages.length} concept
            {pages.length === 1 ? '' : 's'} · {preview.edges.length} prerequisite edge
            {preview.edges.length === 1 ? '' : 's'} · drag to set learning hierarchy
          </p>
          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            onDragEnd={handleDragEnd}
          >
            <SortableContext
              items={pages.map((p) => p.concept_id)}
              strategy={verticalListSortingStrategy}
            >
              <ul className="wb-wiki__list">
                {pages.map((page) => (
                  <WikiPageRow
                    key={page.concept_id}
                    page={page}
                    open={expanded[page.concept_id] ?? false}
                    reorderable={reorderable}
                    onToggle={() =>
                      setExpanded((prev) => ({
                        ...prev,
                        [page.concept_id]: !(prev[page.concept_id] ?? false),
                      }))
                    }
                  />
                ))}
              </ul>
            </SortableContext>
          </DndContext>
        </div>
      )}
    </section>
  );
}
