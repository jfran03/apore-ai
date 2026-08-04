import { useEffect, useRef } from 'react';

export interface PromptBarPosition {
  left: number;
  top: number;
}

export type PromptBarMode = 'ask' | 'submit' | 'submitting' | 'submit-error';

interface ScratchpadPromptBarProps {
  open: boolean;
  mode: PromptBarMode;
  busy: boolean;
  selectionCount: number;
  prompt: string;
  previewDataUri: string | null;
  errorMessage: string | null;
  position: PromptBarPosition;
  onPromptChange: (value: string) => void;
  onAsk: () => void;
  onConfirmSubmit: () => void;
  onRetrySubmit: () => void;
  onClose: () => void;
}

export function ScratchpadPromptBar({
  open,
  mode,
  busy,
  selectionCount,
  prompt,
  previewDataUri,
  errorMessage,
  position,
  onPromptChange,
  onAsk,
  onConfirmSubmit,
  onRetrySubmit,
  onClose,
}: ScratchpadPromptBarProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const confirmRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const id = window.requestAnimationFrame(() => {
      if (mode === 'ask') inputRef.current?.focus();
      else if (mode === 'submit' || mode === 'submit-error') confirmRef.current?.focus();
    });
    return () => window.cancelAnimationFrame(id);
  }, [open, mode]);

  useEffect(() => {
    if (!open) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape' && mode !== 'submitting') {
        e.preventDefault();
        onClose();
      }
    }
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [open, mode, onClose]);

  if (!open) return null;

  if (mode === 'ask') {
    return (
      <div
        className="scratchpad-prompt-bar"
        style={{ left: position.left, top: position.top }}
        role="dialog"
        aria-label="Ask about selection"
      >
        <button
          type="button"
          className="scratchpad-prompt-bar__chip"
          onClick={onClose}
          disabled={busy}
          aria-label="Clear selection prompt"
        >
          {selectionCount} selected
          <span aria-hidden="true">×</span>
        </button>
        <input
          ref={inputRef}
          id="scratchpad-prompt-input"
          className="scratchpad-prompt-bar__input"
          type="text"
          value={prompt}
          onChange={(e) => onPromptChange(e.target.value)}
          placeholder="Ask Apore about this…"
          disabled={busy}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              onAsk();
            }
          }}
        />
        <button
          type="button"
          className="scratchpad-prompt-bar__send"
          disabled={busy}
          onClick={onAsk}
          aria-label="Ask Apore"
        >
          ↑
        </button>
      </div>
    );
  }

  const isSubmitting = mode === 'submitting';
  const isError = mode === 'submit-error';
  const title = isSubmitting
    ? 'Grading selected answer'
    : isError
      ? 'Submit failed'
      : 'Submit selected answer';

  return (
    <div
      className="scratchpad-submit-confirm"
      style={{ left: position.left, top: position.top }}
      role="dialog"
      aria-label={title}
      aria-busy={isSubmitting}
    >
      <div className="scratchpad-submit-confirm__header">
        <p className="scratchpad-submit-confirm__title">{title}</p>
        <p className="scratchpad-submit-confirm__meta">
          {selectionCount} selected · Only this selected region will be graded
        </p>
      </div>
      {previewDataUri && (
        <div className="scratchpad-submit-confirm__preview">
          <img src={previewDataUri} alt="Selected answer region" />
        </div>
      )}
      {isError && errorMessage && (
        <p className="scratchpad-submit-confirm__error" role="alert">
          {errorMessage}
        </p>
      )}
      {isSubmitting && (
        <p className="scratchpad-submit-confirm__status" role="status">
          Saving canvas and grading…
        </p>
      )}
      <div className="scratchpad-submit-confirm__actions">
        {!isSubmitting && (
          <button
            type="button"
            className="btn btn--ghost"
            onClick={onClose}
            disabled={busy && !isError}
          >
            Cancel
          </button>
        )}
        {isError ? (
          <button
            ref={confirmRef}
            type="button"
            className="btn btn--primary"
            onClick={onRetrySubmit}
          >
            Retry submit
          </button>
        ) : (
          <button
            ref={confirmRef}
            type="button"
            className="btn btn--primary"
            disabled={isSubmitting || busy}
            onClick={onConfirmSubmit}
          >
            {isSubmitting ? 'Submitting…' : 'Submit selected answer'}
          </button>
        )}
      </div>
    </div>
  );
}
