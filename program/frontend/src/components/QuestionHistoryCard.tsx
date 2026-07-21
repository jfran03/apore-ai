import { useState } from 'react';
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion';
import { DURATION, transition } from '../motion';

export interface HistoryRecord {
  question_number: number;
  question_text: string;
  explicit_rating: string;
  correct: string;
  reward?: number;
}

interface QuestionHistoryCardProps {
  records: HistoryRecord[];
}

const RATING_CLASS: Record<string, string> = {
  easy: 'history-row__rating--easy',
  ok: 'history-row__rating--ok',
  hard: 'history-row__rating--hard',
};

export function QuestionHistoryCard({ records }: QuestionHistoryCardProps) {
  const [expanded, setExpanded] = useState<number | null>(null);
  const reduceMotion = useReducedMotion();

  return (
    <div className="card-island question-history" role="log" aria-label="Question history">
      <h2 className="card-island__heading">Question History</h2>

      {records.length === 0 ? (
        <p className="question-history__empty">Completed questions appear here</p>
      ) : (
        <ul className="question-history__list">
          <AnimatePresence initial={false}>
            {records.map((record) => {
              const isOpen = expanded === record.question_number;
              const ratingKey = record.explicit_rating.toLowerCase();
              return (
                <motion.li
                  key={record.question_number}
                  className="history-row"
                  initial={reduceMotion ? false : { opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={transition(DURATION.enter, reduceMotion)}
                >
                  <button
                    type="button"
                    className="history-row__summary"
                    onClick={() =>
                      setExpanded(isOpen ? null : record.question_number)
                    }
                    aria-expanded={isOpen}
                  >
                    <span className="history-row__q">Q{record.question_number}</span>
                    <span
                      className={`history-row__rating ${RATING_CLASS[ratingKey] ?? ''}`}
                    >
                      {record.explicit_rating}
                    </span>
                    <span
                      className={`history-row__mark ${record.correct === 'yes' ? 'history-row__mark--yes' : 'history-row__mark--no'}`}
                      aria-label={record.correct === 'yes' ? 'Correct' : 'Incorrect'}
                    >
                      {record.correct === 'yes' ? '✓' : '✗'}
                    </span>
                  </button>
                  <AnimatePresence>
                    {isOpen && (
                      <motion.div
                        className="history-row__detail"
                        initial={reduceMotion ? false : { height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={reduceMotion ? undefined : { height: 0, opacity: 0 }}
                        transition={transition(DURATION.exit, reduceMotion)}
                      >
                        <p className="history-row__question">{record.question_text}</p>
                        {record.reward != null && (
                          <p className="history-row__reward">
                            R = {record.reward >= 0 ? '+' : ''}
                            {record.reward.toFixed(2)}
                          </p>
                        )}
                      </motion.div>
                    )}
                  </AnimatePresence>
                </motion.li>
              );
            })}
          </AnimatePresence>
        </ul>
      )}
    </div>
  );
}
