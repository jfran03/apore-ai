# AI-Powered Adaptive Tutoring System
## Research Notes & Actionable Direction

---

# Core Research Direction

## Refined Research Focus

The project investigates whether learner interaction signals during AI-assisted Socratic tutoring can be used to improve adaptive practice-problem generation.

Rather than optimizing for:
- correctness alone,
- engagement metrics,
- or static difficulty progression,

the system attempts to optimize for:
- productive struggle,
- personalized challenge calibration,
- conceptual understanding,
- and learner-specific pedagogical adaptation.

---

# Main Research Contribution

## Proposed Novelty

The strongest and most defensible contribution is:

> Combining learner-provided educational content, Socratic tutoring dialogue, and reinforcement learning from explicit + implicit learner feedback to adaptively generate practice problems calibrated to the learner’s ability.

---

# Important Clarification

Avoid claiming:
- “No existing systems do this”
- “This research area is unexplored”

Instead claim:

> Existing research has explored Socratic LLM tutoring, adaptive educational systems, and retrieval-grounded learning independently, but limited work combines these with reinforcement learning driven by learner interaction signals for adaptive practice-problem generation.

---

# Actual Research Gap

## Strongest Defensible Gap

> Existing adaptive tutoring systems primarily rely on correctness and completion metrics. Limited research explores the use of explicit learner difficulty feedback and implicit Socratic interaction signals to optimize adaptive LLM-generated practice problems.

---

# Key Technical Idea

## System Loop

```text
1. Learner uploads content
      ↓
2. LLM generates practice problem
      ↓
3. Learner attempts problem
      ↓
4. AI tutor provides Socratic guidance
      ↓
5. System captures learner signals
      ↓
6. Reward model updates difficulty calibration
      ↓
7. Future questions become more personalized