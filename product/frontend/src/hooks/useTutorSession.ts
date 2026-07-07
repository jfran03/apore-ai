import { useCallback, useEffect, useReducer, useRef } from 'react';
import {
  getDomainSession,
  postDomainQuestion,
  postDomainTurn,
} from '../api/client';
import type { TranscriptEvent, TurnResponse } from '../api/types';
import { chatReducer, initialChatState, type ChatState } from '../chat/machine';

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

export function useTutorSession(domainId: string, sessionId: string): TutorSession {
  const [state, dispatch] = useReducer(chatReducer, undefined, initialChatState);
  const busyRef = useRef(false);
  const questionRequestRef = useRef(0);

  useEffect(() => {
    let cancelled = false;

    getDomainSession(domainId, sessionId)
      .then((detail) => {
        if (!cancelled) dispatch({ type: 'detail_loaded', detail });
      })
      .catch((err) => {
        if (!cancelled) {
          dispatch({
            type: 'request_failed',
            message: err instanceof Error ? err.message : String(err),
          });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [domainId, sessionId]);

  useEffect(() => {
    questionRequestRef.current += 1;
    busyRef.current = false;
  }, [domainId, sessionId]);

  useEffect(() => {
    if (state.status !== 'loading_question' || busyRef.current) return;

    const requestId = questionRequestRef.current + 1;
    let cancelled = false;
    questionRequestRef.current = requestId;
    busyRef.current = true;
    dispatch({ type: 'question_requested' });

    postDomainQuestion(domainId, sessionId)
      .then((question) => {
        if (!cancelled) dispatch({ type: 'question_received', question });
      })
      .catch((err) => {
        if (!cancelled) {
          dispatch({
            type: 'request_failed',
            message: err instanceof Error ? err.message : String(err),
          });
        }
      })
      .finally(() => {
        if (questionRequestRef.current === requestId) busyRef.current = false;
      });

    return () => {
      cancelled = true;
    };
  }, [state.status, domainId, sessionId]);

  const runTurn = useCallback(
    (body: Record<string, unknown>) => {
      postDomainTurn(domainId, sessionId, body)
        .then((result) =>
          dispatch({ type: 'turn_result', result, localEvents: eventsFromTurn(body, result) }),
        )
        .catch((err) =>
          dispatch({
            type: 'request_failed',
            message: err instanceof Error ? err.message : String(err),
          }),
        );
    },
    [domainId, sessionId],
  );

  return {
    state,
    sendMessage: (text: string) => {
      dispatch({ type: 'message_sent', text });
      runTurn({ learner_message: text });
    },
    rate: (rating) => {
      dispatch({ type: 'rating_sent', rating });
      runTurn({ explicit_rating: rating });
    },
    continueNext: () => {
      dispatch({ type: 'continue_sent' });
      runTurn({ continue: true });
    },
    skip: () => {
      dispatch({ type: 'message_sent', text: '(skip this question)' });
      runTurn({ skip: true });
    },
    dismissError: () => dispatch({ type: 'error_dismissed' }),
  };
}
