"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { FormEvent, useState } from "react";
import { instantTransition } from "@/lib/motion";
import { eduEmailError, normalizeEmail } from "@/lib/validate-email";

type WaitlistFormProps = {
  source: "hero" | "footer";
  variant?: "dark" | "light";
  className?: string;
};

export function WaitlistForm({
  source,
  variant = "dark",
  className = "",
}: WaitlistFormProps) {
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);
  const reduceMotion = useReducedMotion();

  const isDark = variant === "dark";

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    const validationError = eduEmailError(email);
    if (validationError) {
      setError(validationError);
      return;
    }

    setLoading(true);
    try {
      const response = await fetch("/api/waitlist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: normalizeEmail(email), source }),
      });

      const data = (await response.json()) as { error?: string };

      if (!response.ok) {
        setError(data.error ?? "Something went wrong. Please try again.");
        return;
      }

      setSuccess(true);
      setEmail("");
    } catch {
      setError("Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={`mx-auto w-full max-w-lg ${className}`}>
      <AnimatePresence mode="wait">
        {success ? (
          <motion.p
            key="success"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={reduceMotion ? instantTransition : { duration: 0.35 }}
            className={`text-sm ${isDark ? "text-dark-ink" : "text-ink"}`}
            role="status"
          >
            You&apos;re on the list. We&apos;ll reach out at your .edu address.
          </motion.p>
        ) : (
          <motion.div
            key="form"
            initial={{ opacity: 1 }}
            exit={{ opacity: 0, y: -8 }}
            transition={reduceMotion ? instantTransition : { duration: 0.2 }}
          >
            <form onSubmit={handleSubmit} className="w-full" noValidate>
              <label htmlFor={`waitlist-email-${source}`} className="sr-only">
                University email
              </label>
              <div
                className={`flex h-11 w-full items-center justify-between gap-4 rounded-[var(--radius-md)] border px-4 transition focus-within:ring-2 focus-within:ring-accent ${
                  isDark
                    ? "border-white/15 bg-white/5"
                    : "border-hairline bg-white"
                } ${error ? "border-error focus-within:ring-error" : ""}`}
              >
                <input
                  id={`waitlist-email-${source}`}
                  type="email"
                  inputMode="email"
                  autoComplete="email"
                  placeholder="you@university.edu"
                  value={email}
                  onChange={(event) => {
                    setEmail(event.target.value);
                    if (error) setError(null);
                  }}
                  disabled={loading}
                  className={`min-w-0 flex-1 bg-transparent font-mono text-[11px] font-semibold uppercase tracking-[0.08em] outline-none ${
                    isDark
                      ? "text-dark-ink placeholder:text-dark-muted"
                      : "text-ink placeholder:text-muted"
                  }`}
                />
                <button
                  type="submit"
                  disabled={loading}
                  className="section-label shrink-0 font-mono text-accent transition hover:text-accent-active disabled:opacity-60"
                >
                  {loading ? (
                    "Joining…"
                  ) : (
                    <>
                      <span className="sm:hidden">Join →</span>
                      <span className="hidden sm:inline">
                        Join the waitlist →
                      </span>
                    </>
                  )}
                </button>
              </div>
            </form>
            {error ? (
              <motion.p
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                transition={
                  reduceMotion ? instantTransition : { duration: 0.25 }
                }
                className="mt-2 text-sm text-error"
                role="alert"
              >
                {error}
              </motion.p>
            ) : null}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
