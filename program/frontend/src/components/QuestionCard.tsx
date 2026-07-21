import { motion, AnimatePresence } from 'framer-motion';
import { DURATION, EASE_OUT } from '../motion';

interface QuestionCardProps {
  question_text: string;
  concept_label: string;
  concept_id?: string;
  question_type: string;
  intended_difficulty: number;
  question_number?: number;
}

function extractCitation(text: string): { main: string; citation: string | null } {
  const match = text.match(/\[Source:[^\]]+\]/);
  if (!match) return { main: text, citation: null };
  return {
    main: text.replace(match[0], '').trim(),
    citation: match[0],
  };
}

export function QuestionCard({
  question_text,
  concept_label,
  concept_id,
  question_type,
  intended_difficulty,
  question_number = 1,
}: QuestionCardProps) {
  const { main, citation } = extractCitation(question_text);
  const progressLabel = `Question ${question_number}`;

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={question_number}
        className="question-card"
        initial={{ opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -4 }}
        transition={{ duration: DURATION.exit, ease: EASE_OUT }}
      >
        <div className="question-card__meta">
          <span className="question-card__progress">{progressLabel}</span>
          <span className="question-card__concept" title={concept_id}>
            {concept_label}
          </span>
          <span className="question-card__type">{question_type}</span>
          <span className="question-card__difficulty">{intended_difficulty.toFixed(2)}</span>
        </div>
        <p className="question-card__text">{main}</p>
        {citation && (
          <p className="question-card__citation">{citation}</p>
        )}
      </motion.div>
    </AnimatePresence>
  );
}
