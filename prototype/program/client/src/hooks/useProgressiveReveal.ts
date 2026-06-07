import { useEffect, useRef, useState } from 'react';

function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(() => {
    if (typeof window === 'undefined') return false;
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  });

  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    const handler = () => setReduced(mq.matches);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);

  return reduced;
}

interface ProgressiveRevealOptions {
  wordDelayMs?: number;
  onComplete?: () => void;
}

export function useProgressiveReveal(
  fullText: string,
  active: boolean,
  options: ProgressiveRevealOptions = {},
) {
  const reducedMotion = usePrefersReducedMotion();
  const [displayText, setDisplayText] = useState('');
  const onCompleteRef = useRef(options.onComplete);
  onCompleteRef.current = options.onComplete;
  const wordDelayMs = options.wordDelayMs ?? 40;

  useEffect(() => {
    if (!active || !fullText) {
      setDisplayText('');
      return;
    }

    if (reducedMotion) {
      setDisplayText(fullText);
      onCompleteRef.current?.();
      return;
    }

    const tokens = fullText.match(/\S+\s*|\s+/g) ?? [fullText];
    let index = 0;
    let finished = false;
    setDisplayText('');

    const finish = () => {
      if (finished) return;
      finished = true;
      setDisplayText(fullText);
      onCompleteRef.current?.();
    };

    const tick = () => {
      index += 1;
      if (index >= tokens.length) {
        finish();
        return;
      }
      setDisplayText(tokens.slice(0, index).join(''));
    };

    tick();
    const id = window.setInterval(() => {
      tick();
      if (index >= tokens.length) {
        window.clearInterval(id);
      }
    }, wordDelayMs);
    return () => window.clearInterval(id);
  }, [fullText, active, reducedMotion, wordDelayMs]);

  const isComplete = !active || displayText === fullText || reducedMotion;

  return { displayText: active ? displayText : fullText, isComplete };
}
