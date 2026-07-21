# Apore program (runtime root)

Everything in this directory is part of the **runnable** Phase 2 prototype. The parent `prototype/` folder is the dev workspace (PRD, design system, Cursor skills, specs); only `program/` executes.

The program is split into two top-level pieces:

- `backend/` — the Python runtime and everything it reads at runtime
- `frontend/` — the JavaScript/TypeScript client

## What goes here

- `backend/apore/` — Python runtime, HTTP API (`api/`), providers, simulated student, fixtures loader
- `frontend/` — polished front-end (portable React/TS hub → web, desktop via Tauri, mobile via Capacitor); calls `apore/api` only
- `backend/shared/protocols/` — markdown protocols the runtime assembles into prompts
- `backend/shared/_templates/` — scaffold for new domains/chapters (no bundled curriculum)
- `backend/scripts/` — CLIs (e.g. fetch test fixtures, run simulated sessions)
- `backend/AGENTS.md` — canonical tutor harness (loaded by the runtime as the system prompt)
- `backend/AGENT.md` — RL numeric config (weights, α, bounds)

## What does not go here

- Research docs (`PRD.md`, `DESIGN.md`) — stay at prototype root
- `.cursor/`, `.agents/`, `docs/superpowers/` — dev tooling only

## Running the prototype

Requires Python 3.11+, Node 18+.

### Install Python deps

```bash
cd program/backend
pip install -e ".[dev]"
```

### Install frontend deps

```bash
cd program/frontend
npm install
```

### Terminal 1 — API server

```bash
cd program/backend
uvicorn apore.api.app:app --reload --port 8000
```

### Terminal 2 — Frontend dev server

```bash
cd program/frontend
npm run dev
```

Open http://localhost:5173 in your browser.

### Configure API keys (BYOK)

The prototype uses a bring-your-own-key model:

- Open **Settings** in the client and enter an Anthropic and/or NVIDIA NIM key.
- Anthropic is preferred when both are configured; NIM is the fallback.
- Keys entered in Settings persist to `program/backend/.apore/config.json` and are gitignored.
- You can also pre-seed with `ANTHROPIC_API_KEY` or `NVIDIA_API_KEY` in `.env`.

### Run Python tests

```bash
cd program/backend
python -m pytest tests -q
```

### Fetch discrete-math corpus (Study default)

**Setup UI (recommended):** open **Setup** in the client → **Fetch apore-lite**. This syncs the pinned upstream template into `program/backend/domains/discrete-math/` and sets `domain:discrete-math/01-set-theory` for Study.

**CLI (same behavior):**

```bash
cd program/backend
python scripts/fetch_fixture.py
```

Requires **Git** on your PATH. During fetch, the upstream repo is cloned into `program/backend/.fixtures/apore-lite`, `discrete-math/` is copied into `domains/discrete-math`, then `.fixtures/` is removed. Nothing under `.fixtures/` remains after a successful fetch.

## Desktop app (Tauri)

The prototype deliverable is a packaged desktop binary. The `frontend/` directory includes a full Tauri v2 config under `frontend/src-tauri/`.

**Prerequisites (install once):**
- Rust: https://rustup.rs — `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh` (or `winget install Rustlang.Rustup` on Windows)
- WebView2 — already bundled on Windows 10/11 (April 2021+). No install needed.

**Build the desktop binary:**
```bash
cd program/frontend
npm install
npm run tauri:build
# Installer output: frontend/src-tauri/target/release/bundle/
```

**Desktop dev mode (two terminals):**
```
Terminal 1: cd program/backend && uvicorn apore.api.app:app --reload --port 8000
Terminal 2: cd program/frontend && npm run tauri:dev
```

See `frontend/README.md` for full Tauri build docs and the configurable API base URL.

## Notes

The client is a portable React/TS hub. The same codebase builds the web app (`npm run build`) and the desktop app (`npm run tauri:build`). Mobile via Capacitor is viable from the same codebase and deferred to Phase 3. The runtime never moves to the client — every target is a thin client over `apore/api`. Visual design follows [`../DESIGN.md`](../DESIGN.md).

Paths in code should treat `program/backend/` as `PROGRAM_ROOT` unless explicitly configured otherwise.
