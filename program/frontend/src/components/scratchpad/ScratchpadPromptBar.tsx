import { useEffect, useRef } from 'react';

export interface PromptBarPosition {
  left: number;
  top: number;
}

interface ScratchpadPromptBarProps {
  open: boolean;
  busy: boolean;
  selectionCount: number;
  prompt: string;
  position: PromptBarPosition;
  onPromptChange: (value: string) => void;
  onAsk: () => void;
  onSubmit: () => void;
  onClose: () => void;
}

export function ScratchpadPromptBar({
  open,
  busy,
  selectionCount,
  prompt,
  position,
  onPromptChange,
  onAsk,
  onSubmit,
  onClose,
}: ScratchpadPromptBarProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const id = window.requestAnimationFrame(() => inputRef.current?.focus());
    return () => window.cancelAnimationFrame(id);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
      }
    }
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [open, onClose]);

  if (!open) return null;

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
      <button
        type="button"
        className="scratchpad-prompt-bar__submit"
        disabled={busy}
        onClick={onSubmit}
      >
        Submit answer
      </button>
    </div>
  );
}
