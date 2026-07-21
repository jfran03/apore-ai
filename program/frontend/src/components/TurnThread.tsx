import { motion, AnimatePresence } from 'framer-motion';
import { DURATION, EASE_OUT } from '../motion';

export interface TurnRecord {
  question_number: number;
  question_text: string;
  learner_response: string;
  explicit_rating: string;
  correct: string;
  reward: number;
  new_difficulty: number;
  inconsistency_flag: boolean;
}

interface TurnThreadProps {
  turns: TurnRecord[];
}

const RATING_CLASS: Record<string, string> = {
  easy: 'turn-item__rating--easy',
  ok: 'turn-item__rating--ok',
  hard: 'turn-item__rating--hard',
};

export function TurnThread({ turns }: TurnThreadProps) {
  if (turns.length === 0) {
    return (
      <div className="turn-thread turn-thread--empty">
        <span className="turn-thread__empty-text">Session turns will appear here</span>
      </div>
    );
  }

  return (
    <div className="turn-thread" role="log" aria-label="Session turn history" aria-live="polite">
      <AnimatePresence initial={false}>
        {turns.map((turn) => (
          <motion.div
            key={turn.question_number}
            className="turn-item"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: DURATION.soft, ease: EASE_OUT }}
          >
            <div className="turn-item__header">
              <span className="turn-item__q-label">Q{turn.question_number}</span>
              <div className="turn-item__signals">
                <span className={`turn-item__rating ${RATING_CLASS[turn.explicit_rating.toLowerCase()] ?? ''}`}>
                  {turn.explicit_rating}
                </span>
                <span className={`turn-item__correct ${turn.correct === 'yes' ? 'turn-item__correct--yes' : 'turn-item__correct--no'}`}>
                  {turn.correct === 'yes' ? '✓' : '✗'}
                </span>
              </div>
            </div>
            <p className="turn-item__question">{turn.question_text}</p>
            <p className="turn-item__response">{turn.learner_response}</p>
            <p className="turn-item__reward">
              R = {turn.reward >= 0 ? '+' : ''}{turn.reward.toFixed(2)} → {turn.new_difficulty.toFixed(2)}
            </p>
            {turn.inconsistency_flag && (
              <p className="turn-item__mismatch">Signal mismatch detected</p>
            )}
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
