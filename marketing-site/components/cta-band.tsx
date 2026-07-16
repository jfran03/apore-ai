import { RevealWords } from "./motion";
import { WaitlistForm } from "./waitlist-form";

export function CtaBand() {
  return (
    <section className="border-t border-hairline bg-canvas px-6 py-24 md:py-32">
      <div className="mx-auto max-w-3xl text-center">
        <RevealWords
          as="p"
          text="Early access"
          className="section-label mb-4 text-muted"
        />
        <RevealWords
          as="h2"
          text="Ready to learn differently?"
          className="display text-3xl text-ink md:text-4xl"
          delay={0.1}
        />
        <RevealWords
          as="p"
          text="We're opening early access to students and researchers with university emails first."
          className="mx-auto mt-4 max-w-xl text-base text-body"
          delay={0.28}
          stagger={0.03}
        />
        <WaitlistForm
          source="footer"
          variant="light"
          className="mt-10 text-left"
        />
      </div>
    </section>
  );
}
