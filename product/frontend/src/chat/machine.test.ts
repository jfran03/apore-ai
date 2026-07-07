import { describe, expect, it } from 'vitest';
import { chatReducer, initialChatState, type ChatState } from './machine';
import type { QuestionResponse, TurnResponse, WorkspaceSessionDetail } from '../api/types';

const question: QuestionResponse = {
  question_number: 1,
  question_id: 'q1',
  concept_id: 'sets',
  concept_label: 'Sets',
  question_type: 'recall',
  intended_difficulty: 0.5,
  question_text: 'What is a set?',
};

function detail(phase: WorkspaceSessionDetail['phase']): WorkspaceSessionDetail {
  return {
    session_id: 's1',
    title: 'T',
    chapter_id: '01',
    knowledge_source: 'workspace:d/01',
    created_at: '',
    updated_at: '',
    question_count: 1,
    max_questions: 10,
    scalar: 0.5,
    phase,
    transcript: [],
  };
}

function turn(phase: TurnResponse['phase'], extra: Partial<TurnResponse> = {}): TurnResponse {
  return {
    phase,
    question_number: 1,
    tutor_message: 'msg',
    question_closed: false,
    correct: 'yes',
    explicit_rating: null,
    reward: null,
    new_difficulty: null,
    flag_reason: null,
    ...extra,
  };
}

describe('chatReducer', () => {
  it('maps loaded detail phases to statuses', () => {
    expect(chatReducer(initialChatState(), { type: 'detail_loaded', detail: detail('idle') }).status)
      .toBe('loading_question');
    expect(chatReducer(initialChatState(), { type: 'detail_loaded', detail: detail('awaiting_rating') }).status)
      .toBe('awaiting_rating');
    expect(chatReducer(initialChatState(), { type: 'detail_loaded', detail: detail('reflection') }).status)
      .toBe('reflection');
    expect(chatReducer(initialChatState(), { type: 'detail_loaded', detail: detail('complete') }).status)
      .toBe('complete');
  });

  it('runs the happy path: question -> answer -> graded -> rating -> reflection -> continue -> next question', () => {
    let state: ChatState = chatReducer(initialChatState(), {
      type: 'detail_loaded', detail: detail('idle'),
    });
    state = chatReducer(state, { type: 'question_received', question });
    expect(state.status).toBe('awaiting_answer');
    expect(state.transcript[state.transcript.length - 1]?.type).toBe('question');

    state = chatReducer(state, { type: 'message_sent', text: 'a set is a collection' });
    expect(state.status).toBe('working');
    expect(state.transcript[state.transcript.length - 1]?.type).toBe('learner_message');

    state = chatReducer(state, {
      type: 'turn_result',
      result: turn('graded'),
      localEvents: [
        { type: 'tutor_message', ts: '', text: 'feedback' },
        { type: 'graded', ts: '', correct: 'yes' },
      ],
    });
    expect(state.status).toBe('awaiting_rating');

    state = chatReducer(state, { type: 'rating_sent', rating: 'ok' });
    expect(state.status).toBe('working');
    state = chatReducer(state, {
      type: 'turn_result',
      result: turn('reflection', { new_difficulty: 0.55 }),
      localEvents: [{ type: 'rating', ts: '', rating: 'ok', reward: 0.4, new_difficulty: 0.55 }],
    });
    expect(state.status).toBe('reflection');
    expect(state.scalar).toBe(0.55);

    state = chatReducer(state, { type: 'continue_sent' });
    state = chatReducer(state, { type: 'turn_result', result: turn('completed'), localEvents: [] });
    expect(state.status).toBe('loading_question');
  });

  it('session_complete ends the session', () => {
    let state = chatReducer(initialChatState(), { type: 'detail_loaded', detail: detail('reflection') });
    state = chatReducer(state, { type: 'continue_sent' });
    state = chatReducer(state, { type: 'turn_result', result: turn('session_complete'), localEvents: [] });
    expect(state.status).toBe('complete');
  });

  it('request failure preserves recovery status', () => {
    let state = chatReducer(initialChatState(), { type: 'detail_loaded', detail: detail('idle') });
    state = chatReducer(state, { type: 'question_received', question });
    state = chatReducer(state, { type: 'message_sent', text: 'answer' });
    state = chatReducer(state, { type: 'request_failed', message: 'boom' });
    expect(state.status).toBe('error');
    expect(state.error).toBe('boom');
    state = chatReducer(state, { type: 'error_dismissed' });
    expect(state.status).toBe('awaiting_answer');
  });

  it('resume mid-turn: awaiting_rating detail leads straight to rating chips', () => {
    const state = chatReducer(initialChatState(), {
      type: 'detail_loaded', detail: detail('awaiting_rating'),
    });
    expect(state.status).toBe('awaiting_rating');
  });
});
