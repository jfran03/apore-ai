import { useState } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import type { SessionHistoryQuestion } from '../api/types';
import { DURATION, transition } from '../motion';

interface SessionHistoryProps {
  questions: SessionHistoryQuestion[];
}

const RATING_CLASS: Record<string, string> = {
  easy: 'session-history__rating--easy',
  ok: 'session-history__rating--ok',
  hard: 'session-history__rating--hard',
};

function statusLabel(question: SessionHistoryQuestion): string {
  if (question.status === 'in_progress') return 'In progress';
  if (question.status === 'awaiting_rating') return 'Rate';
  if (question.status === 'reflection') return 'Reflect';
  return '';
}

function truncate(text: string, max = 72): string {
  const cleaned = text.replace(/\s+/g, ' ').trim();
  if (cleaned.length <= max) return cleaned;
  return `${cleaned.slice(0, max - 1)}…`;
}

export function SessionHistory({ questions }: SessionHistoryProps) {
  const [expanded, setExpanded] = useState<number | null>(null);
  const reduceMotion = useReducedMotion();

  if (questions.length === 0) {
    return (
      <div className="session-history">
        <p className="session-history__empty">No questions in this session yet.</p>
      </div>
    );
  }

  return (
    <div className="session-history" role="list" aria-label="Session questions">
      <ul className="session-history__list">
        {questions.map((question) => {
          const isOpen = expanded === question.question_number;
          const rating = (question.explicit_rating || '').toLowerCase();
          const completed = question.status === 'completed';
          const openLabel = statusLabel(question);

          return (
            <li key={question.question_number} className="session-history__row" role="listitem">
              <button
                type="button"
                className="session-history__summary"
                onClick={() => setExpanded(isOpen ? null : question.question_number)}
                aria-expanded={isOpen}
              >
                <span className="session-history__q">Q{question.question_number}</span>
                <span className="session-history__concept">
                  {question.concept_label || question.concept_id || 'Concept'}
                </span>
                <span className="session-history__preview" title={question.question_text}>
                  {truncate(question.question_text || 'Question')}
                </span>
                {rating && (
                  <span className={`session-history__rating ${RATING_CLASS[rating] ?? ''}`}>
                    {question.explicit_rating}
                  </span>
                )}
                {completed && question.correct === 'yes' ? (
                  <span className="session-history__mark session-history__mark--yes" aria-label="Correct">
                    ✓
                  </span>
                ) : completed && question.correct === 'no' ? (
                  <span className="session-history__mark session-history__mark--no" aria-label="Incorrect">
                    ✗
                  </span>
                ) : completed ? (
                  <span className="session-history__open-status">Ended</span>
                ) : (
                  <span className="session-history__open-status">{openLabel}</span>
                )}
              </button>

              <AnimatePresence initial={false}>
                {isOpen && (
                  <motion.div
                    className="session-history__detail"
                    initial={reduceMotion ? false : { height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={reduceMotion ? undefined : { height: 0, opacity: 0 }}
                    transition={transition(DURATION.exit, reduceMotion)}
                  >
                    <p className="session-history__question">{question.question_text}</p>
                    {question.messages.length > 0 ? (
                      <div className="session-history__dialogue">
                        {question.messages.map((message, index) => {
                          const label =
                            message.role === 'assistant'
                              ? 'Tutor'
                              : message.role === 'user'
                                ? 'Learner'
                                : message.role;
                          return (
                            <p
                              key={`${question.question_number}-${index}`}
                              className={`session-history__turn session-history__turn--${
                                message.role === 'assistant' ? 'tutor' : 'learner'
                              }`}
                            >
                              <span className="session-history__turn-label">{label}</span>
                              {message.content}
                            </p>
                          );
                        })}
                      </div>
                    ) : (
                      <p className="session-history__dialogue-empty">No dialogue recorded.</p>
                    )}
                  </motion.div>
                )}
              </AnimatePresence>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
