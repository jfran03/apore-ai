import { useState, useCallback, useRef, useEffect } from 'react';
import {
  createSession,
  fetchQuestion,
  postTurn,
  getSessionState,
  getStoredKnowledgeSource,
  setStoredKnowledgeSource,
} from '../api/client';
import type { QuestionResponse, TurnResponse } from '../api/types';
import { parseKnowledgeSource, useActiveDomain } from '../shell/ActiveDomainContext';
import { QuestionCard } from '../components/QuestionCard';
import { QuestionHistoryCard, type HistoryRecord } from '../components/QuestionHistoryCard';
import {
  TutorChatCard,
  type ChatStatus,
  type DialogueMessage,
} from '../components/TutorChatCard';
import type { GradeResult } from '../components/SignalCapture';
import { ScalarBadge } from '../components/ScalarBadge';
import '../styles/setup.css';
import '../styles/study.css';

type FocusMode = 'adaptive' | 'weak_points';

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
  title: string;
  maxQuestions: number;
  scalar: number;
  questionCount: number;
  currentQuestion: CurrentQuestion | null;
  history: HistoryRecord[];
  dialogueMessages: DialogueMessage[];
  chatStatus: ChatStatus;
  pendingReveal: string | null;
  skipPrompt: boolean;
  phase: 'dialogue' | 'rating' | 'reflection';
  graded: GradeResult | null;
  ratingContext: {
    question_number: number;
    question_text: string;
    lastLearnerMessage: string;
  } | null;
  /** Grading fields held until learner continues after optional reflection chat */
  pendingAdvance: {
    question_number: number;
    question_text: string;
    explicit_rating: 'easy' | 'ok' | 'hard';
    correct: string;
    reward?: number;
  } | null;
}

interface SessionCompleteSummary {
  title: string;
  questionsAnswered: number;
  scalar: number;
}

const LENGTH_PRESETS = [5, 10, 15] as const;

function chapterStudyReady(chapter: {
  has_concept_graph: boolean;
  has_question_bank: boolean;
  question_bank_count: number;
}): boolean {
  return chapter.has_concept_graph && chapter.has_question_bank && chapter.question_bank_count > 0;
}

let messageId = 0;
function nextMessageId(): string {
  messageId += 1;
  return `msg-${messageId}`;
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

function gradeFromTurn(res: TurnResponse): GradeResult {
  return {
    question_number: res.question_number,
    correct: res.correct,
    hint_count: res.hint_count,
    turn_count: res.turn_count,
    hedging_count: res.hedging_count,
    flag_reason: res.flag_reason,
  };
}

export function Study() {
  const { activeDomain, catalogError } = useActiveDomain();

  const stored = parseKnowledgeSource(getStoredKnowledgeSource());
  const [chapterId, setChapterId] = useState(stored?.chapterId ?? '01-set-theory');
  const [focusMode, setFocusMode] = useState<FocusMode>('adaptive');
  const [sessionLength, setSessionLength] = useState(10);

  const [session, setSession] = useState<SessionState | null>(null);
  const [sessionComplete, setSessionComplete] = useState<SessionCompleteSummary | null>(null);
  const [startLoading, setStartLoading] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const [questionLoading, setQuestionLoading] = useState(false);
  const [questionError, setQuestionError] = useState<string | null>(null);
  const [submitLoading, setSubmitLoading] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const pendingAfterReveal = useRef<(() => void) | null>(null);

  useEffect(() => {
    if (!activeDomain?.chapters.length) return;
    if (!activeDomain.chapters.some((c) => c.id === chapterId)) {
      setChapterId(activeDomain.chapters[0].id);
    }
  }, [activeDomain, chapterId]);

  const selectedChapter = activeDomain?.chapters.find((c) => c.id === chapterId);
  const canStart =
    selectedChapter != null && chapterStudyReady(selectedChapter) && sessionLength >= 1 && sessionLength <= 50;

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
          title: state.title,
          maxQuestions: state.max_questions,
          scalar: state.scalar,
          questionCount: state.question_count,
          currentQuestion: buildCurrentQuestion(q),
          dialogueMessages: [],
          chatStatus: 'idle',
          pendingReveal: null,
          skipPrompt: false,
          phase: 'dialogue',
          graded: null,
          ratingContext: null,
          pendingAdvance: null,
        };
      });
    } catch (err) {
      setQuestionError(err instanceof Error ? err.message : 'Failed to load question');
    } finally {
      setQuestionLoading(false);
    }
  }, []);

  const handleStartSession = useCallback(async () => {
    if (!selectedChapter || !canStart) return;
    setStoredKnowledgeSource(selectedChapter.knowledge_source);
    setStartLoading(true);
    setStartError(null);
    setSessionComplete(null);
    try {
      const res = await createSession({
        knowledge_source: selectedChapter.knowledge_source,
        focus_mode: focusMode,
        max_questions: sessionLength,
      });
      const state = await getSessionState(res.session_id);
      setSession({
        sessionId: res.session_id,
        title: res.title,
        maxQuestions: res.max_questions,
        scalar: state.scalar,
        questionCount: state.question_count,
        currentQuestion: null,
        history: [],
        dialogueMessages: [],
        chatStatus: 'idle',
        pendingReveal: null,
        skipPrompt: false,
        phase: 'dialogue',
        graded: null,
        ratingContext: null,
        pendingAdvance: null,
      });
      await loadNextQuestion(res.session_id);
    } catch (err) {
      setStartError(err instanceof Error ? err.message : 'Failed to start session');
    } finally {
      setStartLoading(false);
    }
  }, [selectedChapter, canStart, focusMode, sessionLength, loadNextQuestion]);

  const handleNewSession = useCallback(() => {
    setSession(null);
    setSessionComplete(null);
    setStartError(null);
    setQuestionError(null);
    setSubmitError(null);
  }, []);

  const beginTutorReveal = useCallback(
    (tutorMessage: string, afterReveal: () => void) => {
      pendingAfterReveal.current = afterReveal;
      setSession((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          chatStatus: 'revealing',
          pendingReveal: tutorMessage,
        };
      });
    },
    [],
  );

  const handleRevealComplete = useCallback(() => {
    const after = pendingAfterReveal.current;
    pendingAfterReveal.current = null;

    setSession((prev) => {
      if (!prev || !prev.pendingReveal) return prev;
      const assistantMsg: DialogueMessage = {
        id: nextMessageId(),
        role: 'assistant',
        content: prev.pendingReveal,
      };
      return {
        ...prev,
        dialogueMessages: [...prev.dialogueMessages, assistantMsg],
        chatStatus: 'idle',
        pendingReveal: null,
      };
    });

    after?.();
  }, []);

  const handleTurnResponse = useCallback(
    (res: TurnResponse, lastLearnerMessage: string) => {
      if (
        res.phase === 'dialogue' ||
        res.phase === 'skip_prompt' ||
        res.phase === 'reflection'
      ) {
        const tutorText = res.tutor_message ?? '';
        beginTutorReveal(tutorText, () => {
          setSession((prev) => {
            if (!prev) return prev;
            return {
              ...prev,
              phase: res.phase === 'reflection' ? 'reflection' : prev.phase,
              skipPrompt: res.phase === 'skip_prompt',
            };
          });
        });
        return;
      }

      if (res.phase === 'graded') {
        const tutorText = res.tutor_message ?? '';
        const graded = gradeFromTurn(res);
        const enterRating = () => {
          setSession((prev) => {
            if (!prev) return prev;
            const ctx = prev.currentQuestion
              ? {
                  question_number: prev.currentQuestion.question_number,
                  question_text: prev.currentQuestion.question_text,
                  lastLearnerMessage: lastLearnerMessage,
                }
              : prev.ratingContext;
            return {
              ...prev,
              phase: 'rating',
              graded,
              skipPrompt: false,
              ratingContext: ctx,
              currentQuestion: prev.currentQuestion,
            };
          });
        };

        if (tutorText) {
          beginTutorReveal(tutorText, enterRating);
        } else {
          enterRating();
        }
      }
    },
    [beginTutorReveal],
  );

  const handleSendMessage = useCallback(
    async (text: string) => {
      if (!session?.currentQuestion) return;
      setSubmitLoading(true);
      setSubmitError(null);

      const userMsg: DialogueMessage = {
        id: nextMessageId(),
        role: 'user',
        content: text,
      };

      setSession((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          dialogueMessages: [...prev.dialogueMessages, userMsg],
          chatStatus: 'generating',
        };
      });

      try {
        const res = await postTurn(session.sessionId, { learner_message: text });
        handleTurnResponse(res, text);
      } catch (err) {
        setSubmitError(err instanceof Error ? err.message : 'Failed to send message');
        setSession((prev) => {
          if (!prev) return prev;
          return { ...prev, chatStatus: 'idle' };
        });
      } finally {
        setSubmitLoading(false);
      }
    },
    [session, handleTurnResponse],
  );

  const handleSkip = useCallback(async () => {
    if (!session?.currentQuestion) return;
    setSubmitLoading(true);
    setSubmitError(null);
    setSession((prev) => {
      if (!prev) return prev;
      return { ...prev, chatStatus: 'generating' };
    });

    try {
      const res = await postTurn(session.sessionId, { skip: true });
      handleTurnResponse(res, '');
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'Failed to skip question');
      setSession((prev) => {
        if (!prev) return prev;
        return { ...prev, chatStatus: 'idle' };
      });
    } finally {
      setSubmitLoading(false);
    }
  }, [session, handleTurnResponse]);

  const finishQuestionAdvance = useCallback(
    async (
      turnRes: TurnResponse,
      pending: NonNullable<SessionState['pendingAdvance']>,
    ) => {
      if (!session) return;

      const record: HistoryRecord = {
        question_number: pending.question_number,
        question_text: pending.question_text,
        explicit_rating: (turnRes.explicit_rating ?? pending.explicit_rating) as
          | 'easy'
          | 'ok'
          | 'hard',
        correct: turnRes.correct ?? pending.correct,
        reward: turnRes.reward ?? pending.reward,
      };

      const nextScalar = turnRes.new_difficulty ?? session.scalar;
      const nextHistory = [...session.history, record];

      if (turnRes.phase === 'session_complete') {
        setSessionComplete({
          title: session.title,
          questionsAnswered: nextHistory.length,
          scalar: nextScalar,
        });
        setSession(null);
        return;
      }

      setSession((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          scalar: nextScalar,
          history: nextHistory,
          dialogueMessages: [],
          chatStatus: 'idle',
          pendingReveal: null,
          skipPrompt: false,
          phase: 'dialogue',
          graded: null,
          ratingContext: null,
          pendingAdvance: null,
          currentQuestion: null,
        };
      });

      await loadNextQuestion(session.sessionId);
    },
    [session, loadNextQuestion],
  );

  const handleSubmitRating = useCallback(
    async (rating: 'easy' | 'ok' | 'hard') => {
      if (!session?.graded || !session.ratingContext) return;
      setSubmitLoading(true);
      setSubmitError(null);
      try {
        const turnRes = await postTurn(session.sessionId, { explicit_rating: rating });

        if (turnRes.phase !== 'reflection') {
          throw new Error('Expected reflection phase after submitting rating');
        }

        const pendingAdvance = {
          question_number: session.ratingContext.question_number,
          question_text: session.ratingContext.question_text,
          explicit_rating: (turnRes.explicit_rating ?? rating) as 'easy' | 'ok' | 'hard',
          correct: turnRes.correct,
          reward: turnRes.reward ?? undefined,
        };

        setSession((prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            scalar: turnRes.new_difficulty ?? prev.scalar,
            phase: 'reflection',
            graded: null,
            pendingAdvance,
            skipPrompt: false,
            chatStatus: 'idle',
          };
        });
      } catch (err) {
        setSubmitError(err instanceof Error ? err.message : 'Failed to submit rating');
      } finally {
        setSubmitLoading(false);
      }
    },
    [session],
  );

  const handleContinueToNext = useCallback(async () => {
    if (!session?.pendingAdvance) return;
    setSubmitLoading(true);
    setSubmitError(null);
    try {
      const turnRes = await postTurn(session.sessionId, { continue: true });
      if (turnRes.phase !== 'completed' && turnRes.phase !== 'session_complete') {
        throw new Error('Expected completed phase after continuing');
      }
      await finishQuestionAdvance(turnRes, session.pendingAdvance);
    } catch (err) {
      setSubmitError(
        err instanceof Error ? err.message : 'Failed to continue to next question',
      );
    } finally {
      setSubmitLoading(false);
    }
  }, [session, finishQuestionAdvance]);

  if (sessionComplete) {
    return (
      <main className="study-page">
        <div className="study-start study-complete">
          <h1 className="study-start__heading">Session complete</h1>
          <p className="study-start__sub">{sessionComplete.title}</p>
          <div className="study-complete__stats">
            <p>
              Questions answered: <strong>{sessionComplete.questionsAnswered}</strong>
            </p>
            <p>
              Final difficulty: <strong>{sessionComplete.scalar.toFixed(2)}</strong>
            </p>
          </div>
          <button
            type="button"
            className="btn btn--primary study-start__btn"
            onClick={handleNewSession}
          >
            Start new session
          </button>
        </div>
      </main>
    );
  }

  if (!session) {
    return (
      <main className="study-page study-preamble-page">
        <div className="study-preamble">
          <h1 className="study-start__heading">Study Session</h1>
          <p className="study-start__sub">
            New session in <strong>{activeDomain?.id ?? '…'}</strong> — choose a chapter,
            focus, and session length.
          </p>

          {catalogError && <p className="study-start__error">{catalogError}</p>}

          <section className="setup-section" aria-labelledby="study-chapter-heading">
            <h2 id="study-chapter-heading" className="setup-section__heading">
              Chapter
            </h2>
            <div className="setup-radio" role="radiogroup" aria-label="Chapter">
              {activeDomain?.chapters.map((c) => {
                const ready = chapterStudyReady(c);
                return (
                  <label key={c.id} className={!ready ? 'study-preamble__disabled' : undefined}>
                    <input
                      type="radio"
                      name="chapter"
                      value={c.id}
                      checked={chapterId === c.id}
                      disabled={!ready}
                      onChange={() => setChapterId(c.id)}
                    />
                    <span>
                      {c.id}
                      {c.has_concept_graph ? ' · graph ready' : ' · needs graph'}
                      {c.has_question_bank
                        ? ` · ${c.question_bank_count} questions`
                        : ' · no question bank'}
                    </span>
                  </label>
                );
              })}
            </div>
          </section>

          <section className="setup-section" aria-labelledby="study-focus-heading">
            <h2 id="study-focus-heading" className="setup-section__heading">
              Focus
            </h2>
            <div className="setup-radio" role="radiogroup" aria-label="Focus mode">
              <label>
                <input
                  type="radio"
                  name="focus"
                  checked={focusMode === 'adaptive'}
                  onChange={() => setFocusMode('adaptive')}
                />
                <span>
                  Adaptive — calibration on early questions, then balanced progression
                </span>
              </label>
              <label>
                <input
                  type="radio"
                  name="focus"
                  checked={focusMode === 'weak_points'}
                  onChange={() => setFocusMode('weak_points')}
                />
                <span>
                  Focus weak points — prioritize concepts with low mastery (skips calibration)
                </span>
              </label>
            </div>
          </section>

          <section className="setup-section" aria-labelledby="study-length-heading">
            <h2 id="study-length-heading" className="setup-section__heading">
              Session length
            </h2>
            <div className="study-preamble__length">
              {LENGTH_PRESETS.map((n) => (
                <button
                  key={n}
                  type="button"
                  className={`study-preamble__chip${sessionLength === n ? ' study-preamble__chip--active' : ''}`}
                  onClick={() => setSessionLength(n)}
                >
                  {n}
                </button>
              ))}
              <label className="study-preamble__custom">
                <span className="study-preamble__custom-label">Custom</span>
                <input
                  type="number"
                  className="setup-input study-preamble__number"
                  min={1}
                  max={50}
                  value={sessionLength}
                  onChange={(e) => {
                    const val = Number.parseInt(e.target.value, 10);
                    if (!Number.isNaN(val)) setSessionLength(Math.min(50, Math.max(1, val)));
                  }}
                />
              </label>
            </div>
          </section>

          <button
            type="button"
            className="btn btn--primary study-start__btn"
            onClick={handleStartSession}
            disabled={startLoading || !canStart}
          >
            {startLoading ? 'Starting…' : 'Start session'}
          </button>
          {startError && <p className="study-start__error">{startError}</p>}
        </div>
      </main>
    );
  }

  const {
    title,
    maxQuestions,
    scalar,
    questionCount,
    currentQuestion,
    history,
    dialogueMessages,
    chatStatus,
    pendingReveal,
    skipPrompt,
    phase,
    graded,
  } = session;
  const busy = submitLoading || questionLoading || chatStatus !== 'idle';
  const showChat =
    !questionLoading &&
    (Boolean(currentQuestion) || phase === 'rating' || phase === 'reflection');
  const progressNumber =
    currentQuestion?.question_number ?? session.ratingContext?.question_number ?? questionCount;

  return (
    <main className="study-page">
      <header className="study-header">
        <p className="study-header__progress">
          {title} · Question {progressNumber} of {maxQuestions}
        </p>
      </header>
      <div className="study-layout">
        <div className="study-layout__question">
          {questionLoading && (
            <p className="study-start__sub">Generating next question…</p>
          )}
          {questionError && <p className="study-start__error">{questionError}</p>}
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

        <div className="study-layout__chat">
          {showChat && (
            <TutorChatCard
              messages={dialogueMessages}
              chatStatus={chatStatus}
              pendingReveal={pendingReveal}
              onRevealComplete={handleRevealComplete}
              phase={phase}
              graded={graded}
              skipPrompt={skipPrompt}
              onSendMessage={handleSendMessage}
              onSkip={handleSkip}
              onSubmitRating={handleSubmitRating}
              onContinueToNext={handleContinueToNext}
              disabled={busy}
            />
          )}
          {submitError && <p className="study-start__error">{submitError}</p>}
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
              <span className="study-sidebar-meta__val">
                {questionCount} / {maxQuestions}
              </span>
            </div>
          </div>
          <ScalarBadge scalar={scalar} label="Difficulty" />
          <QuestionHistoryCard records={history} />
        </aside>
      </div>
    </main>
  );
}
