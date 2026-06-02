"use client";

import { motion, useReducedMotion } from "framer-motion";
import { FadeInScale, RevealWords, StaggerGroup, StaggerItem } from "./motion";
import { SocraticChatDemo } from "./socratic-chat-demo";
import { defaultTransition, defaultViewport, instantTransition } from "@/lib/motion";

export function ProductMockup() {
  const reduceMotion = useReducedMotion();

  return (
    <section className="bg-canvas px-6 py-24 md:py-32">
      <div className="mx-auto max-w-6xl">
        <RevealWords
          as="p"
          text="Operator experience"
          className="section-label mb-4 text-muted"
        />
        <RevealWords
          as="h2"
          text="Designed for clarity."
          className="display text-3xl text-ink md:text-4xl"
          delay={0.1}
        />
        <RevealWords
          as="p"
          text="The interface surfaces exactly what you need — the question, the dialogue, and where you sit on the difficulty curve."
          className="mt-4 max-w-2xl text-base text-body"
          delay={0.3}
          stagger={0.028}
        />

        <FadeInScale className="mt-12">
          <div className="overflow-hidden rounded-[var(--radius-lg)] border border-hairline bg-white">
            <div className="grid md:grid-cols-2">
              <div className="border-b border-hairline p-6 md:border-b-0 md:border-r">
                <RevealWords
                  as="p"
                  text="Practice"
                  className="section-label text-muted"
                />
                <RevealWords
                  as="p"
                  text={'If A = {1, 2, 3} and B = {2, 3, 4}, what is A ∩ B?'}
                  className="mt-4 font-mono text-sm leading-relaxed text-ink"
                  delay={0.08}
                  stagger={0.04}
                />
                <div className="mt-6 h-2 rounded-full bg-[#efeee8]">
                  <motion.div
                    className="h-2 rounded-full bg-accent"
                    initial={{ width: reduceMotion ? "51%" : "0%" }}
                    whileInView={{ width: "51%" }}
                    viewport={defaultViewport}
                    transition={
                      reduceMotion
                        ? instantTransition
                        : { ...defaultTransition, delay: 0.2, duration: 0.8 }
                    }
                  />
                </div>
                <RevealWords
                  as="p"
                  text="Difficulty: 0.51"
                  className="mt-2 font-mono text-xs text-muted"
                  delay={0.15}
                />
              </div>

              <div className="bg-[#fafaf7] p-6">
                <RevealWords
                  as="p"
                  text="Socratic tutor"
                  className="section-label text-muted"
                />
                <SocraticChatDemo />
              </div>
            </div>

            <StaggerGroup
              fast
              className="flex flex-wrap gap-2 border-t border-hairline px-6 py-4"
            >
              {[
                { label: "Recall", className: "bg-[#dfa88f] text-ink" },
                { label: "Apply", className: "bg-[#9fbbe0] text-ink" },
                { label: "Synthesis", className: "bg-[#c0a8dd] text-ink" },
                { label: "Calibrating", className: "bg-accent text-white" },
              ].map((tag) => (
                <StaggerItem key={tag.label}>
                  <span
                    className={`inline-block rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-wide ${tag.className}`}
                  >
                    {tag.label}
                  </span>
                </StaggerItem>
              ))}
            </StaggerGroup>
          </div>
        </FadeInScale>
      </div>
    </section>
  );
}
