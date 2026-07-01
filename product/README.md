# Apore (product)

`product/` is the runtime root for the Apore desktop application. It is the
engineered successor to `prototype/program/`: the same local-first tutor runtime
and HTTP API, packaged behind a new desktop workspace UI and compiled with Tauri.

```
product/
  backend/    Python FastAPI runtime + tutor engine (program root)
  frontend/   React + Vite workspace UI
    src-tauri/  Tauri v2 desktop shell
  DESIGN.md                 design-system reference
  APORE_PROGRAM_PREVIEW.md  product/IA brief
  artifacts/                static HTML preview the UI is built from
```

The architecture boundary is unchanged from the prototype: the React client is a
thin HTTP client and all tutoring logic, LLM calls, reward math, and file I/O
stay in the Python runtime. The frontend reaches it over `localhost:8000`.

## Prerequisites

- Python 3.11+
- Node 18+
- Rust (for desktop builds only): https://rustup.rs

## Backend

```bash
cd product/backend
pip install -e ".[dev]"

# Run the API
uvicorn apore.api.app:app --reload --port 8000

# Run tests
python -m pytest tests -q
```

The program root is `product/backend/` (the parent of the `apore/` package).
Sessions are written to `product/backend/sessions/`, curriculum lives under
`product/backend/domains/`, and BYOK provider keys persist to
`product/backend/.apore/config.json` (gitignored).

### API keys (BYOK)

Add an Anthropic and/or NVIDIA NIM key in the app Settings, or pre-seed via a
`.env` file (see `.env.example`). Anthropic is preferred when both are set; NIM
is the fallback. Without a key, the runtime returns a clear "no provider
configured" error and the rest of the shell still works.

## Frontend

```bash
cd product/frontend
npm install

# Web dev server (talks to the backend on :8000)
npm run dev          # http://localhost:5173

# Production web build
npm run build        # -> dist/
```

## Desktop (Tauri)

```bash
cd product/frontend

# Dev (two terminals): backend on :8000, then:
npm run tauri:dev

# Packaged installer
npm run tauri:build  # -> src-tauri/target/release/bundle/
```

The API base URL defaults to `http://localhost:8000` and can be overridden at
build time with `VITE_API_BASE_URL`.

## Current state and follow-ups

This is the first vertical slice: the workspace shell, the copied backend, and
the Tauri wiring. The shell connects to the local backend, lists real
curriculum, and can create a real tutoring session end to end.

Not yet implemented (next milestones):

- Bundle/spawn the Python API as a Tauri sidecar (currently a separate process).
- Per-domain filesystem layout (`domain.json` + `sessions/` + `sources/` +
  `knowledge/`) replacing the global `sessions/` and `domains/` trees.
- Real source intake, curriculum graph editing, and the tldraw scratchpad.
- Native desktop integration (file pickers, open-in-folder, app data dir).
- Production CSP hardening and bundle icons.
