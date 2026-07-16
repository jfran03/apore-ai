import { RevealWords } from "./motion";
import { SystemLoopViz } from "./system-loop-viz";

export function SystemLoop() {
  return (
    <section
      id="how-it-works"
      className="border-t border-hairline bg-canvas px-6 py-24 md:py-32"
    >
      <div className="mx-auto max-w-6xl">
        <RevealWords
          as="p"
          text="How it works"
          className="section-label mb-4 text-muted"
        />
        <RevealWords
          as="h2"
          text="How Apore learns you."
          className="display text-3xl text-ink md:text-4xl"
          delay={0.1}
        />
        <RevealWords
          as="p"
          text="A closed loop — grounded content in, calibrated difficulty out. Every session makes the next one fit you better."
          className="mt-4 max-w-2xl text-base text-body"
          delay={0.25}
          stagger={0.028}
        />

        <SystemLoopViz />
      </div>
    </section>
  );
}
