import { useState } from 'react';

interface SignalCaptureProps {
  onSubmit: (response: string, rating: string, correct: string) => void;
  loading: boolean;
}

type Rating = 'easy' | 'ok' | 'hard';
type Correct = 'yes' | 'no';

export function SignalCapture({ onSubmit, loading }: SignalCaptureProps) {
  const [response, setResponse] = useState('');
  const [rating, setRating] = useState<Rating | null>(null);
  const [correct, setCorrect] = useState<Correct | null>(null);

  const canSubmit = !loading && response.trim().length > 0 && rating !== null && correct !== null;

  function handleSubmit() {
    if (!canSubmit || rating === null || correct === null) return;
    onSubmit(response.trim(), rating, correct);
    setResponse('');
    setRating(null);
    setCorrect(null);
  }

  return (
    <div className="signal-capture">
      <div className="signal-capture__controls">
        <div className="signal-capture__group" role="group" aria-label="Difficulty rating">
          {(['easy', 'ok', 'hard'] as Rating[]).map((r) => (
            <button
              key={r}
              type="button"
              className={`signal-capture__btn signal-capture__btn--rating signal-capture__btn--${r}${rating === r ? ' signal-capture__btn--selected' : ''}`}
              onClick={() => setRating(r)}
              aria-pressed={rating === r}
            >
              {r.charAt(0).toUpperCase() + r.slice(1)}
            </button>
          ))}
        </div>
        <div className="signal-capture__group" role="group" aria-label="Correctness">
          <button
            type="button"
            className={`signal-capture__btn signal-capture__btn--correct${correct === 'yes' ? ' signal-capture__btn--selected' : ''}`}
            onClick={() => setCorrect('yes')}
            aria-pressed={correct === 'yes'}
          >
            ✓ Correct
          </button>
          <button
            type="button"
            className={`signal-capture__btn signal-capture__btn--incorrect${correct === 'no' ? ' signal-capture__btn--selected' : ''}`}
            onClick={() => setCorrect('no')}
            aria-pressed={correct === 'no'}
          >
            ✗ Incorrect
          </button>
        </div>
      </div>
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
          disabled={!canSubmit}
          onClick={handleSubmit}
        >
          {loading ? 'Submitting…' : 'Submit →'}
        </button>
      </div>
    </div>
  );
}
