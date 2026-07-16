"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Logo } from "./logo";
import { defaultTransition, instantTransition, slideDown } from "@/lib/motion";

const links = [
  { href: "/manifesto", label: "Manifesto" },
  { href: "/#research", label: "Research" },
  { href: "/#platform", label: "Platform" },
  { href: "/#how-it-works", label: "How it works" },
];

type NavProps = {
  variant?: "dark" | "light";
};

const waitlistButtonClass =
  "inline-flex h-10 items-center rounded-[var(--radius-md)] bg-accent px-4 text-sm font-medium text-white transition hover:bg-accent-active";

export function Nav({ variant = "dark" }: NavProps) {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();
  const reduceMotion = useReducedMotion();
  const isLight = variant === "light";
  const isHome = pathname === "/";
  const isManifesto = pathname === "/manifesto";
  const [showWaitlistCta, setShowWaitlistCta] = useState(!isHome);

  useEffect(() => {
    const headerOffset = "-64px 0px 0px 0px";

    if (isHome) {
      setShowWaitlistCta(false);

      const hero = document.getElementById("hero");
      if (!hero) return;

      const observer = new IntersectionObserver(
        ([entry]) => {
          setShowWaitlistCta(
            !entry.isIntersecting && entry.boundingClientRect.top < 0,
          );
        },
        { threshold: 0, rootMargin: headerOffset },
      );

      observer.observe(hero);
      return () => observer.disconnect();
    }

    if (isManifesto) {
      setShowWaitlistCta(true);

      const waitlist = document.getElementById("waitlist");
      if (!waitlist) return;

      const observer = new IntersectionObserver(
        ([entry]) => {
          setShowWaitlistCta(!entry.isIntersecting);
        },
        { threshold: 0, rootMargin: headerOffset },
      );

      observer.observe(waitlist);
      return () => observer.disconnect();
    }

    setShowWaitlistCta(true);
  }, [isHome, isManifesto]);

  const scrollToWaitlist = useCallback(() => {
    setOpen(false);

    const focusDelay = reduceMotion ? 0 : 650;
    const focusInput = (id: string) => {
      window.setTimeout(() => {
        document.getElementById(id)?.focus({ preventScroll: true });
      }, focusDelay);
    };

    if (isHome) {
      window.scrollTo({
        top: 0,
        left: 0,
        behavior: reduceMotion ? "auto" : "smooth",
      });
      focusInput("waitlist-email-hero");
      return;
    }

    document.getElementById("waitlist")?.scrollIntoView({
      behavior: reduceMotion ? "auto" : "smooth",
      block: "start",
    });
    focusInput("waitlist-email-footer");
  }, [isHome, reduceMotion]);

  const handleWaitlistClick = useCallback(
    (event: React.MouseEvent<HTMLAnchorElement>) => {
      event.preventDefault();
      scrollToWaitlist();
    },
    [scrollToWaitlist],
  );

  return (
    <motion.header
      initial="hidden"
      animate="visible"
      variants={slideDown}
      transition={reduceMotion ? instantTransition : defaultTransition}
      className={
        isLight
          ? "sticky top-0 z-50 border-b border-hairline bg-canvas/90 backdrop-blur-md"
          : "sticky top-0 z-50 border-b border-white/10 bg-dark-bg/90 backdrop-blur-md"
      }
    >
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
        <a href="/" className="flex items-center gap-3">
          <Logo size={28} variant={isLight ? "light" : "dark"} />
          <span
            className={`text-sm font-medium tracking-[0.2em] ${isLight ? "text-ink" : "text-dark-ink"}`}
          >
            APORE
          </span>
        </a>

        <nav className="hidden items-center gap-8 md:flex" aria-label="Primary">
          {links.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className={`text-sm font-medium transition ${
                isLight
                  ? "text-body hover:text-ink"
                  : "text-dark-muted hover:text-dark-ink"
              }`}
            >
              {link.label}
            </a>
          ))}
        </nav>

        <div className="hidden min-h-10 min-w-[137px] items-center justify-end md:flex">
          <AnimatePresence mode="wait">
            {showWaitlistCta ? (
              <motion.a
                key="waitlist-cta"
                href="#waitlist"
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={reduceMotion ? instantTransition : { duration: 0.2 }}
                className={waitlistButtonClass}
                onClick={handleWaitlistClick}
              >
                Join the waitlist
              </motion.a>
            ) : null}
          </AnimatePresence>
        </div>

        <button
          type="button"
          className={`inline-flex h-10 w-10 items-center justify-center rounded-[var(--radius-md)] border md:hidden ${
            isLight
              ? "border-hairline text-ink"
              : "border-white/15 text-dark-ink"
          }`}
          aria-expanded={open}
          aria-controls="mobile-nav"
          aria-label={open ? "Close menu" : "Open menu"}
          onClick={() => setOpen((value) => !value)}
        >
          <span className="text-lg">{open ? "×" : "☰"}</span>
        </button>
      </div>

      <AnimatePresence>
        {open ? (
          <motion.nav
            id="mobile-nav"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={reduceMotion ? instantTransition : { duration: 0.25 }}
            className={`overflow-hidden border-t px-6 md:hidden ${
              isLight ? "border-hairline" : "border-white/10"
            }`}
            aria-label="Mobile"
          >
            <div className="flex flex-col gap-4 py-4">
              {links.map((link) => (
                <a
                  key={link.href}
                  href={link.href}
                  className={`text-sm font-medium ${isLight ? "text-ink" : "text-dark-ink"}`}
                  onClick={() => setOpen(false)}
                >
                  {link.label}
                </a>
              ))}
              {showWaitlistCta ? (
                <a
                  href="#waitlist"
                  className="inline-flex h-11 items-center justify-center rounded-[var(--radius-md)] bg-accent px-4 text-sm font-medium text-white"
                  onClick={handleWaitlistClick}
                >
                  Join the waitlist
                </a>
              ) : null}
            </div>
          </motion.nav>
        ) : null}
      </AnimatePresence>
    </motion.header>
  );
}
