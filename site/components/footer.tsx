import { Logo } from "./logo";

export function Footer() {
  return (
    <footer className="border-t border-hairline bg-canvas px-6 py-16">
      <div className="mx-auto flex max-w-6xl flex-col gap-10 md:flex-row md:items-start md:justify-between">
        <div>
          <div className="flex items-center gap-3">
            <Logo size={28} variant="light" />
            <span className="text-sm font-medium tracking-[0.2em] text-ink">
              APORE
            </span>
          </div>
          <p className="mt-4 max-w-sm text-sm text-body">
            AI-powered Socratic tutoring calibrated to productive struggle.
          </p>
        </div>

        <div>
          <p className="section-label text-muted">Team</p>
          <ul className="mt-4 space-y-2 text-sm text-body">
            <li>Aariyana Sayani</li>
            <li>Bhavitha Keezhuridathil</li>
            <li>Jerome Francisco</li>
            <li>Nida Aamir</li>
          </ul>
          <a
            href="https://www.linkedin.com/company/apore-ai"
            target="_blank"
            rel="noopener noreferrer"
            aria-label="Apore on LinkedIn"
            className="mt-4 inline-flex rounded-[var(--radius-md)] p-1 text-ink transition hover:bg-hairline hover:text-accent"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="currentColor"
              className="h-5 w-5"
              aria-hidden
            >
              <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a-1.999 1.999 0 1 1 0-4 1.999 1.999 0 0 1 0 4zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
            </svg>
          </a>
        </div>
      </div>

      <div className="mx-auto mt-12 max-w-6xl border-t border-hairline pt-8 text-sm text-muted">
        © {new Date().getFullYear()} Apore. All rights reserved.
      </div>
    </footer>
  );
}
