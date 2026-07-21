import type { Transition, Variants } from 'framer-motion';

/** Strong ease-out (ease-out-quart). Starts fast — feels responsive. */
export const EASE_OUT = [0.23, 1, 0.32, 1] as const;

export const DURATION = {
  enter: 0.18,
  exit: 0.12,
  micro: 0.12,
  /** Slightly longer enter for chat / list items */
  soft: 0.2,
} as const;

export function transition(
  duration: number,
  reduceMotion?: boolean | null,
): Transition {
  if (reduceMotion) return { duration: 0 };
  return { duration, ease: EASE_OUT };
}

/** Opacity + small upward tween for page/content reveals. */
export function fadeUp(
  y = 6,
  reduceMotion?: boolean | null,
): {
  initial: false | { opacity: number; y: number };
  animate: { opacity: number; y: number };
  exit: { opacity: number; y: number };
  transition: Transition;
} {
  if (reduceMotion) {
    return {
      initial: false,
      animate: { opacity: 1, y: 0 },
      exit: { opacity: 0, y: 0 },
      transition: { duration: 0 },
    };
  }
  return {
    initial: { opacity: 0, y },
    animate: { opacity: 1, y: 0 },
    exit: { opacity: 0, y: -y * 0.5 },
    transition: transition(DURATION.enter),
  };
}

/** Opacity-only fade (no transform). */
export function fade(reduceMotion?: boolean | null): {
  initial: false | { opacity: number };
  animate: { opacity: number };
  exit: { opacity: number };
  transition: Transition;
} {
  if (reduceMotion) {
    return {
      initial: false,
      animate: { opacity: 1 },
      exit: { opacity: 0 },
      transition: { duration: 0 },
    };
  }
  return {
    initial: { opacity: 0 },
    animate: { opacity: 1 },
    exit: { opacity: 0 },
    transition: transition(DURATION.enter),
  };
}

/** Backdrop / scrim opacity. */
export const overlayVariants: Variants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1 },
};

export function overlayTransition(reduceMotion?: boolean | null): Transition {
  return transition(DURATION.enter, reduceMotion);
}

/**
 * Modal / popover panel: scale from 0.97 + fade.
 * Never scale from 0 — nothing in the real world appears from nothing.
 */
export function panel(
  reduceMotion?: boolean | null,
): {
  initial: false | { opacity: number; scale: number; y?: number };
  animate: { opacity: number; scale: number; y?: number };
  exit: { opacity: number; scale: number; y?: number };
  transition: Transition;
} {
  if (reduceMotion) {
    return {
      initial: false,
      animate: { opacity: 1, scale: 1 },
      exit: { opacity: 0, scale: 1 },
      transition: { duration: 0 },
    };
  }
  return {
    initial: { opacity: 0, scale: 0.97, y: 4 },
    animate: { opacity: 1, scale: 1, y: 0 },
    exit: { opacity: 0, scale: 0.97, y: 4 },
    transition: transition(DURATION.enter),
  };
}

/** Popover anchored under a trigger — slight y drift. */
export function popover(
  reduceMotion?: boolean | null,
): {
  initial: false | { opacity: number; scale: number; y: number };
  animate: { opacity: number; scale: number; y: number };
  exit: { opacity: number; scale: number; y: number };
  transition: Transition;
} {
  if (reduceMotion) {
    return {
      initial: false,
      animate: { opacity: 1, scale: 1, y: 0 },
      exit: { opacity: 0, scale: 1, y: 0 },
      transition: { duration: 0 },
    };
  }
  return {
    initial: { opacity: 0, scale: 0.97, y: -4 },
    animate: { opacity: 1, scale: 1, y: 0 },
    exit: { opacity: 0, scale: 0.97, y: -4 },
    transition: transition(DURATION.exit),
  };
}

/** Route outlet: enter 180ms, exit 120ms. */
export function routeFade(reduceMotion?: boolean | null) {
  if (reduceMotion) {
    return {
      initial: false as const,
      animate: { opacity: 1, y: 0 },
      exit: { opacity: 0, y: 0 },
      transition: { duration: 0 },
    };
  }
  return {
    initial: { opacity: 0, y: 6 },
    animate: { opacity: 1, y: 0 },
    exit: { opacity: 0, y: -4 },
    transition: { duration: DURATION.enter, ease: EASE_OUT },
    exitTransition: { duration: DURATION.exit, ease: EASE_OUT },
  };
}
