import { RevealWords } from "./motion";

export function ResearchBand() {
  return (
    <section
      id="research"
      className="border-t border-hairline bg-canvas px-6 py-24 md:py-32"
    >
      <div className="mx-auto max-w-4xl text-center">
        <RevealWords
          as="p"
          text="Research"
          className="section-label mb-4 text-muted"
        />
        <RevealWords
          as="h2"
          text="Research-backed, honestly scoped."
          className="display text-3xl text-ink md:text-4xl"
          delay={0.1}
        />
        <RevealWords
          as="p"
          text="Apore is a student-driven applied research project under SAIT. Existing work has explored Socratic LLM tutoring, adaptive educational systems, and retrieval-grounded learning independently — Apore combines these with reinforcement-style calibration driven by learner interaction signals."
          className="mx-auto mt-6 max-w-3xl text-base leading-relaxed text-body"
          delay={0.35}
          stagger={0.028}
        />

        <div className="mt-10 flex flex-col items-center justify-center">
          <a
            href="https://github.com/jfran03/apore-lite"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex h-11 items-center text-sm font-medium text-ink underline-offset-4 hover:underline"
          >
            Explore apore-lite on GitHub
          </a>
        </div>
      </div>
    </section>
  );
}
