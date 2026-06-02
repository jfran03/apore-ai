import { RevealWords } from "./motion";
import { SignalContrastCards } from "./signal-contrast";

export function ProblemBand() {
  return (
    <section className="border-t border-hairline bg-canvas px-6 py-24 md:py-32">
      <div className="mx-auto grid max-w-6xl gap-12 lg:grid-cols-2 lg:items-start">
        <div>
          <RevealWords
            as="p"
            text="The gap"
            className="section-label mb-4 text-muted"
          />
          <RevealWords
            as="h2"
            text="Beyond right and wrong."
            className="display text-3xl text-ink md:text-4xl"
            delay={0.1}
          />
          <RevealWords
            as="p"
            text="Limited research explores using explicit learner difficulty feedback and implicit Socratic interaction signals to optimize adaptive LLM-generated practice problems. Apore is built to close that gap."
            className="mt-6 max-w-xl text-base leading-relaxed text-body"
            delay={0.35}
            stagger={0.028}
          />
        </div>

        <SignalContrastCards />
      </div>
    </section>
  );
}
