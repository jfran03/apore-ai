import { useState } from 'react';

export interface GradeResult {
  question_number: number;
  correct: string;
  hint_count: number;
  turn_count: number;
  hedging_count: number;
  flag_reason?: string | null;
  assisted?: boolean;
  /** Tutor grade explanation shown after submit (Correct./Not quite. prose). */
  feedback?: string | null;
}

interface SignalCaptureProps {
  phase: 'answer' | 'rating';
  graded: GradeResult | null;
  onSubmitAnswer: (response: string) => void | Promise<void>;
  onSubmitRating: (rating: 'easy' | 'ok' | 'hard') => void | Promise<void>;
  loading: boolean;
}

type Rating = 'easy' | 'ok' | 'hard';

export function SignalCapture({
  phase,
  graded,
  onSubmitAnswer,
  onSubmitRating,
  loading,
}: SignalCaptureProps) {
  const [response, setResponse] = useState('');
  const [rating, setRating] = useState<Rating | null>(null);

  const canSubmitAnswer = !loading && phase === 'answer' && response.trim().length > 0;
  const canSubmitRating = !loading && phase === 'rating' && rating !== null;

  async function handleSubmitAnswer() {
    if (!canSubmitAnswer) return;
    const text = response.trim();
    await onSubmitAnswer(text);
    setResponse('');
  }

  async function handleSubmitRating() {
    if (!canSubmitRating || rating === null) return;
    await onSubmitRating(rating);
    setRating(null);
  }

  const verdictCorrect = graded?.correct === 'yes';

  return (
    <div className="signal-capture">
      {phase === 'rating' && graded && (
        <div
          className={`signal-capture__verdict signal-capture__verdict--${verdictCorrect ? 'correct' : 'incorrect'}`}
          role="status"
          aria-live="polite"
        >
          {verdictCorrect ? '✓ Correct' : '✗ Incorrect'}
        </div>
      )}

      {phase === 'answer' && (
        <>
          <textarea
            className="signal-capture__textarea"
            rows={3}
            placeholder="Write your response here..."
            value={response}
            onChange={(e) => setResponse(e.target.value)}
            disabled={loading}
            aria-label="Your response"
          />
          <div className="signal-capture__footer">
            <button
              type="button"
              className="btn btn--primary signal-capture__submit"
              disabled={!canSubmitAnswer}
              onClick={handleSubmitAnswer}
            >
              {loading ? 'Grading…' : 'Submit answer'}
            </button>
          </div>
        </>
      )}

      {phase === 'rating' && (
        <>
          <p className="signal-capture__rating-prompt">How difficult was this question?</p>
          <div className="signal-capture__controls">
            <div className="signal-capture__group" role="group" aria-label="Difficulty rating">
              {(['easy', 'ok', 'hard'] as Rating[]).map((r) => (
                <button
                  key={r}
                  type="button"
                  className={`signal-capture__btn signal-capture__btn--rating signal-capture__btn--${r}${rating === r ? ' signal-capture__btn--selected' : ''}`}
                  onClick={() => setRating(r)}
                  disabled={loading}
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
              onClick={handleSubmitRating}
            >
              {loading ? 'Saving…' : 'Continue'}
            </button>
          </div>
        </>
      )}
    </div>
  );
}
