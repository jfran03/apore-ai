import { useEffect, useRef, useState } from 'react';

interface ScalarBadgeProps {
  scalar: number;
  label?: string;
}

export function ScalarBadge({ scalar, label = 'Difficulty' }: ScalarBadgeProps) {
  const [displayScalar, setDisplayScalar] = useState(scalar);
  const [flash, setFlash] = useState(false);
  const prevScalar = useRef(scalar);

  useEffect(() => {
    if (scalar !== prevScalar.current) {
      setFlash(true);
      setDisplayScalar(scalar);
      prevScalar.current = scalar;
      const t = setTimeout(() => setFlash(false), 300);
      return () => clearTimeout(t);
    }
  }, [scalar]);

  // Map scalar [0.1, 0.9] to fill percentage
  const fillPct = Math.max(0, Math.min(100, ((displayScalar - 0.1) / 0.8) * 100));

  return (
    <div className="scalar-badge">
      <span className="scalar-badge__label">{label}</span>
      <span className={`scalar-badge__value${flash ? ' scalar-badge__value--flash' : ''}`}>
        {displayScalar.toFixed(2)}
      </span>
      <div className="scalar-badge__track" aria-hidden="true">
        <div
          className="scalar-badge__fill"
          style={{ width: `${fillPct}%` }}
        />
      </div>
    </div>
  );
}
