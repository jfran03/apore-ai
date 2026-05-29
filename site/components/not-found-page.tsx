"use client";

import Image from "next/image";
import Link from "next/link";
import { motion, useReducedMotion } from "framer-motion";
import { GlowPulse, HeroSequence, RevealWords, StaggerItem } from "./motion";
import { defaultTransition, instantTransition } from "@/lib/motion";

const tutorLines = [
  "Interesting hypothesis. Where did you get that URL from?",
  "Let's work backwards — what were you actually trying to find?",
  "That's not in the syllabus. Or anywhere else, honestly.",
];

export function NotFoundPage() {
  const reduceMotion = useReducedMotion();

  return (
    <section className="relative flex min-h-[calc(100dvh-4rem)] flex-col justify-center overflow-hidden bg-dark-bg px-6 py-16">
      <GlowPulse className="pointer-events-none absolute inset-0 flex items-center justify-center">
        <Image
          src="/logo-glow.png"
          alt=""
          width={520}
          height={520}
          className="max-w-[60vw] opacity-25 blur-2xl"
          aria-hidden
        />
      </GlowPulse>

      <HeroSequence className="relative mx-auto flex w-full max-w-2xl flex-col items-center text-center">
        <StaggerItem>
          <p className="section-label text-dark-muted">Error 404</p>
        </StaggerItem>

        <RevealWords
          as="h1"
          text="Wrong turn. Good instinct to ask."
          className="display mt-4 max-w-xl text-3xl text-dark-ink md:text-5xl"
          trigger="mount"
          delay={0.15}
        />

        <StaggerItem className="mt-6 max-w-lg">
          <p className="text-base leading-relaxed text-dark-muted md:text-lg">
            This page doesn&apos;t exist — which is fine. Productive struggle
            starts with admitting you&apos;re lost. You&apos;re already ahead of
            most people who mash refresh and hope.
          </p>
        </StaggerItem>

        <StaggerItem className="mt-10 w-full max-w-md">
          <div
            className="rounded-[var(--radius-lg)] border border-white/10 bg-white/[0.03] p-5 text-left backdrop-blur-sm"
            aria-label="Apore tutor response"
          >
            <p className="text-[10px] font-semibold uppercase tracking-wide text-dark-muted">
              Apore
            </p>
            <div className="mt-3 space-y-3">
              {tutorLines.map((line, index) => (
                <motion.div
                  key={line}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={
                    reduceMotion
                      ? instantTransition
                      : { ...defaultTransition, delay: 0.5 + index * 0.35 }
                  }
                  className="rounded-[var(--radius-md)] border border-white/10 bg-white/[0.04] px-4 py-3 text-sm leading-relaxed text-dark-ink"
                >
                  {line}
                </motion.div>
              ))}
            </div>
          </div>
        </StaggerItem>

        <StaggerItem className="mt-10 flex flex-col items-center gap-4 sm:flex-row">
          <Link
            href="/"
            className="inline-flex h-11 items-center rounded-[var(--radius-md)] bg-accent px-6 text-sm font-medium text-white transition hover:bg-accent-active"
          >
            Back to somewhere real
          </Link>
          <Link
            href="/manifesto"
            className="inline-flex h-11 items-center rounded-[var(--radius-md)] border border-white/15 px-6 text-sm font-medium text-dark-ink transition hover:border-white/30 hover:bg-white/5"
          >
            Read the manifesto instead
          </Link>
        </StaggerItem>

        <StaggerItem className="mt-8">
          <p className="font-mono text-xs text-dark-muted/80">
            /this-page-was-never-on-the-rubric
          </p>
        </StaggerItem>
      </HeroSequence>
    </section>
  );
}
