import type { Transition, Variants } from "framer-motion";

export const easeOut = [0.22, 1, 0.36, 1] as const;

export const defaultTransition: Transition = {
  duration: 0.55,
  ease: easeOut,
};

export const instantTransition: Transition = {
  duration: 0,
};

export const defaultViewport = {
  once: true,
  margin: "-8% 0px",
} as const;

export const fadeUp: Variants = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0 },
};

export const fadeIn: Variants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1 },
};

export const scaleIn: Variants = {
  hidden: { opacity: 0, scale: 0.96 },
  visible: { opacity: 1, scale: 1 },
};

export const slideDown: Variants = {
  hidden: { opacity: 0, y: -12 },
  visible: { opacity: 1, y: 0 },
};

export const staggerContainer: Variants = {
  hidden: {},
  visible: {
    transition: {
      staggerChildren: 0.08,
      delayChildren: 0.04,
    },
  },
};

export const staggerContainerFast: Variants = {
  hidden: {},
  visible: {
    transition: {
      staggerChildren: 0.05,
      delayChildren: 0.02,
    },
  },
};

export const wordReveal: Variants = {
  hidden: { opacity: 0, y: "0.35em", filter: "blur(8px)" },
  visible: {
    opacity: 1,
    y: 0,
    filter: "blur(0px)",
  },
};

export const wordStagger = (stagger = 0.055, delay = 0): Variants => ({
  hidden: {},
  visible: {
    transition: {
      staggerChildren: stagger,
      delayChildren: delay,
    },
  },
});

export function splitWords(text: string): string[] {
  return text.trim().split(/\s+/).filter(Boolean);
}

export function withTransition(
  reduceMotion: boolean | null,
  transition: Transition = defaultTransition,
): Transition {
  return reduceMotion ? instantTransition : transition;
}

export const wordTransition: Transition = {
  duration: 0.45,
  ease: easeOut,
};
