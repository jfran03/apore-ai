import { useCallback, useEffect, useRef, useState, type CSSProperties } from 'react';
import type { ConceptMasteryDelta, MasteryBand } from '../api/types';

export interface MasteryDeltaItem {
  concept_id: string;
  label: string;
  delta: ConceptMasteryDelta;
}

interface MasteryDeltaListProps {
  items: MasteryDeltaItem[];
  /** Recap mode: heading + auto-collapse countdown. Live: bare rows. */
  variant?: 'live' | 'recap';
  /** Auto-collapse after this many ms (recap only). Default 5000. */
  collapseAfterMs?: number;
}

const BAND_LABEL: Record<MasteryBand, string> = {
  new: 'New',
  struggling: 'struggling',
  learning: 'learning',
  proficient: 'proficient',
};

function formatPct(pct: number | null): string {
  return pct == null ? 'New' : `${pct}%`;
}

function bandClass(band: MasteryBand): string {
  return `mastery-delta__band mastery-delta__band--${band}`;
}

function compactSummary(items: MasteryDeltaItem[]): string {
  const n = items.length;
  const nowProficient = items.filter(
    (i) => i.delta.band_after === 'proficient' && i.delta.band_before !== 'proficient',
  ).length;
  const concepts = n === 1 ? '1 concept moved' : `${n} concepts moved`;
  if (nowProficient === 0) return concepts;
  const prof =
    nowProficient === 1 ? '1 now proficient' : `${nowProficient} now proficient`;
  return `${concepts} · ${prof}`;
}

function MasteryDeltaRow({ item, index }: { item: MasteryDeltaItem; index: number }) {
  const { delta, label } = item;
  const sameBand = delta.band_before === delta.band_after;

  return (
    <li
      className="mastery-delta__row"
      style={{ '--mastery-delta-i': index } as CSSProperties}
    >
      <span className="mastery-delta__label" title={item.concept_id}>
        {label}
      </span>
      <span className="mastery-delta__bands">
        {sameBand ? (
          <span className={bandClass(delta.band_after)}>
            {BAND_LABEL[delta.band_after]}
          </span>
        ) : (
          <>
            <span className="mastery-delta__band mastery-delta__band--origin">
              {BAND_LABEL[delta.band_before]}
            </span>
            <span className="mastery-delta__arrow" aria-hidden="true">
              →
            </span>
            <span className={bandClass(delta.band_after)}>
              {BAND_LABEL[delta.band_after]}
            </span>
          </>
        )}
      </span>
      <span className="mastery-delta__pcts">
        <span className="mastery-delta__pct">{formatPct(delta.pct_before)}</span>
        <span className="mastery-delta__arrow" aria-hidden="true">
          →
        </span>
        <span className="mastery-delta__pct">{formatPct(delta.pct_after)}</span>
      </span>
    </li>
  );
}

export function MasteryDeltaList({
  items,
  variant = 'live',
  collapseAfterMs = 5000,
}: MasteryDeltaListProps) {
  const isRecap = variant === 'recap';
  const [collapsed, setCollapsed] = useState(false);
  const [paused, setPaused] = useState(false);
  const [remainingMs, setRemainingMs] = useState(collapseAfterMs);
  const remainingRef = useRef(collapseAfterMs);

  const collapse = useCallback(() => {
    setCollapsed(true);
  }, []);

  useEffect(() => {
    if (!isRecap || collapsed || items.length === 0) return;

    const interval = window.setInterval(() => {
      if (document.visibilityState === 'hidden' || paused) return;
      remainingRef.current = Math.max(0, remainingRef.current - 100);
      setRemainingMs(remainingRef.current);
      if (remainingRef.current <= 0) {
        collapse();
      }
    }, 100);

    return () => window.clearInterval(interval);
  }, [isRecap, collapsed, items.length, paused, collapse]);

  if (items.length === 0) {
    if (!isRecap) return null;
    return (
      <section className="mastery-delta mastery-delta--recap" aria-label="Concepts practiced">
        <h2 className="mastery-delta__heading">Concepts practiced</h2>
        <p className="mastery-delta__empty">No concepts practiced this session.</p>
      </section>
    );
  }

  const fillPct = Math.max(0, Math.min(100, (remainingMs / collapseAfterMs) * 100));

  return (
    <section
      className={`mastery-delta mastery-delta--${variant}${collapsed ? ' mastery-delta--collapsed' : ''}`}
      aria-label={isRecap ? 'Concepts practiced' : 'Concept mastery movement'}
      onPointerEnter={isRecap && !collapsed ? () => setPaused(true) : undefined}
      onPointerLeave={isRecap && !collapsed ? () => setPaused(false) : undefined}
      onFocusCapture={isRecap && !collapsed ? () => setPaused(true) : undefined}
      onBlurCapture={
        isRecap && !collapsed
          ? (e) => {
              if (!e.currentTarget.contains(e.relatedTarget as Node | null)) {
                setPaused(false);
              }
            }
          : undefined
      }
    >
      {isRecap && <h2 className="mastery-delta__heading">Concepts practiced</h2>}

      {!collapsed ? (
        <div className="mastery-delta__expanded">
          <ul className="mastery-delta__list">
            {items.map((item, index) => (
              <MasteryDeltaRow key={item.concept_id} item={item} index={index} />
            ))}
          </ul>

          {isRecap && (
            <div className="mastery-delta__countdown">
              <div className="mastery-delta__countdown-track" aria-hidden="true">
                <div
                  className="mastery-delta__countdown-fill"
                  style={{ width: `${fillPct}%` }}
                />
              </div>
              <button
                type="button"
                className="mastery-delta__close"
                onClick={collapse}
              >
                Close summary
              </button>
            </div>
          )}
        </div>
      ) : (
        <p className="mastery-delta__compact">{compactSummary(items)}</p>
      )}
    </section>
  );
}
