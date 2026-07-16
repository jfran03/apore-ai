import { RevealWords } from "./motion";

const features = [
  {
    title: "Grounded Wiki",
    body: "Upload study material — HTML, plain text, images — and Apore compiles a wiki your tutor actually uses. No out-of-context answers.",
  },
  {
    title: "Socratic Tutor",
    body: "Guidance follows the Dean–Teacher–Student pattern: constraints against direct answers, hints that cite your sources, dialogue that builds understanding.",
  },
  {
    title: "Adaptive Calibration",
    body: "A difficulty scalar (0.1–0.9) updated after every question from explicit ratings and implicit signals — concept depth and question type tracked separately.",
  },
];

export function PlatformFeatures() {
  return (
    <section id="platform" className="bg-canvas px-6 py-24 md:py-32">
      <div className="mx-auto max-w-6xl">
        <RevealWords
          as="p"
          text="The platform"
          className="section-label mb-4 text-muted"
        />
        <RevealWords
          as="h2"
          text="Built for calibration."
          className="display text-3xl text-ink md:text-4xl"
          delay={0.1}
        />
        <RevealWords
          as="p"
          text="Intelligence is not bolted on — it is foundational. Apore learns from how you struggle, not just whether you got the answer."
          className="mt-4 max-w-2xl text-base text-body"
          delay={0.3}
          stagger={0.028}
        />

        <div className="mt-12 grid gap-6 md:grid-cols-3">
          {features.map((feature, index) => (
            <article
              key={feature.title}
              className="rounded-[var(--radius-lg)] border border-hairline bg-white p-6 transition hover:border-hairline-strong"
            >
              <RevealWords
                as="h3"
                text={feature.title}
                className="text-lg font-semibold text-ink"
                delay={index * 0.08}
              />
              <RevealWords
                as="p"
                text={feature.body}
                className="mt-3 text-sm leading-relaxed text-body"
                delay={index * 0.08 + 0.1}
                stagger={0.03}
              />
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
