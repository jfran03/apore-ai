# Phase 2 Full Send — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `program/` as a runnable Phase 2 prototype: Python runtime + FastAPI + polished React UI + headless convergence harness, sharing one orchestration core.

**Architecture:** `apore.runtime` owns loop, reward math, and provider calls; `apore.api` exposes JSON for `program/client/` (a portable React hub targeting web/desktop/mobile); `apore.sim` drives batch runs. UI never calls LLMs or computes rewards. Design tokens from root `DESIGN.md`.

**Tech Stack:** Python 3.11+, FastAPI, uvicorn, pytest; React + TypeScript + Vite portable hub (web build → Tauri desktop, Capacitor iOS/Android); pinned `apore-lite` fixture.

**Front-end target:** **Desktop app (Tauri)** is the primary prototype deliverable; the web hub is the build base, mobile (Capacitor) deferred but kept viable. Build the web hub first, then wrap in Tauri (Task 19). Enforce portability rules from spec §4.6.1 from day one (configurable API base URL, no browser/fs assumptions in shared logic, tokens as the cross-platform contract, touch-sized targets) so the deferred targets stay a packaging step, not a rewrite.

**Spec:** [`docs/superpowers/specs/2026-05-29-milestone-a-tutor-loop-design.md`](../specs/2026-05-29-milestone-a-tutor-loop-design.md)

---

## File map (create order)

| Path | Responsibility |
|------|----------------|
| `program/pyproject.toml` | deps, pytest, package `apore` |
| `program/apore/runtime/reward.py` | pure R + difficulty update |
| `program/apore/runtime/paths.py` | `PROGRAM_ROOT` |
| `program/apore/runtime/state.py` | learner-state.md I/O |
| `program/apore/runtime/context.py` | prompt assembly |
| `program/apore/runtime/core.py` | per-question loop |
| `program/apore/providers/*` | adapters + throttle |
| `program/apore/api/app.py` | FastAPI routes |
| `program/apore/sim/*` | student + runner + convergence |
| `program/apore/fixtures/manifest.json` | pinned apore-lite commit |
| `program/scripts/fetch_fixture.py` | clone fixture |
| `program/shared/protocols/*.md` | generate + extract |
| `program/AGENTS.md`, `program/AGENT.md` | harness + RL config |
| `program/client/*` | polished UI (portable hub: web → desktop/mobile) |

---

### Task 1: Python package scaffold

**Files:**
- Create: `program/pyproject.toml`, `program/apore/__init__.py`, `program/apore/runtime/__init__.py`
- Test: `program/tests/test_smoke.py`

- [ ] **Step 1:** Add `pyproject.toml` with `apore` package, pytest, fastapi, httpx, anthropic, openai (NIM)
- [ ] **Step 2:** `test_import_apore` passes
- [ ] **Step 3:** `pytest program/tests -q` green

---

### Task 2: Reward math (TDD)

**Files:**
- Create: `program/apore/runtime/reward.py`
- Test: `program/tests/runtime/test_reward.py`

- [ ] **Step 1:** Failing tests for each signal bucket + clamp `R` and `new_difficulty`
- [ ] **Step 2:** Implement `compute_reward(signals) -> float` and `update_difficulty(current, r, alpha=0.1)`
- [ ] **Step 3:** All reward tests pass (no I/O, no LLM)

---

### Task 3: PROGRAM_ROOT + learner-state I/O

**Files:**
- Create: `program/apore/runtime/paths.py`, `program/apore/runtime/state.py`
- Test: `program/tests/runtime/test_state.py`

- [ ] **Step 1:** `get_program_root()` resolves directory containing `apore/`
- [ ] **Step 2:** Parse/append question log rows; read/write scalar + mastery block
- [ ] **Step 3:** Round-trip test with temp `learner-state.md`

---

### Task 4: Harness files + protocols

**Files:**
- Create: `program/AGENTS.md`, `program/AGENT.md`, `program/shared/protocols/generate-question.md`, `extract-signals.md`
- Create: `program/shared/_templates/` (minimal)

- [ ] **Step 1:** Port PRD §5.3 / Appendix B content into `AGENTS.md` (provider-agnostic tutor rules)
- [ ] **Step 2:** `AGENT.md` with weights, α=0.1, bounds
- [ ] **Step 3:** Protocol markdown stubs referenced by `context.py`

---

### Task 5: Context assembly

**Files:**
- Create: `program/apore/runtime/context.py`
- Test: `program/tests/runtime/test_context.py`

- [ ] **Step 1:** Load `AGENTS.md` + protocol + grounding slice + learner-state into system/user messages
- [ ] **Step 2:** Test with fixture path to `.fixtures/apore-lite/.../wiki` snippet

---

### Task 6: Provider interface + stub

**Files:**
- Create: `program/apore/providers/base.py`, `stub.py`, `throttle.py`
- Test: `program/tests/providers/test_stub.py`

- [ ] **Step 1:** Protocol `invoke(system_prompt, messages, model, config) -> str`
- [ ] **Step 2:** Stub returns canned JSON for extract-signals / question text
- [ ] **Step 3:** Contract test: two adapters same bookkeeping path

---

### Task 7: Anthropic + NIM adapters

**Files:**
- Create: `program/apore/providers/anthropic_adapter.py`, `nim_adapter.py`
- Test: optional integration (skip without API keys)

- [ ] **Step 1:** Anthropic Messages API with `system` top-level
- [ ] **Step 2:** NIM OpenAI-compatible client + env `NVIDIA_API_KEY`
- [ ] **Step 3:** Config switch `provider: anthropic | nim`

---

### Task 8: Core orchestration loop

**Files:**
- Create: `program/apore/runtime/core.py`
- Test: `program/tests/runtime/test_core_stub.py`

- [ ] **Step 1:** One question cycle: generate → respond → extract → reward → state append
- [ ] **Step 2:** Full stub session (N questions) produces valid log
- [ ] **Step 3:** Metadata records fixture commit, provider, model

---

### Task 9: Fixture manifest + fetch script

**Files:**
- Create: `program/apore/fixtures/manifest.json`, `program/scripts/fetch_fixture.py`
- Create: `program/.gitignore` (`.fixtures/`)

- [ ] **Step 1:** Pin `apore-lite` commit at planning time
- [ ] **Step 2:** Script clones to `program/.fixtures/apore-lite/`
- [ ] **Step 3:** Runtime adapter reads wiki + `concept-graph.json` if present

---

### Task 10: FastAPI layer

**Files:**
- Create: `program/apore/api/app.py`, `schemas.py`
- Test: `program/tests/api/test_session.py`

- [ ] **Step 1:** `POST /sessions`, `POST /sessions/{id}/turn`, `GET /sessions/{id}/state`
- [ ] **Step 2:** `GET/PUT /config/provider`, `POST /runs/batch` (headless trigger)
- [ ] **Step 3:** OpenAPI types exported for web client

---

### Task 11: Simulated student + headless runner

**Files:**
- Create: `program/apore/sim/student.py`, `runner.py`, `convergence.py`
- Test: `program/tests/sim/test_convergence_stub.py`

- [ ] **Step 1:** Student profile `{ability, misconceptions, seed}`
- [ ] **Step 2:** Runner executes ≥10 sessions via `core` (not API)
- [ ] **Step 3:** CSV/JSON trajectories + summary markdown; downward error trend test on stub

---

### Task 12: Client hub scaffold + DESIGN tokens (portable)

**Files:**
- Create: `program/client/package.json`, `vite.config.ts`, `src/styles/tokens.css`
- Invoke: `impeccable` setup script against `DESIGN.md`

- [ ] **Step 1:** Vite React TS app; proxy `/api` → uvicorn; **API base URL from env/config** (no hard-coded localhost — spec §4.6.1 rule 1)
- [ ] **Step 2:** CSS variables from `DESIGN.md` (cream, ink, orange, fonts) as the single cross-platform token source
- [ ] **Step 3:** Responsive app shell (nav, main, mono citations); interactive targets ≥44px for touch parity
- [ ] **Step 4:** Keep shared logic free of `window`/`document`/`fs` coupling so Tauri/Capacitor wrappers drop in later

---

### Task 13: API client + settings page

**Files:**
- Create: `program/client/src/api/client.ts`, `pages/Settings.tsx`

- [ ] **Step 1:** Typed fetch wrapper for session + config routes
- [ ] **Step 2:** Provider/model picker (Anthropic vs NIM)
- [ ] **Step 3:** Fixture load status + fetch trigger (researcher)

---

### Task 14: Study session UI (polished)

**Files:**
- Create: `program/client/src/pages/Study.tsx`, components `QuestionCard`, `TurnThread`, `SignalCapture`, `ScalarBadge`
- Invoke: `impeccable` for layout; `emil-design-eng` for turn transitions only

- [ ] **Step 1:** Start session → display question + Socratic thread
- [ ] **Step 2:** Capture easy/ok/hard + correctness; show inconsistency flag
- [ ] **Step 3:** Read-only difficulty scalar + per-turn reward display from API

---

### Task 15: Graph viewer + structural edit

**Files:**
- Create: `program/client/src/pages/Graph.tsx`
- API: graph read/write endpoints

- [ ] **Step 1:** Render DAG from fixture `concept-graph.json` or graphify HTML embed
- [ ] **Step 2:** Add/remove/redirect edge → persist → recompute depth
- [ ] **Step 3:** Scalar remains read-only; banner when DAG frozen for a run

---

### Task 16: Convergence dashboard

**Files:**
- Create: `program/client/src/pages/Runs.tsx`

- [ ] **Step 1:** List batch runs + per-session trajectory chart
- [ ] **Step 2:** Download CSV/JSON artifacts
- [ ] **Step 3:** Aggregate trend indicator (downward = success)

---

### Task 17: Integration + manual QA

- [ ] **Step 1:** `README` run instructions verified on Windows (two terminals)
- [ ] **Step 2:** One live session with Anthropic OR NIM
- [ ] **Step 3:** `impeccable` audit on Study + Setup flows; fix contrast/spacing issues

---

### Task 18: Provider swap proof (PRD success criterion 5)

- [ ] **Step 1:** Same fixture + seed, run session on Anthropic
- [ ] **Step 2:** Repeat on NIM; compare learner-state row shape and scalar path (bookkeeping identical)
- [ ] **Step 3:** Document in `program/docs/swap-test.md`

---

### Task 19: Desktop packaging (Tauri) — primary deliverable

**Files:**
- Create: `program/client/src-tauri/` (Tauri config), `program/client/README.md` (build steps)

- [ ] **Step 1:** Add Tauri to the hub; confirm Rust + WebView2 toolchain on the build machine
- [ ] **Step 2:** Tauri window loads the hub build; points at API base URL (config, default localhost)
- [ ] **Step 3:** `npm run tauri build` produces a launchable desktop binary; verify a full study session runs in it
- [ ] **Step 4:** (Optional, productionization) Tauri sidecar launches bundled uvicorn so it's one-click — note in README if not done
- [ ] **Step 5:** Confirm no shared-logic regressions (portability rules §4.6.1 held); mobile/web still build from the same hub

> Mobile (Capacitor) and standalone web stay viable from this same codebase but are **not** built for the prototype.

---

## Cut line (if June 9 pressure)

Keep: Tasks 1–11, 12–14, 17–19 (desktop is the deliverable).  
Defer: Task 15 (full graph edit), Task 16 polish, Task 19 Step 4 sidecar (run two-terminal dev instead), mobile/web wrappers, L4 graphify compile, FR-5 calibration burst.

---

## Verification checklist (PRD exit)

- [ ] Reward math unit tests pass
- [ ] ≥10 simulated sessions, downward trajectory error
- [ ] Polished UI study flow works end-to-end
- [ ] **Desktop (Tauri) binary launches and runs a full study session**
- [ ] Provider swap without code change (config only)
- [ ] Fixture commit pinned in manifest + run metadata
