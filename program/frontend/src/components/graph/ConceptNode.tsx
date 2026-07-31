import { useEffect, type WheelEvent, type TouchEvent } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { Markdown } from '../Markdown';
import { BAND_COLOR_VAR, BAND_LABEL, masteryText } from './bands';
import type { ConceptFlowNode } from './layout';
import { useConceptWiki } from './useConceptWiki';

function stopCanvasScroll(e: WheelEvent | TouchEvent) {
  e.stopPropagation();
}

export function ConceptNode({ data, selected }: NodeProps<ConceptFlowNode>) {
  const bandColor = BAND_COLOR_VAR[data.band];
  const wiki = useConceptWiki(
    data.conceptId,
    data.knowledgeSource,
    data.hasWiki,
    Boolean(selected),
  );

  useEffect(() => {
    if (!selected) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') data.onClose?.();
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [selected, data]);

  if (selected) {
    return (
      <div
        className={`graph-node graph-node--concept graph-node--expanded graph-node--band-${data.band} graph-node--selected`}
      >
        <Handle type="target" position={Position.Left} isConnectable={false} />
        <header className="graph-node__expand-header">
          <div className="graph-node__expand-heading">
            <span className="graph-node__expand-chapter">{data.chapterId}</span>
            <span className="graph-node__expand-title">{data.label}</span>
          </div>
          <button
            type="button"
            className="graph-node__expand-close"
            aria-label="Close concept detail"
            onClick={(e) => {
              e.stopPropagation();
              data.onClose?.();
            }}
          >
            <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
              <path
                d="M4 4l8 8M12 4l-8 8"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
              />
            </svg>
          </button>
        </header>

        <dl className="graph-node__expand-mastery">
          <div>
            <dt>Mastery</dt>
            <dd className="graph-node__pct" style={{ color: bandColor }}>
              {masteryText(data.displayPct)}
            </dd>
          </div>
          <div>
            <dt>Band</dt>
            <dd style={{ color: bandColor }}>{BAND_LABEL[data.band]}</dd>
          </div>
          <div>
            <dt>Obs</dt>
            <dd>{data.nObserved}</dd>
          </div>
        </dl>

        <div
          className="graph-node__expand-body nowheel nodrag"
          onWheel={stopCanvasScroll}
          onTouchMove={stopCanvasScroll}
          onPointerDown={(e) => e.stopPropagation()}
        >
          {wiki.status === 'loading' && (
            <div className="graph-node__expand-skeleton" aria-hidden="true">
              <span className="graph-node__expand-bone" style={{ width: '80%' }} />
              <span className="graph-node__expand-bone" style={{ width: '95%' }} />
              <span className="graph-node__expand-bone" style={{ width: '70%' }} />
            </div>
          )}
          {wiki.status === 'ready' && (
            <Markdown className="graph-node__expand-wiki">{wiki.body}</Markdown>
          )}
          {wiki.status === 'missing' && (
            <p className="graph-node__expand-empty">
              No compiled wiki for this concept yet. Compile the chapter in Setup to
              generate its page.
            </p>
          )}
          {wiki.status === 'error' && (
            <p className="graph-node__expand-empty graph-node__expand-empty--error">
              {wiki.message}
            </p>
          )}
        </div>
        <Handle type="source" position={Position.Right} isConnectable={false} />
      </div>
    );
  }

  return (
    <div
      className={`graph-node graph-node--concept graph-node--band-${data.band}`}
    >
      <Handle type="target" position={Position.Left} isConnectable={false} />
      <span
        className="graph-node__dot"
        style={{ backgroundColor: bandColor }}
        aria-hidden="true"
      />
      <span className="graph-node__concept-label" title={data.label}>
        {data.label}
      </span>
      <span
        className="graph-node__pct"
        style={{ color: bandColor }}
        title={`${BAND_LABEL[data.band]} · ${data.nObserved} observation${
          data.nObserved === 1 ? '' : 's'
        }`}
      >
        {masteryText(data.displayPct)}
      </span>
      <Handle type="source" position={Position.Right} isConnectable={false} />
    </div>
  );
}
