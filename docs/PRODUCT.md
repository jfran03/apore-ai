# Product

## Register

product

## Users

**Researcher / content setup** — PhD-adjacent, sets up domain knowledge and configures the system. Uses it at a desk, deliberate pace, reviewing graphs and running batch experiments. Expects precision and transparency over hand-holding.

**Simulated student (automated)** — headless, no direct UI interaction. Drives batch convergence runs.

**(Future) Learner** — self-study user who wants to practice a domain via Socratic dialogue. Expects clarity and focus, not gamification.

## Product Purpose

Apore is an adaptive Socratic tutor loop. It captures explicit and implicit learner signals during dialogue, computes a deterministic reward, and updates a per-learner difficulty scalar per question. Phase 2 collects the interaction data needed to answer whether the system can converge toward a learner's true ability using simulated students. The product surfaces this loop in a polished UI and proves it works headlessly at scale.

## Brand Personality

Precise, calm, rigorous. A research instrument, not an edutainment product. The interface should feel like a well-designed academic paper or a Cursor IDE pane — confident typography, economy of color, no animation for its own sake.

## Anti-references

- **ChatGPT / ChatUI clones** — no full-width chat bubble walls edge to edge. The dialogue is one part of the interface, not the whole thing. The system state (difficulty scalar, concept, signals) must be visibly tracked alongside the conversation.
- **Generic SaaS dashboards** — no hero metric cards, no gradient stat blocks, no dark nav sidebar with icon-only collapsed states, no KPI grids.
- **Duolingo / gamified learning** — no XP bars, streaks, confetti, mascots, or progress ring animations.
- **Flashcard / quiz apps** — no flip-card layouts, no card-grid question banks, no progress bar as the primary reading.

## Design Principles

1. **System state is always visible.** The difficulty scalar, current concept, and turn count are never hidden behind a toggle or drawer. Learners and researchers need to trust the bookkeeping.
2. **Dialogue without the bubble wall.** Conversation turns are typeset as structured prose, not a chat client. Source citations appear inline in monospace. The turn thread is a reading surface, not a messenger.
3. **Orange earns its place.** Cursor Orange (#f54e00) is reserved for one primary action per view. It is the single moment of commitment — starting a session, saving config. Never decorative.
4. **Hairlines over shadows.** Depth through structure and whitespace, not elevation. Cards are a last resort; hairline separators and whitespace do the heavy lifting.
5. **Signal capture is explicit, not inferred.** Easy / OK / Hard and Correct / Incorrect are deliberate researcher inputs, not inferred from behavior. The UI must make them feel consequential, not casual.

## Accessibility & Inclusion

WCAG AA minimum. All interactive targets ≥44px (touch parity for future mobile wrap). Reduced-motion variants for all Framer Motion transitions. Sufficient contrast on body text (≥4.5:1 against canvas). JetBrains Mono for all citations and code surfaces.
