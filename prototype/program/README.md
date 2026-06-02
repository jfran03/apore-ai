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

## Running the prototype

Requires Python 3.11+, Node 18+.

### Install Python deps

```bash
cd program
pip install -e ".[dev]"
```

### Install client deps

```bash
cd program/client
npm install
```

### Terminal 1 — API server

```bash
cd program
uvicorn apore.api.app:app --reload --port 8000
```

### Terminal 2 — Client dev server

```bash
cd program/client
npm run dev
```

Open http://localhost:5173 in your browser.

### Configure API keys (BYOK)

The prototype uses a bring-your-own-key model:

- Open **Settings** in the client and enter an Anthropic and/or NVIDIA NIM key.
- Anthropic is preferred when both are configured; NIM is the fallback.
- Keys entered in Settings persist to `program/.apore/config.json` and are gitignored.
- You can also pre-seed with `ANTHROPIC_API_KEY` or `NVIDIA_API_KEY` in `.env`.

### Run Python tests

```bash
cd program
python -m pytest tests -q
```

### Fetch the test fixture (needed for Study with apore-lite)

**Setup UI (recommended):** open **Setup** in the client → **Fetch apore-lite**. This clones the pinned corpus, builds `concept-graph.json` from its wiki pages, and saves `fixture:apore-lite` for Study.

**CLI (same behavior):**

```bash
cd program
python scripts/fetch_fixture.py
```

Requires **Git** on your PATH. The clone lands in `program/.fixtures/apore-lite` (gitignored).

## Desktop app (Tauri)

The prototype deliverable is a packaged desktop binary. The `client/` directory includes a full Tauri v2 config under `client/src-tauri/`.

**Prerequisites (install once):**
- Rust: https://rustup.rs — `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh` (or `winget install Rustlang.Rustup` on Windows)
- WebView2 — already bundled on Windows 10/11 (April 2021+). No install needed.

**Build the desktop binary:**
```bash
cd program/client
npm install
npm run tauri:build
# Installer output: client/src-tauri/target/release/bundle/
```

**Desktop dev mode (two terminals):**
```
Terminal 1: cd program && uvicorn apore.api.app:app --reload --port 8000
Terminal 2: cd program/client && npm run tauri:dev
```

See `client/README.md` for full Tauri build docs and the configurable API base URL.

## Notes

The client is a portable React/TS hub. The same codebase builds the web app (`npm run build`) and the desktop app (`npm run tauri:build`). Mobile via Capacitor is viable from the same codebase and deferred to Phase 3. The runtime never moves to the client — every target is a thin client over `apore/api`. Visual design follows [`../DESIGN.md`](../DESIGN.md).

Paths in code should treat `program/` as `PROGRAM_ROOT` unless explicitly configured otherwise.
