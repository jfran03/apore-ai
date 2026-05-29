"use client";

import Image from "next/image";
import { Logo } from "./logo";
import { WaitlistForm } from "./waitlist-form";
import { GlowPulse, HeroSequence, RevealWords, StaggerItem } from "./motion";

export function Hero() {
  return (
    <section
      id="hero"
      className="relative flex min-h-[calc(100dvh-4rem)] flex-col justify-center overflow-hidden bg-dark-bg px-6 py-12"
    >
      <GlowPulse className="pointer-events-none absolute inset-0 flex items-center justify-center">
        <Image
          src="/logo-glow.png"
          alt=""
          width={640}
          height={640}
          className="max-w-[70vw] opacity-40 blur-2xl"
          aria-hidden
        />
      </GlowPulse>

      <HeroSequence className="relative mx-auto flex max-w-6xl flex-col items-center text-center">
        <StaggerItem>
          <Logo size={140} variant="dark" className="mb-8" />
        </StaggerItem>

        <RevealWords
          as="p"
          text="AI-powered adaptive tutoring"
          className="section-label mb-6 text-dark-muted"
          trigger="mount"
          delay={0.2}
        />

        <RevealWords
          as="h1"
          text="Learning, Recalibrated"
          className="display max-w-4xl text-4xl text-dark-ink md:text-6xl lg:text-7xl"
          trigger="mount"
          delay={0.45}
        />

        <RevealWords
          as="p"
          text="Struggle is where learning starts"
          className="mt-6 max-w-2xl text-lg leading-relaxed text-dark-muted"
          trigger="mount"
          delay={0.85}
          stagger={0.03}
        />

        <StaggerItem className="mt-10 w-full">
          <div id="waitlist" className="scroll-mt-24">
            <WaitlistForm source="hero" variant="dark" />
          </div>
        </StaggerItem>

        <StaggerItem>
          <a
            href="/manifesto"
            className="mt-8 inline-flex h-11 items-center text-sm font-medium text-dark-ink underline-offset-4 hover:underline"
          >
            Read our manifesto
          </a>
        </StaggerItem>
      </HeroSequence>
    </section>
  );
}
