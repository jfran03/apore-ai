"use client";

import {
  motion,
  useReducedMotion,
  type HTMLMotionProps,
  type Variants,
} from "framer-motion";
import type { ElementType, ReactNode } from "react";
import {
  defaultTransition,
  defaultViewport,
  fadeIn,
  fadeUp,
  scaleIn,
  splitWords,
  staggerContainer,
  wordReveal,
  wordStagger,
  wordTransition,
  withTransition,
} from "@/lib/motion";

type MotionDivProps = HTMLMotionProps<"div"> & {
  delay?: number;
};

function useMotionTransition(delay = 0) {
  const reduceMotion = useReducedMotion();
  return withTransition(reduceMotion, { ...defaultTransition, delay });
}

export function FadeIn({
  children,
  className,
  delay = 0,
  ...props
}: MotionDivProps) {
  const transition = useMotionTransition(delay);

  return (
    <motion.div
      initial="hidden"
      whileInView="visible"
      viewport={defaultViewport}
      variants={fadeUp}
      transition={transition}
      className={className}
      {...props}
    >
      {children}
    </motion.div>
  );
}

export function FadeInScale({
  children,
  className,
  delay = 0,
  ...props
}: MotionDivProps) {
  const transition = useMotionTransition(delay);

  return (
    <motion.div
      initial="hidden"
      whileInView="visible"
      viewport={defaultViewport}
      variants={scaleIn}
      transition={transition}
      className={className}
      {...props}
    >
      {children}
    </motion.div>
  );
}

export function StaggerGroup({
  children,
  className,
  fast = false,
  ...props
}: MotionDivProps & { fast?: boolean }) {
  const reduceMotion = useReducedMotion();

  return (
    <motion.div
      initial="hidden"
      whileInView="visible"
      viewport={defaultViewport}
      variants={
        reduceMotion
          ? undefined
          : fast
            ? { hidden: {}, visible: { transition: { staggerChildren: 0.05 } } }
            : staggerContainer
      }
      className={className}
      {...props}
    >
      {children}
    </motion.div>
  );
}

export function StaggerItem({
  children,
  className,
  variants = fadeUp,
  ...props
}: MotionDivProps & { variants?: Variants }) {
  const reduceMotion = useReducedMotion();

  return (
    <motion.div
      variants={reduceMotion ? fadeIn : variants}
      transition={withTransition(reduceMotion)}
      className={className}
      {...props}
    >
      {children}
    </motion.div>
  );
}

export function HeroSequence({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  const reduceMotion = useReducedMotion();

  return (
    <motion.div
      initial="hidden"
      animate="visible"
      variants={reduceMotion ? undefined : staggerContainer}
      className={className}
    >
      {children}
    </motion.div>
  );
}

export function GlowPulse({
  className,
  children,
}: {
  className?: string;
  children?: ReactNode;
}) {
  const reduceMotion = useReducedMotion();

  if (reduceMotion) {
    return (
      <div className={className} aria-hidden>
        {children}
      </div>
    );
  }

  return (
    <motion.div
      className={className}
      aria-hidden
      animate={{
        opacity: [0.25, 0.45, 0.25],
        scale: [1, 1.06, 1],
      }}
      transition={{
        duration: 8,
        repeat: Infinity,
        ease: "easeInOut",
      }}
    >
      {children}
    </motion.div>
  );
}

type RevealWordsProps = {
  text: string;
  as?: ElementType;
  className?: string;
  /** Mount on page load (hero) or when scrolled into view */
  trigger?: "mount" | "view";
  /** Delay before the first word animates */
  delay?: number;
  /** Gap between each word */
  stagger?: number;
};

export function RevealWords({
  text,
  as: Component = "span",
  className = "",
  trigger = "view",
  delay = 0,
  stagger = 0.055,
}: RevealWordsProps) {
  const reduceMotion = useReducedMotion();
  const words = splitWords(text);

  if (reduceMotion) {
    return <Component className={className}>{text}</Component>;
  }

  const motionProps =
    trigger === "mount"
      ? { initial: "hidden" as const, animate: "visible" as const }
      : {
          initial: "hidden" as const,
          whileInView: "visible" as const,
          viewport: defaultViewport,
        };

  return (
    <Component className={className}>
      <motion.span
        {...motionProps}
        variants={wordStagger(stagger, delay)}
        className="inline-flex flex-wrap max-md:w-full max-md:justify-center"
      >
        {words.map((word, index) => (
          <motion.span
            key={`${word}-${index}`}
            variants={wordReveal}
            transition={wordTransition}
            className="mr-[0.28em] inline-block last:mr-0"
          >
            {word}
          </motion.span>
        ))}
      </motion.span>
    </Component>
  );
}
