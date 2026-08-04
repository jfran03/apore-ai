import { useEffect, useRef, useState } from 'react';
import { Markdown } from '../Markdown';
import type { PromptBarPosition } from './ScratchpadPromptBar';

export type AnnotationPanelMode = 'loading' | 'error' | 'response' | 'marker';

export type AnnotationVerdict = 'correct' | 'incorrect';

interface ScratchpadAnnotationPanelProps {
  mode: AnnotationPanelMode;
  position: PromptBarPosition;
  prompt?: string;
  response?: string;
  error?: string | null;
  busy?: boolean;
  /** Ask replies (default) vs grade results. */
  kind?: 'ask' | 'grade';
  /** When set on grade response/marker mode, shows Correct/Incorrect chrome. */
  verdict?: AnnotationVerdict | null;
  verdictAssisted?: boolean;
  onExpand?: () => void;
  onCollapse?: () => void;
  onDismiss?: () => void;
  onRetry?: () => void;
}

export function ScratchpadAnnotationPanel({
  mode,
  position,
  prompt,
  response,
  error,
  busy = false,
  kind = 'ask',
  verdict = null,
  verdictAssisted = false,
  onExpand,
  onCollapse,
  onDismiss,
  onRetry,
}: ScratchpadAnnotationPanelProps) {
  const panelRef = useRef<HTMLDivElement | null>(null);
  const [confirmDismiss, setConfirmDismiss] = useState(false);
  const isGrade = kind === 'grade';

  useEffect(() => {
    setConfirmDismiss(false);
  }, [mode]);

  useEffect(() => {
    if (mode === 'marker' || mode === 'loading') return;
    const id = window.requestAnimationFrame(() => panelRef.current?.focus());
    return () => window.cancelAnimationFrame(id);
  }, [mode]);

  useEffect(() => {
    if (mode !== 'response') return;

    function onPointerDown(e: PointerEvent) {
      const target = e.target;
      if (!(target instanceof Node)) return;
      if (panelRef.current?.contains(target)) return;
      setConfirmDismiss(false);
      onCollapse?.();
    }

    document.addEventListener('pointerdown', onPointerDown);
    return () => document.removeEventListener('pointerdown', onPointerDown);
  }, [mode, onCollapse]);

  useEffect(() => {
    if (mode === 'marker' || mode === 'loading') return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key !== 'Escape') return;
      e.preventDefault();
      if (mode === 'response') {
        setConfirmDismiss(false);
        onCollapse?.();
        return;
      }
      onDismiss?.();
    }
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [mode, onCollapse, onDismiss]);

  if (mode === 'marker') {
    return (
      <button
        type="button"
        className="scratchpad-annotation-marker"
        style={{ left: position.left, top: position.top }}
        onClick={onExpand}
        aria-label={isGrade ? 'Open grade result for selection' : 'Open Apore reply for selection'}
      >
        {isGrade
          ? verdict === 'correct'
            ? 'Correct'
            : verdict === 'incorrect'
              ? 'Incorrect'
              : 'Grade'
          : 'Apore'}
      </button>
    );
  }

  const isLoading = mode === 'loading';
  const isError = mode === 'error';
  const ariaLabel = isLoading
    ? isGrade
      ? 'Grading selected answer'
      : 'Apore is thinking'
    : isError
      ? 'Ask failed'
      : isGrade
        ? 'Grade result for selection'
        : 'Apore reply for selection';

  const verdictLabel =
    verdict === 'correct'
      ? verdictAssisted
        ? '✓ Correct (with tutor help)'
        : '✓ Correct'
      : verdict === 'incorrect'
        ? '✗ Incorrect'
        : null;

  return (
    <div
      ref={panelRef}
      className={`scratchpad-annotation-panel scratchpad-annotation-panel--${mode}${
        isGrade ? ' scratchpad-annotation-panel--grade' : ''
      }${verdict ? ` scratchpad-annotation-panel--${verdict}` : ''}`}
      style={{ left: position.left, top: position.top }}
      role={isError ? 'alertdialog' : isLoading ? 'status' : 'dialog'}
      aria-label={ariaLabel}
      aria-live={isLoading ? 'polite' : undefined}
      tabIndex={isLoading ? undefined : -1}
    >
      <div className="scratchpad-annotation-panel__header">
        <span className="scratchpad-annotation-panel__label">
          {isLoading
            ? isGrade
              ? 'Grading answer'
              : 'Apore is thinking'
            : isGrade
              ? 'Grade'
              : 'Apore'}
        </span>
        <div className="scratchpad-annotation-panel__actions">
          {isLoading && (
            <span className="scratchpad-annotation-panel__dots" aria-hidden="true">
              <span />
              <span />
              <span />
            </span>
          )}
          {mode === 'response' && confirmDismiss && (
            <>
              <span className="scratchpad-annotation-panel__confirm-prompt">
                Dismiss this reply?
              </span>
              <button
                type="button"
                className="scratchpad-annotation-panel__cancel"
                onClick={() => setConfirmDismiss(false)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="scratchpad-annotation-panel__dismiss"
                disabled={busy}
                onClick={onDismiss}
                aria-label="Confirm dismiss reply"
              >
                Dismiss
              </button>
            </>
          )}
          {mode === 'response' && !confirmDismiss && (
            <button
              type="button"
              className="scratchpad-annotation-panel__dismiss"
              disabled={busy}
              onClick={() => setConfirmDismiss(true)}
              aria-label="Dismiss reply"
            >
              Dismiss
            </button>
          )}
          {isError && (
            <button
              type="button"
              className="scratchpad-annotation-panel__dismiss"
              disabled={busy}
              onClick={onDismiss}
              aria-label="Dismiss failed ask"
            >
              Dismiss
            </button>
          )}
        </div>
      </div>

      {verdictLabel && mode === 'response' && (
        <div
          className={`signal-capture__verdict signal-capture__verdict--${
            verdict === 'correct' ? 'correct' : 'incorrect'
          } scratchpad-annotation-panel__verdict`}
          role="status"
        >
          {verdictLabel}
        </div>
      )}

      {prompt && !isGrade ? (
        <p className="scratchpad-annotation-panel__prompt">{prompt}</p>
      ) : null}

      {isLoading && (
        <p className="scratchpad-annotation-panel__thinking">
          {isGrade ? 'Reading the selected answer…' : 'Reading the selected work…'}
        </p>
      )}

      {isError && (
        <>
          <p className="scratchpad-annotation-panel__error">
            {error || 'Failed to ask about selection'}
          </p>
          <div className="scratchpad-annotation-panel__actions">
            <button
              type="button"
              className="scratchpad-annotation-panel__retry"
              disabled={busy}
              onClick={onRetry}
            >
              Retry
            </button>
          </div>
        </>
      )}

      {mode === 'response' && (
        <div className="scratchpad-annotation-panel__response" aria-live="polite">
          <Markdown className="scratchpad-annotation-panel__markdown">
            {response?.trim() || 'No reply was returned for this selection.'}
          </Markdown>
        </div>
      )}
    </div>
  );
}
