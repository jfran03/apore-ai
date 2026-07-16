import { WaitlistForm } from "./waitlist-form";

function Hi({ children }: { children: React.ReactNode }) {
  return (
    <span className="rounded-sm bg-hairline px-1 font-semibold text-ink">
      {children}
    </span>
  );
}

export function Manifesto() {
  return (
    <article className="bg-canvas px-6 pb-24 pt-28 md:pb-32 md:pt-36">
      <div className="mx-auto max-w-xl">
        <h1 className="display text-[2rem] font-semibold leading-tight text-ink md:text-4xl">
          We want to calibrate for struggle.
        </h1>

        <div className="mt-12 space-y-8 text-lg leading-relaxed text-body">
          <p>
            For a long time, getting the <Hi>right answer</Hi> was the point of
            tutoring.
          </p>

          <p>
            Submit. Grade. Move on.
          </p>

          <p>
            But anyone who&apos;s actually learned something knows that&apos;s
            not how it works.
          </p>

          <p>
            The moment you <Hi>understand</Hi> is rarely the moment you got it
            right. It&apos;s the moment you were stuck — and worked through it.
          </p>

          <p>
            <Hi>Adaptive</Hi> tutoring was supposed to fix this. Most systems
            still measure the wrong thing: <Hi>correctness</Hi>, completion, time
            on task.
          </p>

          <p>
            We built <Hi>Apore</Hi> because the signal that matters is{" "}
            <Hi>productive struggle</Hi> — not whether you got the answer on the
            first try.
          </p>

          <p>
            Upload your materials. Practice with Socratic guidance. Tell us when
            it&apos;s too easy or too hard. We calibrate from{" "}
            <Hi>how you learn</Hi>, not just <Hi>what you got right</Hi>.
          </p>

          <blockquote className="border-l-2 border-hairline-strong pl-5 italic text-ink">
            But this is different.
          </blockquote>

          <p>
            This isn&apos;t a chatbot that gives you the answer.
          </p>

          <p>
            This is tutoring that stays in the zone where learning actually
            happens — personalized, grounded in your content, and tuned to{" "}
            <Hi>you</Hi>.
          </p>

          <p className="italic text-ink">
            We don&apos;t think struggle is failure.
          </p>

          <p className="italic text-ink">
            We think it&apos;s the whole point.
          </p>
        </div>

        <section
          id="waitlist"
          className="scroll-mt-24 mt-20 border-t border-hairline pt-12"
        >
          <p className="section-label text-muted">Early access</p>
          <h2 className="display mt-3 text-2xl text-ink md:text-3xl">
            Ready to learn differently?
          </h2>
          <p className="mt-4 text-base leading-relaxed text-body">
            We&apos;re opening early access to students and researchers with
            university emails first.
          </p>
          <WaitlistForm
            source="footer"
            variant="light"
            className="mt-8 !mx-0 max-w-none text-left"
          />
        </section>
      </div>
    </article>
  );
}
