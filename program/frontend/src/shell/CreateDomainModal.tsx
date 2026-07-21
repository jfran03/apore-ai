import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { createDomain } from '../api/client';
import { DURATION, EASE_OUT, overlayTransition, panel } from '../motion';
import { useActiveDomain } from './ActiveDomainContext';

const GOAL_PRESETS = [
  { value: 'exam-prep', label: 'Exam prep' },
  { value: 'general-mastery', label: 'General mastery' },
  { value: 'skill-development', label: 'Skill development' },
  { value: 'custom', label: 'Custom…' },
] as const;

const STYLE_PRESETS = [
  { value: 'rigorous', label: 'Rigorous' },
  { value: 'conversational', label: 'Conversational' },
  { value: 'socratic', label: 'Socratic' },
  { value: 'custom', label: 'Custom…' },
] as const;

const GOAL_LABELS: Record<string, string> = {
  'exam-prep': 'Exam prep',
  'general-mastery': 'General mastery',
  'skill-development': 'Skill development',
};

const STYLE_LABELS: Record<string, string> = {
  rigorous: 'Rigorous',
  conversational: 'Conversational',
  socratic: 'Socratic',
};

/** Convert a display name to a lowercase hyphenated domain id. */
export function slugifyDomainName(name: string): string {
  return name
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .replace(/-{2,}/g, '-');
}

interface CreateDomainModalProps {
  open: boolean;
  onClose: () => void;
}

export function CreateDomainModal({ open, onClose }: CreateDomainModalProps) {
  const { setActiveDomainId, refreshCatalog } = useActiveDomain();
  const navigate = useNavigate();
  const nameRef = useRef<HTMLInputElement>(null);
  const reduceMotion = useReducedMotion();
  const dialogMotion = panel(reduceMotion);

  const [name, setName] = useState('');
  const [scope, setScope] = useState('');
  const [goalPreset, setGoalPreset] = useState<string>('general-mastery');
  const [goalCustom, setGoalCustom] = useState('');
  const [stylePreset, setStylePreset] = useState<string>('socratic');
  const [styleCustom, setStyleCustom] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const domainId = slugifyDomainName(name);
  const goalValue =
    goalPreset === 'custom' ? goalCustom.trim() : (GOAL_LABELS[goalPreset] ?? goalPreset);
  const styleValue =
    stylePreset === 'custom' ? styleCustom.trim() : (STYLE_LABELS[stylePreset] ?? stylePreset);

  const canSubmit =
    Boolean(name.trim()) &&
    Boolean(domainId) &&
    Boolean(scope.trim()) &&
    Boolean(goalValue) &&
    Boolean(styleValue) &&
    !busy;

  useEffect(() => {
    if (!open) return;
    setName('');
    setScope('');
    setGoalPreset('general-mastery');
    setGoalCustom('');
    setStylePreset('socratic');
    setStyleCustom('');
    setBusy(false);
    setError(null);
    const t = window.setTimeout(() => nameRef.current?.focus(), 0);
    return () => window.clearTimeout(t);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !busy) onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, busy, onClose]);

  const handleSubmit = async () => {
    if (!canSubmit) return;
    setBusy(true);
    setError(null);
    try {
      await createDomain(domainId, {
        name: name.trim(),
        scope: scope.trim(),
        goal: goalValue,
        tutor_style: styleValue,
      });
      await refreshCatalog();
      setActiveDomainId(domainId);
      onClose();
      navigate('/setup');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create domain');
    } finally {
      setBusy(false);
    }
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="create-domain-modal"
          role="presentation"
          initial={reduceMotion ? false : { opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={reduceMotion ? undefined : { opacity: 0 }}
          transition={overlayTransition(reduceMotion)}
          onClick={(e) => {
            if (e.target === e.currentTarget && !busy) onClose();
          }}
        >
          <motion.form
            className="create-domain-modal__dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="create-domain-title"
            initial={dialogMotion.initial}
            animate={dialogMotion.animate}
            exit={
              reduceMotion
                ? dialogMotion.exit
                : { ...dialogMotion.exit, transition: { duration: DURATION.exit, ease: EASE_OUT } }
            }
            transition={dialogMotion.transition}
            onSubmit={(e) => {
              e.preventDefault();
              void handleSubmit();
            }}
          >
            <button
              type="button"
              className="create-domain-modal__close"
              aria-label="Close"
              disabled={busy}
              onClick={onClose}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path
                  d="M6 6l12 12M18 6L6 18"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                />
              </svg>
            </button>
            <h3 id="create-domain-title" className="create-domain-modal__title">
              New domain
            </h3>
            <p className="create-domain-modal__lead">
              Define how this subject should be taught.
            </p>

            <label className="create-domain-modal__field">
              <span className="create-domain-modal__label">Domain name</span>
              <input
                ref={nameRef}
                className="create-domain-modal__input"
                value={name}
                disabled={busy}
                placeholder="e.g. Discrete Math"
                onChange={(e) => setName(e.target.value)}
              />
            </label>

            <label className="create-domain-modal__field">
              <span className="create-domain-modal__label">Subject scope</span>
              <textarea
                className="create-domain-modal__textarea"
                value={scope}
                disabled={busy}
                rows={3}
                placeholder="What this domain covers, and what it excludes"
                onChange={(e) => setScope(e.target.value)}
              />
            </label>

            <label className="create-domain-modal__field">
              <span className="create-domain-modal__label">Goal</span>
              <select
                className="create-domain-modal__select"
                value={goalPreset}
                disabled={busy}
                onChange={(e) => setGoalPreset(e.target.value)}
              >
                {GOAL_PRESETS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
              {goalPreset === 'custom' && (
                <input
                  className="create-domain-modal__input"
                  value={goalCustom}
                  disabled={busy}
                  placeholder="Describe the goal in your own words"
                  onChange={(e) => setGoalCustom(e.target.value)}
                  aria-label="Custom goal"
                />
              )}
            </label>

            <label className="create-domain-modal__field">
              <span className="create-domain-modal__label">Tutor style</span>
              <select
                className="create-domain-modal__select"
                value={stylePreset}
                disabled={busy}
                onChange={(e) => setStylePreset(e.target.value)}
              >
                {STYLE_PRESETS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
              {stylePreset === 'custom' && (
                <input
                  className="create-domain-modal__input"
                  value={styleCustom}
                  disabled={busy}
                  placeholder="Describe the tutoring tone"
                  onChange={(e) => setStyleCustom(e.target.value)}
                  aria-label="Custom tutor style"
                />
              )}
            </label>

            {error && <p className="create-domain-modal__error">{error}</p>}

            <div className="create-domain-modal__actions">
              <button type="button" className="btn btn--ghost" disabled={busy} onClick={onClose}>
                Cancel
              </button>
              <button type="submit" className="btn btn--primary" disabled={!canSubmit}>
                {busy ? 'Creating…' : 'Create domain'}
              </button>
            </div>
          </motion.form>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
