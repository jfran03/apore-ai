"use client";

import { motion, useInView, useReducedMotion } from "framer-motion";
import { useRef } from "react";
import { defaultTransition, instantTransition } from "@/lib/motion";

const contrasts = [
  {
    title: "Correctness-only",
    badge: "Status quo",
    tone: "muted" as const,
    items: [
      "Binary right/wrong scoring",
      "Static difficulty ladders",
      "Completion as proxy for learning",
    ],
  },
  {
    title: "Apore signals",
    badge: "Richer signal",
    tone: "accent" as const,
    items: [
      "Self-rated difficulty after each problem",
      "Hint count and turns to resolution",
      "Hedging language and dialogue patterns",
    ],
  },
];

function BinaryGauge() {
  const reduceMotion = useReducedMotion();

  return (
    <div
      className="flex items-center gap-2 rounded-[var(--radius-md)] border border-hairline bg-[#fafaf7] px-3 py-2"
      aria-hidden
    >
      {["0", "1"].map((bit, index) => (
        <motion.span
          key={bit}
          className={`flex h-8 flex-1 items-center justify-center rounded font-mono text-xs ${
            index === 0
              ? "bg-hairline text-muted"
              : "border border-hairline bg-white text-body"
          }`}
          animate={
            reduceMotion
              ? { opacity: 1 }
              : { opacity: index === 0 ? [1, 0.45, 1] : [0.45, 1, 0.45] }
          }
          transition={
            reduceMotion
              ? instantTransition
              : { duration: 2.4, repeat: Infinity, ease: "easeInOut" }
          }
        >
          {bit}
        </motion.span>
      ))}
      <span className="font-mono text-[10px] text-muted">only</span>
    </div>
  );
}

function SignalGauge() {
  const reduceMotion = useReducedMotion();
  const bars = [
    { label: "Difficulty", color: "#c08532", width: "68%" },
    { label: "Hints", color: "#9fbbe0", width: "42%" },
    { label: "Dialogue", color: "#c0a8dd", width: "81%" },
  ];

  return (
    <div
      className="space-y-2 rounded-[var(--radius-md)] border border-accent/30 bg-white px-3 py-2"
      aria-hidden
    >
      {bars.map((bar, index) => (
        <div key={bar.label} className="space-y-1">
          <div className="flex justify-between font-mono text-[9px] text-muted">
            <span>{bar.label}</span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-[#efeee8]">
            <motion.div
              className="h-full rounded-full"
              style={{ backgroundColor: bar.color }}
              initial={{ width: reduceMotion ? bar.width : "0%" }}
              animate={{ width: bar.width }}
              transition={
                reduceMotion
                  ? instantTransition
                  : { ...defaultTransition, delay: 0.15 + index * 0.12, duration: 0.7 }
              }
            />
          </div>
        </div>
      ))}
    </div>
  );
}

export function SignalContrastCards() {
  const reduceMotion = useReducedMotion();
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-10% 0px" });
  const transition = reduceMotion ? instantTransition : defaultTransition;

  return (
    <div ref={ref} className="grid items-stretch gap-4 sm:grid-cols-2">
      {contrasts.map((column, columnIndex) => {
        const isApore = column.tone === "accent";

        return (
          <motion.div
            key={column.title}
            initial={{ opacity: 0, y: 12 }}
            animate={inView ? { opacity: 1, y: 0 } : { opacity: 0, y: 12 }}
            transition={{ ...transition, delay: columnIndex * 0.1 }}
            className={`relative flex min-h-[320px] flex-col rounded-[var(--radius-lg)] border p-5 sm:p-6 ${
              isApore
                ? "border-accent bg-[#fafaf7] shadow-[0_0_0_1px_rgba(192,133,50,0.08)]"
                : "border-hairline bg-white opacity-90"
            }`}
          >
            {isApore && (
              <motion.div
                className="pointer-events-none absolute inset-0 rounded-[var(--radius-lg)] ring-1 ring-accent/20"
                animate={
                  reduceMotion
                    ? { opacity: 1 }
                    : { opacity: [0.35, 0.7, 0.35] }
                }
                transition={
                  reduceMotion
                    ? instantTransition
                    : { duration: 2.8, repeat: Infinity, ease: "easeInOut" }
                }
              />
            )}

            <div className="relative flex flex-1 flex-col">
              <div className="space-y-2">
                <span
                  className={`inline-flex w-fit rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
                    isApore
                      ? "bg-accent text-white"
                      : "border border-hairline bg-[#fafaf7] text-muted"
                  }`}
                >
                  {column.badge}
                </span>
                <h3
                  className={`text-sm font-semibold leading-snug ${
                    isApore ? "text-ink" : "text-body"
                  }`}
                >
                  {column.title}
                </h3>
              </div>

              <div className="mt-4">
                {isApore ? <SignalGauge /> : <BinaryGauge />}
              </div>

              <ul className="mt-4 space-y-3 text-sm">
                {column.items.map((item, itemIndex) => (
                  <motion.li
                    key={item}
                    className="flex gap-2.5"
                    initial={{ opacity: 0, x: isApore ? 6 : 0 }}
                    animate={
                      inView
                        ? { opacity: isApore ? 1 : 0.72, x: 0 }
                        : { opacity: 0, x: isApore ? 6 : 0 }
                    }
                    transition={{
                      ...transition,
                      delay: 0.2 + columnIndex * 0.08 + itemIndex * 0.1,
                    }}
                  >
                    <span
                      aria-hidden
                      className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[10px] font-bold ${
                        isApore
                          ? "bg-accent/15 text-accent"
                          : "bg-hairline text-muted"
                      }`}
                    >
                      {isApore ? "✓" : "×"}
                    </span>
                    <span className={isApore ? "text-ink" : "text-muted"}>
                      {item}
                    </span>
                  </motion.li>
                ))}
              </ul>
            </div>
          </motion.div>
        );
      })}
    </div>
  );
}
