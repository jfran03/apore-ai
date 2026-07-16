Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 0. Repository layout (`program/` vs dev root)

This folder (`prototype/`) is the **development workspace**: specs (`PRD.md`, `DESIGN.md`), design docs, Cursor/Claude tooling (`.cursor/`, `.agents/`), and this `AGENTS.md` for coding agents.

**All runnable Apore prototype code lives under `program/`.** Treat `program/` as the runtime root — anything outside it does not execute as part of the tutor system.

| Location | Purpose |
|----------|---------|
| `prototype/` (repo root) | Dev environment, research docs, agent rules for building the prototype |
| `prototype/program/` | **Runs.** Python package, CLI/scripts, protocols, `AGENT.md`, domain skeleton, fixtures manifest, tests |

When implementing Milestone A or later milestones:

- Put new Python modules under `program/apore/`.
- Put `shared/protocols/`, `shared/_templates/`, and session scripts under `program/`.
- Run tests and CLIs with working directory `program/` (or resolve paths from `program/` as `PROGRAM_ROOT`).
- Do **not** add runtime packages at the prototype root.

The tutor harness markdown the **runtime** loads is `program/AGENTS.md` (model-agnostic). Root `CLAUDE.md` (`@AGENTS.md`) is for this dev workspace only.

See `program/README.md` for what belongs inside the runnable tree.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

---

## 5. UI/UX Decision Matrix

All visual and interactive design work in this prototype follows `DESIGN.md` as the canonical design system (colors, typography, spacing, components).

**Skill routing — mandatory, no exceptions:**

| Task type | Skill to invoke |
|---|---|
| UI/UX design — layout, components, visual hierarchy, design-system decisions | `impeccable` |
| Animation — motion, transitions, keyframes, timing, choreography | `emil-design-eng` |

**Hard boundaries:**
- `impeccable` handles UI design only. Do NOT use it to spec or implement animations.
- `emil-design-eng` handles animation only. Do NOT use it to make UI/UX design decisions.
- If a task spans both (e.g. "animated card component"), split it: design the component with `impeccable` first, then hand off animation spec to `emil-design-eng`.

**Before any UI or animation work**, invoke the appropriate skill above. This applies to new components, modifications to existing ones, and layout decisions.