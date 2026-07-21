import { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion';
import { useProgressiveReveal } from '../hooks/useProgressiveReveal';
import { DURATION, transition } from '../motion';
import { TutorGeneratingRow } from './TutorGeneratingRow';
import type { GradeResult } from './SignalCapture';

export interface DialogueMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
}

export type ChatStatus = 'idle' | 'generating' | 'revealing';

interface TutorChatCardProps {
  messages: DialogueMessage[];
  chatStatus: ChatStatus;
  pendingReveal: string | null;
  onRevealComplete: () => void;
  phase: 'dialogue' | 'rating' | 'reflection';
  graded: GradeResult | null;
  skipPrompt: boolean;
  onSendMessage: (text: string) => void | Promise<void>;
  onSkip: () => void | Promise<void>;
  onSubmitRating: (rating: 'easy' | 'ok' | 'hard') => void | Promise<void>;
  onContinueToNext: () => void | Promise<void>;
  disabled: boolean;
}

type Rating = 'easy' | 'ok' | 'hard';

function extractCitation(text: string): { main: string; citation: string | null } {
  const match = text.match(/\[Source:[^\]]+\]/);
  if (!match) return { main: text, citation: null };
  return {
    main: text.replace(match[0], '').trim(),
    citation: match[0],
  };
}

function SendIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path
        d="M8 3.5v9M8 3.5L4.5 7M8 3.5L11.5 7"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function TutorMessage({ content, reduceMotion }: { content: string; reduceMotion: boolean }) {
  const { main, citation } = extractCitation(content);
  return (
    <motion.div
      className="tutor-chat__tutor"
      initial={reduceMotion ? false : { opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={transition(DURATION.soft, reduceMotion)}
    >
      <p className="tutor-chat__tutor-text">{main}</p>
      {citation && <p className="tutor-chat__citation">{citation}</p>}
    </motion.div>
  );
}

export function TutorChatCard({
  messages,
  chatStatus,
  pendingReveal,
  onRevealComplete,
  phase,
  graded,
  skipPrompt,
  onSendMessage,
  onSkip,
  onSubmitRating,
  onContinueToNext,
  disabled,
}: TutorChatCardProps) {
  const [draft, setDraft] = useState('');
  const [rating, setRating] = useState<Rating | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const revealCompleteRef = useRef(onRevealComplete);
  revealCompleteRef.current = onRevealComplete;
  const reduceMotion = useReducedMotion();

  const { displayText, isComplete } = useProgressiveReveal(
    pendingReveal ?? '',
    chatStatus === 'revealing' && Boolean(pendingReveal),
    {
      wordDelayMs: 40,
      onComplete: () => revealCompleteRef.current(),
    },
  );

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [messages, chatStatus, displayText]);

  const inputLocked = disabled || chatStatus !== 'idle' || phase === 'rating';
  const canSend =
    !inputLocked && draft.trim().length > 0 && (phase === 'dialogue' || phase === 'reflection');
  const canSkip =
    !disabled && chatStatus === 'idle' && phase === 'dialogue' && !skipPrompt;
  const canSubmitRating = !disabled && phase === 'rating' && rating !== null;
  const canContinue =
    !disabled && phase === 'reflection' && chatStatus === 'idle';
  const verdictCorrect = graded?.correct === 'yes';

  async function handleSend() {
    if (!canSend) return;
    const text = draft.trim();
    setDraft('');
    await onSendMessage(text);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      void handleSend();
    }
  }

  return (
    <div className="tutor-chat">
      <div
        ref={scrollRef}
        className="tutor-chat__thread"
        role="log"
        aria-label="Tutor dialogue for current question"
        aria-live="polite"
      >
        {messages.length === 0 && chatStatus === 'idle' && phase === 'dialogue' && (
          <p className="tutor-chat__hint">
            Type your answer. Say you need help or ask for an explanation to get hints.
          </p>
        )}
        {phase === 'reflection' && chatStatus === 'idle' && (
          <p className="tutor-chat__hint">
            Ask about this question, or continue when you are ready.
          </p>
        )}

        <AnimatePresence initial={false}>
          {messages.map((msg) =>
            msg.role === 'user' ? (
              <motion.p
                key={msg.id}
                className="tutor-chat__learner"
                initial={reduceMotion ? false : { opacity: 0, x: 16, scale: 0.98 }}
                animate={{ opacity: 1, x: 0, scale: 1 }}
                transition={transition(DURATION.soft, reduceMotion)}
              >
                {msg.content}
              </motion.p>
            ) : (
              <TutorMessage
                key={msg.id}
                content={msg.content}
                reduceMotion={Boolean(reduceMotion)}
              />
            ),
          )}
        </AnimatePresence>

        <AnimatePresence>
          {chatStatus === 'generating' && (
            <motion.div
              initial={reduceMotion ? false : { opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={reduceMotion ? undefined : { opacity: 0, y: -4 }}
              transition={transition(DURATION.exit, reduceMotion)}
            >
              <TutorGeneratingRow />
            </motion.div>
          )}
        </AnimatePresence>

        {chatStatus === 'revealing' && pendingReveal && (
          <div className="tutor-chat__tutor tutor-chat__tutor--revealing">
            <p className="tutor-chat__tutor-text">
              {isComplete ? pendingReveal : displayText}
              {!isComplete && (
                <span className="tutor-chat__cursor" aria-hidden="true">
                  ▍
                </span>
              )}
            </p>
          </div>
        )}
      </div>

      {phase === 'rating' && graded && (
        <motion.div
          className="tutor-chat__rating-block"
          initial={reduceMotion ? false : { opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={transition(DURATION.soft, reduceMotion)}
        >
          <div
            className={`signal-capture__verdict signal-capture__verdict--${verdictCorrect ? 'correct' : 'incorrect'}`}
            role="status"
          >
            {verdictCorrect ? '✓ Correct' : '✗ Incorrect'}
          </div>
          <p className="signal-capture__rating-prompt">How difficult was this question?</p>
          <div className="signal-capture__controls">
            <div className="signal-capture__group" role="group" aria-label="Difficulty rating">
              {(['easy', 'ok', 'hard'] as Rating[]).map((r) => (
                <button
                  key={r}
                  type="button"
                  className={`signal-capture__btn signal-capture__btn--rating signal-capture__btn--${r}${rating === r ? ' signal-capture__btn--selected' : ''}`}
                  onClick={() => setRating(r)}
                  disabled={disabled}
                  aria-pressed={rating === r}
                >
                  {r.charAt(0).toUpperCase() + r.slice(1)}
                </button>
              ))}
            </div>
          </div>
          <div className="signal-capture__footer">
            <button
              type="button"
              className="btn btn--primary signal-capture__submit"
              disabled={!canSubmitRating}
              onClick={() => rating && void onSubmitRating(rating)}
            >
              {disabled ? 'Saving…' : 'Submit rating'}
            </button>
          </div>
        </motion.div>
      )}

      {phase === 'reflection' && (
        <motion.div
          className="tutor-chat__composer-wrap"
          layout
          transition={transition(DURATION.soft, reduceMotion)}
        >
          <div
            className={`tutor-chat__composer-island${inputLocked ? ' tutor-chat__composer-island--locked' : ''}`}
          >
            <textarea
              className="tutor-chat__island-input"
              rows={2}
              placeholder="Ask about this question…"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={inputLocked}
              aria-label="Reflection message"
            />
            <div className="tutor-chat__island-toolbar tutor-chat__island-toolbar--reflection">
              <button
                type="button"
                className="btn btn--primary tutor-chat__next-question"
                disabled={!canContinue}
                onClick={() => void onContinueToNext()}
              >
                {disabled ? 'Loading…' : 'Next question'}
              </button>
              <motion.button
                type="button"
                className={`tutor-chat__send-icon${canSend ? ' tutor-chat__send-icon--ready' : ''}`}
                disabled={!canSend}
                onClick={() => void handleSend()}
                aria-label={chatStatus === 'generating' ? 'Sending' : 'Send message'}
                whileTap={reduceMotion || !canSend ? undefined : { scale: 0.94 }}
                transition={transition(DURATION.micro, reduceMotion)}
              >
                <SendIcon />
              </motion.button>
            </div>
          </div>
        </motion.div>
      )}

      {phase === 'dialogue' && (
        <motion.div
          className="tutor-chat__composer-wrap"
          layout
          transition={transition(DURATION.soft, reduceMotion)}
        >
          <div
            className={`tutor-chat__composer-island${inputLocked ? ' tutor-chat__composer-island--locked' : ''}`}
          >
            <textarea
              className="tutor-chat__island-input"
              rows={2}
              placeholder={
                skipPrompt
                  ? 'Why do you want to skip this question?'
                  : 'Your answer…'
              }
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={inputLocked}
              aria-label={skipPrompt ? 'Skip reason' : 'Your message'}
            />
            <div className="tutor-chat__island-toolbar">
              <button
                type="button"
                className="tutor-chat__skip"
                disabled={!canSkip}
                onClick={() => void onSkip()}
              >
                Skip
              </button>
              <motion.button
                type="button"
                className={`tutor-chat__send-icon${canSend ? ' tutor-chat__send-icon--ready' : ''}`}
                disabled={!canSend}
                onClick={() => void handleSend()}
                aria-label={chatStatus === 'generating' ? 'Sending' : 'Send message'}
                whileTap={reduceMotion || !canSend ? undefined : { scale: 0.94 }}
                transition={transition(DURATION.micro, reduceMotion)}
              >
                <SendIcon />
              </motion.button>
            </div>
          </div>
        </motion.div>
      )}
    </div>
  );
}
