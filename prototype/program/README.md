# Apore program (runtime root)

Everything in this directory is part of the **runnable** Phase 2 prototype. The parent `prototype/` folder is the dev workspace (PRD, design system, Cursor skills, specs); only `program/` executes.

## What goes here

- `apore/` — Python runtime, HTTP API (`api/`), providers, simulated student, fixtures loader
- `client/` — polished front-end (portable React/TS hub → web, desktop via Tauri, mobile via Capacitor); calls `apore/api` only
- `shared/protocols/` — markdown protocols the runtime assembles into prompts
- `shared/_templates/` — scaffold for new domains/chapters (no bundled curriculum)
- `scripts/` — CLIs (e.g. fetch test fixtures, run simulated sessions)
- `AGENTS.md` — canonical tutor harness (loaded by the runtime as the system prompt)
- `AGENT.md` — RL numeric config (weights, α, bounds)
- `CLAUDE.md` — optional stub `@AGENTS.md` when using Claude Code with cwd here

## What does not go here

- Research docs (`PRD.md`, `DESIGN.md`) — stay at prototype root
- `.cursor/`, `.agents/`, `docs/superpowers/` — dev tooling only

## Running

From this directory (once implemented):

```bash
cd program
# Terminal 1: API + runtime
# uvicorn apore.api.app:app --reload

# Terminal 2: polished UI (portable hub)
# cd client && npm run dev
```

The client is a portable React/TS hub. The **prototype deliverable is a desktop app (Tauri)**; the same codebase also builds the web app and wraps to mobile (Capacitor, iOS + Android) without a rewrite. The runtime never moves to the client — every target is a thin client over `apore/api`. Visual design follows [`../DESIGN.md`](../DESIGN.md). UI work uses the `impeccable` skill; motion uses `emil-design-eng`.

Paths in code should treat `program/` as `PROGRAM_ROOT` unless explicitly configured otherwise.
