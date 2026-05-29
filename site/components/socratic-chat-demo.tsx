"use client";

import {
  AnimatePresence,
  motion,
  useInView,
  useReducedMotion,
} from "framer-motion";
import { useEffect, useRef, useState } from "react";
import { defaultTransition, instantTransition } from "@/lib/motion";

type Message = {
  from: "apore" | "you";
  text: string;
};

const MESSAGES: Message[] = [
  { from: "apore", text: "What elements appear in both sets?" },
  { from: "you", text: "I think 2 and 3? Maybe also 4…" },
  {
    from: "apore",
    text: "Check whether 4 belongs to set A. What does the wiki say about intersection?",
  },
];

function MessageBubble({
  message,
  className = "",
}: {
  message: Message;
  className?: string;
}) {
  const isYou = message.from === "you";

  return (
    <div
      className={`flex flex-col gap-1.5 ${
        isYou ? "items-end" : "items-start"
      } ${className}`}
    >
      <span className="px-1 text-[10px] font-semibold uppercase tracking-wide text-muted">
        {isYou ? "You" : "Apore"}
      </span>
      <div
        className={`max-w-[92%] rounded-[var(--radius-md)] border px-4 py-3 text-sm leading-relaxed ${
          isYou
            ? "border-hairline-strong bg-[#efeee8] text-ink"
            : "border-hairline bg-white text-body"
        }`}
      >
        {message.text}
      </div>
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="flex gap-1 py-0.5" aria-hidden>
      {[0, 1, 2].map((index) => (
        <motion.span
          key={index}
          className="h-1.5 w-1.5 rounded-full bg-muted"
          animate={{ opacity: [0.35, 1, 0.35] }}
          transition={{
            duration: 0.9,
            repeat: Infinity,
            delay: index * 0.15,
          }}
        />
      ))}
    </div>
  );
}

export function SocraticChatDemo() {
  const reduceMotion = useReducedMotion();
  const containerRef = useRef<HTMLDivElement>(null);
  const inView = useInView(containerRef, { once: true, margin: "-8% 0px" });
  const [visibleCount, setVisibleCount] = useState(
    reduceMotion ? MESSAGES.length : 0,
  );
  const [typing, setTyping] = useState(false);

  useEffect(() => {
    if (reduceMotion) {
      setVisibleCount(MESSAGES.length);
      setTyping(false);
      return;
    }

    if (!inView) return;

    const timeouts: ReturnType<typeof setTimeout>[] = [];
    const schedule = (fn: () => void, delayMs: number) => {
      timeouts.push(setTimeout(fn, delayMs));
    };

    setVisibleCount(0);
    setTyping(false);

    schedule(() => setVisibleCount(1), 350);
    schedule(() => setVisibleCount(2), 1900);
    schedule(() => setTyping(true), 2700);
    schedule(() => {
      setTyping(false);
      setVisibleCount(3);
    }, 3600);

    return () => {
      for (const timeout of timeouts) clearTimeout(timeout);
    };
  }, [inView, reduceMotion]);

  const transition = reduceMotion ? instantTransition : defaultTransition;

  return (
    <div
      ref={containerRef}
      className="relative mt-4"
      aria-live="polite"
      aria-label="Sample Socratic tutoring conversation"
    >
      <div className="invisible pointer-events-none select-none" aria-hidden>
        <div className="flex flex-col gap-3">
          {MESSAGES.map((message, index) => (
            <MessageBubble key={index} message={message} />
          ))}
        </div>
      </div>

      <div className="absolute inset-0 flex flex-col gap-3">
        <AnimatePresence initial={false}>
          {MESSAGES.slice(0, visibleCount).map((message, index) => (
            <motion.div
              key={`${message.from}-${index}`}
              initial={{ opacity: 0, y: 12, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              transition={{ ...transition, duration: 0.4 }}
            >
              <MessageBubble message={message} />
            </motion.div>
          ))}
        </AnimatePresence>

        <AnimatePresence>
          {typing && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ ...transition, duration: 0.25 }}
              className="flex flex-col items-start gap-1.5"
            >
              <span className="px-1 text-[10px] font-semibold uppercase tracking-wide text-muted">
                Apore
              </span>
              <div className="rounded-[var(--radius-md)] border border-hairline bg-white px-4 py-3">
                <TypingIndicator />
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
