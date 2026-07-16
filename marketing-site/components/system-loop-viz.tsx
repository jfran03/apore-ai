"use client";

import {
  AnimatePresence,
  motion,
  useInView,
  useReducedMotion,
} from "framer-motion";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { defaultTransition, instantTransition } from "@/lib/motion";

const STEP_MS = 2600;

export const LOOP_STEPS = [
  {
    label: "Learner uploads study content",
    shortLabel: "Upload",
    color: "#dfa88f",
    caption: "Notes, slides, and readings enter the system.",
  },
  {
    label: "LLM compiles a grounded wiki",
    shortLabel: "Wiki",
    color: "#9fbbe0",
    caption: "Sources become a linked knowledge graph — no hallucinated context.",
  },
  {
    label: "System generates a calibrated practice problem",
    shortLabel: "Problem",
    color: "#c0a8dd",
    caption: "Difficulty targets productive struggle, not guesswork.",
  },
  {
    label: "Learner attempts the problem",
    shortLabel: "Attempt",
    color: "#9fc9a2",
    caption: "Every attempt is signal, not just right or wrong.",
  },
  {
    label: "AI tutor provides Socratic guidance",
    shortLabel: "Socratic",
    color: "#c0a8dd",
    caption: "Hints cite your wiki — answers are never handed over.",
  },
  {
    label: "System captures learner signals",
    shortLabel: "Signals",
    color: "#9fc9a2",
    caption: "Time, hints, partial progress, and confidence feed the model.",
  },
  {
    label: "Reward model updates difficulty calibration",
    shortLabel: "Calibrate",
    color: "#c08532",
    caption: "The difficulty scalar shifts after every interaction.",
  },
  {
    label: "Future questions become more personalized",
    shortLabel: "Personalize",
    color: "#dfa88f",
    caption: "The loop closes — the next problem fits you better.",
  },
] as const;

function SceneShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-full min-h-[220px] items-center justify-center px-4 py-6">
      {children}
    </div>
  );
}

function UploadScene() {
  return (
    <SceneShell>
      <div className="flex w-full max-w-sm flex-col items-center gap-5">
        <motion.div
          className="w-36 rounded-[var(--radius-md)] border border-hairline bg-white p-4 shadow-none"
          animate={{ y: [0, -10, 0] }}
          transition={{ duration: 1.6, repeat: Infinity, ease: "easeInOut" }}
        >
          <div className="mb-3 h-1.5 w-10 rounded-full bg-accent/70" />
          <div className="space-y-2">
            <div className="h-1.5 w-full rounded-full bg-hairline" />
            <div className="h-1.5 w-4/5 rounded-full bg-hairline" />
            <div className="h-1.5 w-3/5 rounded-full bg-hairline" />
          </div>
          <p className="mt-3 font-mono text-[10px] text-muted">
            lecture-notes.pdf
          </p>
        </motion.div>
        <motion.div
          className="flex items-center gap-2 text-xs text-muted"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.2 }}
        >
          <span className="inline-block h-px w-8 bg-hairline-strong" />
          <span>Uploading to Apore</span>
          <span className="inline-block h-px w-8 bg-hairline-strong" />
        </motion.div>
        <div className="h-1.5 w-full max-w-xs overflow-hidden rounded-full bg-[#efeee8]">
          <motion.div
            className="h-full rounded-full bg-accent"
            initial={{ width: "0%" }}
            animate={{ width: "100%" }}
            transition={{ duration: 1.8, ease: "easeOut" }}
          />
        </div>
      </div>
    </SceneShell>
  );
}

function WikiScene() {
  const nodes = [
    { x: 50, y: 18, label: "Set A" },
    { x: 18, y: 58, label: "∩" },
    { x: 82, y: 58, label: "Set B" },
    { x: 50, y: 82, label: "Wiki" },
  ];

  return (
    <SceneShell>
      <div className="relative h-44 w-full max-w-sm">
        <svg
          className="absolute inset-0 h-full w-full"
          viewBox="0 0 100 100"
          aria-hidden
        >
          {[
            [0, 1],
            [0, 2],
            [1, 3],
            [2, 3],
          ].map(([from, to], index) => (
            <motion.line
              key={`${from}-${to}`}
              x1={nodes[from].x}
              y1={nodes[from].y}
              x2={nodes[to].x}
              y2={nodes[to].y}
              stroke="#cfcdc4"
              strokeWidth="1.5"
              initial={{ pathLength: 0, opacity: 0 }}
              animate={{ pathLength: 1, opacity: 1 }}
              transition={{ delay: 0.15 + index * 0.18, duration: 0.5 }}
            />
          ))}
        </svg>
        {nodes.map((node, index) => (
          <motion.div
            key={node.label}
            className="absolute flex -translate-x-1/2 -translate-y-1/2 flex-col items-center gap-1"
            style={{ left: `${node.x}%`, top: `${node.y}%` }}
            initial={{ opacity: 0, scale: 0.85 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: index * 0.12, duration: 0.35 }}
          >
            <div className="flex h-10 w-10 items-center justify-center rounded-full border border-hairline bg-white text-[10px] font-semibold text-ink">
              {node.label}
            </div>
          </motion.div>
        ))}
        <motion.p
          className="absolute bottom-0 left-0 right-0 text-center font-mono text-[10px] text-muted"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.8 }}
        >
          Grounded in your sources
        </motion.p>
      </div>
    </SceneShell>
  );
}

function ProblemScene() {
  return (
    <SceneShell>
      <div className="w-full max-w-sm space-y-5">
        <div className="rounded-[var(--radius-md)] border border-hairline bg-white p-4">
          <p className="font-mono text-xs leading-relaxed text-ink">
            If A = {"{1, 2, 3}"} and B = {"{2, 3, 4}"}, what is A ∩ B?
          </p>
        </div>
        <div>
          <div className="mb-2 flex justify-between font-mono text-[10px] text-muted">
            <span>Difficulty target</span>
            <motion.span
              key="difficulty-value"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
            >
              0.51
            </motion.span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-[#efeee8]">
            <motion.div
              className="h-full rounded-full bg-[#c0a8dd]"
              initial={{ width: "28%" }}
              animate={{ width: "51%" }}
              transition={{ duration: 1.2, ease: "easeOut" }}
            />
          </div>
        </div>
      </div>
    </SceneShell>
  );
}

function AttemptScene() {
  return (
    <SceneShell>
      <div className="w-full max-w-sm">
        <p className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-muted">
          Your answer
        </p>
        <div className="rounded-[var(--radius-md)] border border-hairline-strong bg-[#efeee8] px-4 py-3 font-mono text-sm text-ink">
          2, 3… maybe 4
          <motion.span
            className="ml-0.5 inline-block h-4 w-0.5 bg-accent"
            animate={{ opacity: [1, 0, 1] }}
            transition={{ duration: 0.9, repeat: Infinity }}
          />
        </div>
      </div>
    </SceneShell>
  );
}

function SocraticScene() {
  return (
    <SceneShell>
      <div className="flex w-full max-w-sm flex-col gap-3">
        <motion.div
          className="self-start rounded-[var(--radius-md)] border border-hairline bg-white px-3 py-2 text-xs text-body"
          initial={{ opacity: 0, x: -8 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.1 }}
        >
          Does 4 belong to set A?
        </motion.div>
        <motion.div
          className="self-end rounded-[var(--radius-md)] border border-hairline-strong bg-[#efeee8] px-3 py-2 text-xs text-ink"
          initial={{ opacity: 0, x: 8 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.45 }}
        >
          …checking the wiki
        </motion.div>
        <motion.p
          className="text-center text-[10px] text-muted"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.75 }}
        >
          Socratic — never the final answer
        </motion.p>
      </div>
    </SceneShell>
  );
}

function SignalsScene() {
  const signals = [
    { label: "42s", x: 0 },
    { label: "2 hints", x: 1 },
    { label: "partial", x: 2 },
  ];

  return (
    <SceneShell>
      <div className="relative w-full max-w-sm">
        <div className="mb-8 flex justify-center gap-3">
          {signals.map((signal, index) => (
            <motion.div
              key={signal.label}
              className="rounded-full border border-hairline bg-white px-3 py-1 font-mono text-[10px] text-ink"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.15 }}
            >
              {signal.label}
            </motion.div>
          ))}
        </div>
        {signals.map((signal, index) => (
          <motion.div
            key={`flow-${signal.label}`}
            className="absolute left-1/2 top-10 h-1.5 w-1.5 -translate-x-1/2 rounded-full bg-[#9fc9a2]"
            initial={{ opacity: 0, y: 0 }}
            animate={{ opacity: [0, 1, 0], y: 48 }}
            transition={{
              delay: 0.4 + index * 0.2,
              duration: 0.9,
              ease: "easeIn",
            }}
            style={{ marginLeft: (index - 1) * 28 }}
          />
        ))}
        <motion.div
          className="mx-auto flex h-16 w-40 items-center justify-center rounded-[var(--radius-md)] border border-dashed border-hairline-strong bg-white text-[10px] font-semibold uppercase tracking-wide text-muted"
          initial={{ opacity: 0, scale: 0.96 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.55 }}
        >
          Signal bundle
        </motion.div>
      </div>
    </SceneShell>
  );
}

function RewardScene() {
  return (
    <SceneShell>
      <div className="w-full max-w-md space-y-4">
        <div className="rounded-[var(--radius-md)] border border-hairline bg-white p-4">
          <div className="mb-3 flex items-center justify-between">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-muted">
              Reward model
            </p>
            <motion.span
              className="rounded-full bg-[#fafaf7] px-2 py-0.5 font-mono text-[10px] text-accent"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.9 }}
            >
              + productive struggle
            </motion.span>
          </div>

          <div className="relative h-20 rounded-[var(--radius-md)] bg-[#fafaf7] px-3 py-2">
            <div className="absolute inset-x-3 top-1/2 flex -translate-y-1/2 justify-between font-mono text-[9px] text-muted">
              <span>0.1</span>
              <span>0.9</span>
            </div>
            <div className="absolute inset-x-3 top-1/2 h-2 -translate-y-1/2 overflow-hidden rounded-full bg-[#efeee8]">
              <motion.div
                className="absolute top-0 h-full rounded-full bg-accent/25"
                initial={{ left: "44%", width: "0%" }}
                animate={{ left: "44%", width: "11%" }}
                transition={{ delay: 0.6, duration: 0.8, ease: "easeOut" }}
              />
              <motion.div
                className="absolute top-1/2 h-3 w-3 -translate-y-1/2 rounded-full border-2 border-white bg-accent"
                initial={{ left: "44%" }}
                animate={{ left: "55%" }}
                transition={{ delay: 0.5, duration: 1, ease: "easeInOut" }}
              />
            </div>
            <div className="absolute inset-x-3 bottom-2 flex justify-between font-mono text-[9px]">
              <span className="text-muted">before</span>
              <span className="text-accent">after</span>
            </div>
          </div>

          <div className="mt-3 grid grid-cols-3 gap-2 font-mono text-[10px]">
            {[
              { label: "Time", value: "42s" },
              { label: "Hints", value: "2" },
              { label: "Partial", value: "yes" },
            ].map((item, index) => (
              <motion.div
                key={item.label}
                className="rounded-[var(--radius-md)] border border-hairline bg-[#fafaf7] px-2 py-1.5 text-center"
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.1 }}
              >
                <span className="block text-muted">{item.label}</span>
                <span className="text-ink">{item.value}</span>
              </motion.div>
            ))}
          </div>
        </div>

        <motion.div
          className="flex items-center justify-between rounded-[var(--radius-md)] border border-hairline bg-white px-4 py-3 font-mono text-[11px]"
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.55 }}
        >
          <span className="text-muted">Difficulty calibration</span>
          <span className="text-accent">0.51 → 0.55</span>
        </motion.div>
      </div>
    </SceneShell>
  );
}

function PersonalizeScene() {
  return (
    <SceneShell>
      <div className="w-full max-w-lg space-y-4">
        <div className="flex items-stretch justify-center gap-3 md:gap-4">
          <motion.div
            className="flex w-[42%] flex-col rounded-[var(--radius-md)] border border-hairline bg-white p-3"
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 0.55, x: 0 }}
          >
            <p className="text-[10px] font-semibold uppercase tracking-wide text-muted">
              Generic
            </p>
            <p className="mt-2 font-mono text-[10px] leading-relaxed text-body">
              Define “subset.” Give one example.
            </p>
            <p className="mt-3 text-[9px] text-muted">Same for everyone</p>
          </motion.div>

          <motion.div
            className="flex flex-col items-center justify-center text-accent"
            animate={{ opacity: [0.5, 1, 0.5] }}
            transition={{ duration: 1.4, repeat: Infinity }}
            aria-hidden
          >
            →
          </motion.div>

          <motion.div
            className="flex w-[42%] flex-col rounded-[var(--radius-md)] border border-accent bg-[#fafaf7] p-3"
            initial={{ opacity: 0, x: 8, scale: 0.96 }}
            animate={{ opacity: 1, x: 0, scale: 1 }}
            transition={{ delay: 0.3 }}
          >
            <p className="text-[10px] font-semibold uppercase tracking-wide text-accent">
              For you
            </p>
            <p className="mt-2 font-mono text-[10px] leading-relaxed text-ink">
              A = {"{1,2,3}"}, B = {"{2,3,4}"} — find A ∩ B at your weak edge.
            </p>
            <div className="mt-3 flex items-center gap-2">
              <span className="rounded-full bg-[#c0a8dd] px-2 py-0.5 text-[9px] font-semibold text-ink">
                Set ops
              </span>
              <span className="font-mono text-[9px] text-accent">0.55</span>
            </div>
          </motion.div>
        </div>

        <motion.div
          className="flex items-center justify-center gap-2 text-[10px] text-muted"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.7 }}
        >
          <span className="inline-block h-px w-6 bg-hairline-strong" />
          <span>Loop closes — next session starts smarter</span>
          <span className="inline-block h-px w-6 bg-hairline-strong" />
        </motion.div>
      </div>
    </SceneShell>
  );
}

const SCENES = [
  UploadScene,
  WikiScene,
  ProblemScene,
  AttemptScene,
  SocraticScene,
  SignalsScene,
  RewardScene,
  PersonalizeScene,
];

export function SystemLoopViz() {
  const reduceMotion = useReducedMotion();
  const containerRef = useRef<HTMLDivElement>(null);
  const inView = useInView(containerRef, { once: false, margin: "-10% 0px" });
  const [activeStep, setActiveStep] = useState(0);

  useEffect(() => {
    if (!inView) return;

    if (reduceMotion) {
      setActiveStep(LOOP_STEPS.length - 1);
      return;
    }

    let step = 0;
    setActiveStep(0);

    const interval = setInterval(() => {
      step = (step + 1) % LOOP_STEPS.length;
      setActiveStep(step);
    }, STEP_MS);

    return () => clearInterval(interval);
  }, [inView, reduceMotion]);

  const transition = reduceMotion ? instantTransition : defaultTransition;
  const step = LOOP_STEPS[activeStep];
  const Scene = SCENES[activeStep];

  return (
    <div ref={containerRef} className="mt-12">
      <div className="overflow-hidden rounded-[var(--radius-lg)] border border-hairline bg-white">
        <div className="border-b border-hairline px-5 py-4 md:px-6">
          <div className="flex flex-wrap items-center gap-3">
            <span
              className="font-mono text-xs"
              style={{ color: step.color }}
            >
              {String(activeStep + 1).padStart(2, "0")}
            </span>
            <p className="text-sm font-medium text-ink">{step.label}</p>
          </div>
          <AnimatePresence mode="wait">
            <motion.p
              key={step.caption}
              className="mt-2 max-w-2xl text-sm text-body"
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ ...transition, duration: 0.25 }}
            >
              {step.caption}
            </motion.p>
          </AnimatePresence>
        </div>

        <div className="relative bg-[#fafaf7]">
          <div className="invisible pointer-events-none select-none" aria-hidden>
            <PersonalizeScene />
          </div>
          <div className="absolute inset-0">
            <AnimatePresence mode="wait">
              <motion.div
                key={activeStep}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ ...transition, duration: 0.35 }}
                className="h-full"
              >
                <Scene />
              </motion.div>
            </AnimatePresence>
          </div>
        </div>

        <div className="border-t border-hairline px-4 py-4 md:px-6">
          <div
            className="flex gap-1.5 overflow-x-auto pb-1"
            role="tablist"
            aria-label="System loop stages"
          >
            {LOOP_STEPS.map((item, index) => {
              const isActive = index === activeStep;
              return (
                <motion.div
                  key={item.label}
                  role="tab"
                  aria-selected={isActive}
                  className={`min-w-[72px] flex-1 rounded-[var(--radius-md)] border px-2 py-2 text-center transition-colors ${
                    isActive
                      ? "border-hairline-strong bg-[#fafaf7]"
                      : "border-transparent bg-transparent opacity-50"
                  }`}
                  animate={
                    isActive
                      ? { opacity: 1, scale: 1 }
                      : { opacity: 0.5, scale: 0.98 }
                  }
                  transition={transition}
                >
                  <span
                    className="block font-mono text-[10px]"
                    style={{ color: isActive ? item.color : undefined }}
                  >
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <span className="mt-1 text-[10px] leading-snug text-body">
                    {item.shortLabel}
                  </span>
                </motion.div>
              );
            })}
          </div>
          <div className="mt-3 h-1 overflow-hidden rounded-full bg-[#efeee8]">
            <motion.div
              className="h-full rounded-full bg-accent"
              animate={{
                width: `${((activeStep + 1) / LOOP_STEPS.length) * 100}%`,
              }}
              transition={{ ...transition, duration: 0.45 }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
