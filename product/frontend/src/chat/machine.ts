import type {
  QuestionResponse,
  SessionPhase,
  TranscriptEvent,
  TurnResponse,
  WorkspaceSessionDetail,
} from '../api/types';

export type ChatStatus =
  | 'boot'
  | 'loading_question'
  | 'awaiting_answer'
  | 'working'
  | 'awaiting_rating'
  | 'reflection'
  | 'complete'
  | 'error';

export interface ChatState {
  status: ChatStatus;
  transcript: TranscriptEvent[];
  questionsAsked: number;
  maxQuestions: number;
  scalar: number;
  error: string | null;
  errorRecovery: ChatStatus;
}

export type ChatAction =
  | { type: 'detail_loaded'; detail: WorkspaceSessionDetail }
  | { type: 'question_requested' }
  | { type: 'question_received'; question: QuestionResponse }
  | { type: 'message_sent'; text: string }
  | { type: 'rating_sent'; rating: string }
  | { type: 'continue_sent' }
  | { type: 'turn_result'; result: TurnResponse; localEvents: TranscriptEvent[] }
  | { type: 'request_failed'; message: string }
  | { type: 'error_dismissed' };

export function initialChatState(): ChatState {
  return {
    status: 'boot',
    transcript: [],
    questionsAsked: 0,
    maxQuestions: 10,
    scalar: 0.5,
    error: null,
    errorRecovery: 'boot',
  };
}

const PHASE_TO_STATUS: Record<SessionPhase, ChatStatus> = {
  idle: 'loading_question',
  awaiting_answer: 'awaiting_answer',
  awaiting_rating: 'awaiting_rating',
  reflection: 'reflection',
  complete: 'complete',
};

const TURN_PHASE_TO_STATUS: Record<TurnResponse['phase'], ChatStatus> = {
  dialogue: 'awaiting_answer',
  skip_prompt: 'awaiting_answer',
  graded: 'awaiting_rating',
  reflection: 'reflection',
  completed: 'loading_question',
  session_complete: 'complete',
};

export function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case 'detail_loaded':
      return {
        ...state,
        status: PHASE_TO_STATUS[action.detail.phase],
        transcript: [...action.detail.transcript],
        questionsAsked: action.detail.question_count,
        maxQuestions: action.detail.max_questions,
        scalar: action.detail.scalar,
        error: null,
      };
    case 'question_requested':
      return { ...state, status: 'loading_question', errorRecovery: state.status };
    case 'question_received':
      return {
        ...state,
        status: 'awaiting_answer',
        questionsAsked: action.question.question_number,
        transcript: [
          ...state.transcript,
          {
            type: 'question',
            ts: new Date().toISOString(),
            question_number: action.question.question_number,
            question_id: action.question.question_id,
            concept_id: action.question.concept_id,
            concept_label: action.question.concept_label,
            question_text: action.question.question_text,
          },
        ],
      };
    case 'message_sent':
      return {
        ...state,
        status: 'working',
        errorRecovery: state.status,
        transcript: [
          ...state.transcript,
          { type: 'learner_message', ts: new Date().toISOString(), text: action.text },
        ],
      };
    case 'rating_sent':
    case 'continue_sent':
      return { ...state, status: 'working', errorRecovery: state.status };
    case 'turn_result': {
      const nextState: ChatState = {
        ...state,
        status: TURN_PHASE_TO_STATUS[action.result.phase],
        transcript: [...state.transcript, ...action.localEvents],
      };

      if (action.result.new_difficulty !== null && action.result.new_difficulty !== undefined) {
        nextState.scalar = action.result.new_difficulty;
      }

      return nextState;
    }
    case 'request_failed':
      return { ...state, status: 'error', error: action.message };
    case 'error_dismissed':
      return { ...state, status: state.errorRecovery, error: null };
    default:
      return state;
  }
}
