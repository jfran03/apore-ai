import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from 'react';
import {
  getDomainSession,
  postDomainQuestion,
  postDomainTurn,
} from '../api/client';
import type { TranscriptEvent, TurnResponse } from '../api/types';
import { chatReducer, initialChatState, type ChatAction, type ChatState } from '../chat/machine';

export interface TutorSession {
  state: ChatState;
  sendMessage: (text: string) => void;
  rate: (rating: 'easy' | 'ok' | 'hard') => void;
  continueNext: () => void;
  skip: () => void;
  dismissError: () => void;
}

function eventsFromTurn(body: Record<string, unknown>, result: TurnResponse): TranscriptEvent[] {
  const ts = new Date().toISOString();
  const events: TranscriptEvent[] = [];

  if (result.tutor_message) {
    events.push({ type: 'tutor_message', ts, text: result.tutor_message });
  }

  if (result.phase === 'graded') {
    events.push({ type: 'graded', ts, correct: result.correct });
  }

  if (result.phase === 'reflection' && body.explicit_rating) {
    events.push({
      type: 'rating',
      ts,
      rating: result.explicit_rating ?? String(body.explicit_rating),
      reward: result.reward,
      new_difficulty: result.new_difficulty,
    });
  }

  return events;
}

type TutorSessionAction = ChatAction | { type: 'session_reset' };

function tutorSessionReducer(state: ChatState, action: TutorSessionAction): ChatState {
  if (action.type === 'session_reset') {
    return initialChatState();
  }

  return chatReducer(state, action);
}

export function useTutorSession(domainId: string, sessionId: string): TutorSession {
  const sessionKey = `${domainId}\0${sessionId}`;
  const pendingState = useMemo(() => initialChatState(), [sessionKey]);
  const [state, dispatch] = useReducer(tutorSessionReducer, undefined, initialChatState);
  const [loadedSessionKey, setLoadedSessionKey] = useState<string | null>(null);
  const generationRef = useRef(0);
  const questionBusyRef = useRef(false);
  const turnBusyRef = useRef(false);

  useEffect(() => {
    generationRef.current += 1;
    const generation = generationRef.current;

    questionBusyRef.current = false;
    turnBusyRef.current = false;
    setLoadedSessionKey(null);
    dispatch({ type: 'session_reset' });

    getDomainSession(domainId, sessionId)
      .then((detail) => {
        if (generationRef.current === generation) {
          dispatch({ type: 'detail_loaded', detail });
          setLoadedSessionKey(sessionKey);
        }
      })
      .catch((err) => {
        if (generationRef.current === generation) {
          dispatch({
            type: 'request_failed',
            message: err instanceof Error ? err.message : String(err),
          });
          setLoadedSessionKey(sessionKey);
        }
      });
  }, [domainId, sessionId, sessionKey]);

  useEffect(() => {
    if (
      loadedSessionKey !== sessionKey ||
      state.status !== 'loading_question' ||
      questionBusyRef.current
    ) {
      return;
    }

    const generation = generationRef.current;
    let cancelled = false;
    questionBusyRef.current = true;
    dispatch({ type: 'question_requested' });

    postDomainQuestion(domainId, sessionId)
      .then((question) => {
        if (!cancelled && generationRef.current === generation) {
          dispatch({ type: 'question_received', question });
        }
      })
      .catch((err) => {
        if (!cancelled && generationRef.current === generation) {
          dispatch({
            type: 'request_failed',
            message: err instanceof Error ? err.message : String(err),
          });
        }
      })
      .finally(() => {
        if (generationRef.current === generation) {
          questionBusyRef.current = false;
        }
      });

    return () => {
      cancelled = true;
    };
  }, [state.status, domainId, loadedSessionKey, sessionId, sessionKey]);

  const runTurn = useCallback(
    (body: Record<string, unknown>, applyOptimisticUpdate: () => void) => {
      if (turnBusyRef.current) return;

      const generation = generationRef.current;
      turnBusyRef.current = true;
      applyOptimisticUpdate();

      postDomainTurn(domainId, sessionId, body)
        .then((result) => {
          if (generationRef.current === generation) {
            dispatch({ type: 'turn_result', result, localEvents: eventsFromTurn(body, result) });
          }
        })
        .catch((err) => {
          if (generationRef.current === generation) {
            dispatch({
              type: 'request_failed',
              message: err instanceof Error ? err.message : String(err),
            });
          }
        })
        .finally(() => {
          if (generationRef.current === generation) {
            turnBusyRef.current = false;
          }
        });
    },
    [domainId, sessionId],
  );

  return {
    state: loadedSessionKey === sessionKey ? state : pendingState,
    sendMessage: (text: string) => {
      runTurn({ learner_message: text }, () => dispatch({ type: 'message_sent', text }));
    },
    rate: (rating) => {
      runTurn({ explicit_rating: rating }, () => dispatch({ type: 'rating_sent', rating }));
    },
    continueNext: () => {
      runTurn({ continue: true }, () => dispatch({ type: 'continue_sent' }));
    },
    skip: () => {
      runTurn({ skip: true }, () =>
        dispatch({ type: 'message_sent', text: '(skip this question)' }),
      );
    },
    dismissError: () => dispatch({ type: 'error_dismissed' }),
  };
}
