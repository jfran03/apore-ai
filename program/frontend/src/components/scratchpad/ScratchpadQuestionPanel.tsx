export const SCRATCHPAD_TOOLBAR_HEIGHT = 52;

interface ScratchpadQuestionPanelProps {
  id: string;
  open: boolean;
  questionText: string;
  conceptLabel: string;
  questionNumber: number;
  maxQuestions: number;
}

export function ScratchpadQuestionPanel({
  id,
  open,
  questionText,
  conceptLabel,
  questionNumber,
  maxQuestions,
}: ScratchpadQuestionPanelProps) {
  if (!open) return null;

  return (
    <aside
      id={id}
      className="scratchpad-question-preview"
      role="tooltip"
      aria-label="Current question"
    >
      <p className="scratchpad-question-preview__meta">
        Q{questionNumber}/{maxQuestions} · {conceptLabel}
      </p>
      <p className="scratchpad-question-preview__text">{questionText}</p>
    </aside>
  );
}
