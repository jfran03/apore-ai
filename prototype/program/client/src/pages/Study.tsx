import { useState, useCallback } from 'react';
import { createSession, postTurn, getSessionState } from '../api/client';
import { QuestionCard } from '../components/QuestionCard';
import { TurnThread } from '../components/TurnThread';
import { SignalCapture } from '../components/SignalCapture';
import { ScalarBadge } from '../components/ScalarBadge';
import type { TurnRecord } from '../components/TurnThread';
import '../styles/study.css';

interface CurrentQuestion {
  question_number: number;
  question_text: string;
  concept: string;
  question_type: string;
  intended_difficulty: number;
}

interface SessionState {
  sessionId: string;
  scalar: number;
  questionCount: number;
  currentQuestion: CurrentQuestion | null;
  turns: TurnRecord[];
}

// The stub backend returns a question as part of TurnResponse.
// question_text in TurnResponse is the *next* question after the turn.
function buildCurrentQuestion(
  questionText: string,
  questionNumber: number,
  difficulty: number,
): CurrentQuestion {
  return {
    question_number: questionNumber,
    question_text: questionText,
    concept: 'set_theory_intro',
    question_type: 'free_response',
    intended_difficulty: difficulty,
  };
}

export function Study() {
  const [session, setSession] = useState<SessionState | null>(null);
  const [startLoading, setStartLoading] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const [submitLoading, setSubmitLoading] = useState(false);

  const handleStartSession = useCallback(async () => {
    setStartLoading(true);
    setStartError(null);
    try {
      const res = await createSession({ provider: 'stub', model: 'stub', fixture: 'apore-lite' });
      // After creating the session, fetch the first question via a lightweight turn
      // The stub provider synthesises a question on the first /turn call.
      // We initialise with a placeholder question and let the first real submit
      // replace it. Alternatively, call postTurn immediately to get Q1.
      const firstTurn = await postTurn(res.session_id, {
        learner_response: '',
        concept_id: 'set_theory_intro',
      });
      const state = await getSessionState(res.session_id);
      setSession({
        sessionId: res.session_id,
        scalar: state.scalar,
        questionCount: state.question_count,
        currentQuestion: buildCurrentQuestion(
          firstTurn.question_text,
          firstTurn.question_number,
          firstTurn.new_difficulty,
        ),
        turns: [],
      });
    } catch (err) {
      setStartError(err instanceof Error ? err.message : 'Failed to start session');
    } finally {
      setStartLoading(false);
    }
  }, []);

  const handleSubmitTurn = useCallback(
    async (response: string, rating: string, correct: string) => {
      if (!session?.currentQuestion) return;
      setSubmitLoading(true);
      try {
        const body = {
          learner_response: response,
          concept_id: 'set_theory_intro',
          explicit_rating: rating,
          correct,
        };

        const turnRes = await postTurn(session.sessionId, body);
        const state = await getSessionState(session.sessionId);

        const completedTurn: TurnRecord = {
          question_number: session.currentQuestion.question_number,
          question_text: session.currentQuestion.question_text,
          learner_response: response,
          explicit_rating: rating,
          correct,
          reward: turnRes.reward,
          new_difficulty: turnRes.new_difficulty,
          inconsistency_flag: turnRes.inconsistency_flag,
        };

        setSession((prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            scalar: state.scalar,
            questionCount: state.question_count,
            turns: [...prev.turns, completedTurn],
            currentQuestion: buildCurrentQuestion(
              turnRes.question_text,
              turnRes.question_number,
              turnRes.new_difficulty,
            ),
          };
        });
      } catch (err) {
        console.error('Turn submission failed:', err);
      } finally {
        setSubmitLoading(false);
      }
    },
    [session],
  );

  if (!session) {
    return (
      <main className="study-page">
        <div className="study-start">
          <h1 className="study-start__heading">Study Session</h1>
          <p className="study-start__sub">
            Start an adaptive session using the set theory introduction fixture.
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

  const { scalar, questionCount, currentQuestion, turns } = session;

  return (
    <main className="study-page">
      <div className="study-layout">
        {/* Left column — thread */}
        <div className="study-layout__main-thread">
          <TurnThread turns={turns} />
        </div>

        {/* Left column — question card */}
        <div className="study-layout__main-question">
          {currentQuestion && (
            <QuestionCard
              question_text={currentQuestion.question_text}
              concept={currentQuestion.concept}
              question_type={currentQuestion.question_type}
              intended_difficulty={currentQuestion.intended_difficulty}
              question_number={currentQuestion.question_number}
            />
          )}
        </div>

        {/* Left column — signal capture */}
        <div className="study-layout__main-capture">
          <SignalCapture onSubmit={handleSubmitTurn} loading={submitLoading} />
        </div>

        {/* Right sidebar */}
        <aside className="study-layout__sidebar">
          <div className="study-sidebar-meta">
            <div className="study-sidebar-meta__row">
              <span className="study-sidebar-meta__key">Concept</span>
              <span className="study-sidebar-meta__val">set_theory_intro</span>
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
