import { RevealWords } from "./motion";

const audiences = [
  {
    label: "Students",
    title: "Challenge that meets you",
    body: "Practice problems calibrated to your ability — hard enough to grow, not so hard you disengage.",
  },
  {
    label: "Educators",
    title: "Grounded in your materials",
    body: "Upload course content and get a tutor that teaches from your sources, not the open internet.",
  },
  {
    label: "Researchers",
    title: "Interpretable by design",
    body: "Markdown-first architecture where difficulty state, signals, and protocols are readable — not buried in weights.",
  },
];

export function AudienceGrid() {
  return (
    <section className="bg-canvas px-6 py-24 md:py-32">
      <div className="mx-auto max-w-6xl">
        <RevealWords
          as="p"
          text="Who it's for"
          className="section-label mb-4 text-muted"
        />
        <RevealWords
          as="h2"
          text="Built for learners who think deeply"
          className="display max-w-2xl text-3xl text-ink md:text-4xl"
          delay={0.1}
        />

        <div className="mt-12 grid gap-6 md:grid-cols-3">
          {audiences.map((item, index) => (
            <article
              key={item.label}
              className="rounded-[var(--radius-lg)] border border-hairline bg-white p-6 transition hover:border-hairline-strong"
            >
              <RevealWords
                as="p"
                text={item.label}
                className="section-label mb-4 text-muted"
                delay={index * 0.08}
              />
              <RevealWords
                as="h3"
                text={item.title}
                className="text-lg font-semibold text-ink"
                delay={index * 0.08 + 0.06}
              />
              <RevealWords
                as="p"
                text={item.body}
                className="mt-3 text-sm leading-relaxed text-body"
                delay={index * 0.08 + 0.14}
                stagger={0.03}
              />
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
