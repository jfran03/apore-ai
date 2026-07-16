# QA Notes — Phase 2 Prototype

**Date:** 2026-06-01
**Tested with:** StubProvider (no live API keys required for smoke tests)

## Python test suite

- **89 passed, 2 skipped** in 3.99s
- Test breakdown: runtime, providers (stub + Anthropic + NIM adapters), API endpoints, simulated student, fixtures loader

## Client build

- `npm run build`: success
- 0 TypeScript errors
- Bundle: 295.21 KB JS (95.47 KB gzip), 12.44 KB CSS

## README run instructions

- Verified Windows-compatible (PowerShell handles forward slashes; no backslash changes needed)
- Two-terminal setup documented: `uvicorn apore.api.app:app --reload --port 8000` + `npm run dev`
- Install steps, test runner command, and optional fixture fetch all included

## Known issues / deferred

- Live Anthropic/NIM integration test deferred to Task 18
- Provider swap proof to be documented in `docs/swap-test.md` (Task 18)
- `StarletteDeprecationWarning`: httpx/starlette testclient warns to install `httpx2`; non-blocking, tests pass regardless

## Run instructions

See `README.md` — two-terminal setup (uvicorn + npm run dev). Open http://localhost:5173 after both servers are running.
