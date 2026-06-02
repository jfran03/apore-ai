import { useState, useCallback } from 'react';
import { createSession, fetchQuestion, postTurn, getSessionState } from '../api/client';
import type { QuestionResponse } from '../api/types';
import { QuestionCard } from '../components/QuestionCard';
import { TurnThread } from '../components/TurnThread';
import { SignalCapture, type GradeResult } from '../components/SignalCapture';
import { ScalarBadge } from '../components/ScalarBadge';
import type { TurnRecord } from '../components/TurnThread';
import '../styles/study.css';

interface CurrentQuestion {
  question_number: number;
  question_text: string;
  concept_id: string;
  concept_label: string;
  question_type: string;
  intended_difficulty: number;
}

interface SessionState {
  sessionId: string;
  scalar: number;
  questionCount: number;
  currentQuestion: CurrentQuestion | null;
  turns: TurnRecord[];
  capturePhase: 'answer' | 'rating';
  graded: GradeResult | null;
  pendingLearnerResponse: string | null;
}

function buildCurrentQuestion(q: QuestionResponse): CurrentQuestion {
  return {
    question_number: q.question_number,
    question_text: q.question_text,
    concept_id: q.concept_id,
    concept_label: q.concept_label,
    question_type: q.question_type,
    intended_difficulty: q.intended_difficulty,
  };
}

export function Study() {
  const [session, setSession] = useState<SessionState | null>(null);
  const [startLoading, setStartLoading] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const [questionLoading, setQuestionLoading] = useState(false);
  const [questionError, setQuestionError] = useState<string | null>(null);
  const [submitLoading, setSubmitLoading] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const loadNextQuestion = useCallback(async (sessionId: string) => {
    setQuestionLoading(true);
    setQuestionError(null);
    try {
      const q = await fetchQuestion(sessionId, {});
      const state = await getSessionState(sessionId);
      setSession((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          scalar: state.scalar,
          questionCount: state.question_count,
          currentQuestion: buildCurrentQuestion(q),
          capturePhase: 'answer',
          graded: null,
          pendingLearnerResponse: null,
        };
      });
    } catch (err) {
      setQuestionError(err instanceof Error ? err.message : 'Failed to load question');
    } finally {
      setQuestionLoading(false);
    }
  }, []);

  const handleStartSession = useCallback(async () => {
    setStartLoading(true);
    setStartError(null);
    try {
      const res = await createSession({});
      const state = await getSessionState(res.session_id);
      setSession({
        sessionId: res.session_id,
        scalar: state.scalar,
        questionCount: state.question_count,
        currentQuestion: null,
        turns: [],
        capturePhase: 'answer',
        graded: null,
        pendingLearnerResponse: null,
      });
      await loadNextQuestion(res.session_id);
    } catch (err) {
      setStartError(err instanceof Error ? err.message : 'Failed to start session');
    } finally {
      setStartLoading(false);
    }
  }, [loadNextQuestion]);

  const handleSubmitAnswer = useCallback(
    async (response: string) => {
      if (!session?.currentQuestion) return;
      setSubmitLoading(true);
      setSubmitError(null);
      try {
        const gradeRes = await postTurn(session.sessionId, {
          learner_response: response,
          concept_id: session.currentQuestion.concept_id,
        });

        if (gradeRes.phase !== 'graded') {
          throw new Error('Expected graded phase after submitting answer');
        }

        const graded: GradeResult = {
          question_number: gradeRes.question_number,
          correct: gradeRes.correct,
          hint_count: gradeRes.hint_count,
          turn_count: gradeRes.turn_count,
          hedging_count: gradeRes.hedging_count,
          flag_reason: gradeRes.flag_reason,
        };

        setSession((prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            capturePhase: 'rating',
            graded,
            pendingLearnerResponse: response,
          };
        });
      } catch (err) {
        setSubmitError(err instanceof Error ? err.message : 'Failed to grade answer');
      } finally {
        setSubmitLoading(false);
      }
    },
    [session],
  );

  const handleSubmitRating = useCallback(
    async (rating: 'easy' | 'ok' | 'hard') => {
      if (!session?.currentQuestion || !session.graded || !session.pendingLearnerResponse) return;
      setSubmitLoading(true);
      setSubmitError(null);
      try {
        const turnRes = await postTurn(session.sessionId, {
          explicit_rating: rating,
        });

        if (turnRes.phase !== 'completed') {
          throw new Error('Expected completed phase after submitting rating');
        }

        const completedTurn: TurnRecord = {
          question_number: session.currentQuestion.question_number,
          question_text: session.currentQuestion.question_text,
          learner_response: session.pendingLearnerResponse,
          explicit_rating: turnRes.explicit_rating ?? rating,
          correct: turnRes.correct,
          reward: turnRes.reward ?? 0,
          new_difficulty: turnRes.new_difficulty ?? session.scalar,
          inconsistency_flag: turnRes.inconsistency_flag,
        };

        setSession((prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            scalar: turnRes.new_difficulty ?? prev.scalar,
            turns: [...prev.turns, completedTurn],
            capturePhase: 'answer',
            graded: null,
            pendingLearnerResponse: null,
          };
        });

        await loadNextQuestion(session.sessionId);
      } catch (err) {
        setSubmitError(err instanceof Error ? err.message : 'Failed to submit rating');
      } finally {
        setSubmitLoading(false);
      }
    },
    [session, loadNextQuestion],
  );

  if (!session) {
    return (
      <main className="study-page">
        <div className="study-start">
          <h1 className="study-start__heading">Study Session</h1>
          <p className="study-start__sub">
            Start an adaptive session using the knowledge source saved in Setup.
          </p>
          <button
            type="button"
            className="btn btn--primary study-start__btn"
            onClick={handleStartSession}
            disabled={startLoading}
          >
            {startLoading ? 'Starting…' : 'Start Session'}
          </button>
          {startError && (
            <p className="study-start__error">{startError}</p>
          )}
        </div>
      </main>
    );
  }

  const { scalar, questionCount, currentQuestion, turns, capturePhase, graded } = session;
  const busy = submitLoading || questionLoading;
  const showCapture = currentQuestion && !questionLoading;

  return (
    <main className="study-page">
      <div className="study-layout">
        <div className="study-layout__main-thread">
          <TurnThread turns={turns} />
        </div>

        <div className="study-layout__main-question">
          {questionLoading && (
            <p className="study-start__sub">Generating next question…</p>
          )}
          {questionError && (
            <p className="study-start__error">{questionError}</p>
          )}
          {currentQuestion && !questionLoading && (
            <QuestionCard
              question_text={currentQuestion.question_text}
              concept_label={currentQuestion.concept_label}
              concept_id={currentQuestion.concept_id}
              question_type={currentQuestion.question_type}
              intended_difficulty={currentQuestion.intended_difficulty}
              question_number={currentQuestion.question_number}
            />
          )}
        </div>

        <div className="study-layout__main-capture">
          {showCapture && (
            <SignalCapture
              phase={capturePhase}
              graded={graded}
              onSubmitAnswer={handleSubmitAnswer}
              onSubmitRating={handleSubmitRating}
              loading={busy}
            />
          )}
          {submitError && (
            <p className="study-start__error">{submitError}</p>
          )}
        </div>

        <aside className="study-layout__sidebar">
          <div className="study-sidebar-meta">
            <div className="study-sidebar-meta__row">
              <span className="study-sidebar-meta__key">Concept</span>
              <span className="study-sidebar-meta__val">
                {currentQuestion?.concept_label ?? '—'}
              </span>
            </div>
            <div className="study-sidebar-meta__row">
              <span className="study-sidebar-meta__key">Questions</span>
              <span className="study-sidebar-meta__val">{questionCount}</span>
            </div>
          </div>
          <ScalarBadge scalar={scalar} label="Difficulty" />
        </aside>
      </div>
    </main>
  );
}
