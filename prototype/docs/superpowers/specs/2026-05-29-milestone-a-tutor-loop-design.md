# Phase 2 Prototype — Full Send (Design Spec)

**Project:** Apore AI (CMPP4010 Applied Research) — Phase 2 Prototype
**Scope:** Runtime core + provider abstraction + adaptive loop + **full polished UI** + headless convergence harness
**Date:** 2026-05-29
**Status:** Approved for planning (scope expanded per product decision)
**References:** [`PRD.md`](../../../PRD.md), [`DESIGN.md`](../../../DESIGN.md), [`jfran03/apore-lite`](https://github.com/jfran03/apore-lite)

---

## 1. Goal

Ship a **complete Phase 2 prototype** that satisfies PRD exit criteria:

1. **Mechanism:** reward-guided loop updates per-learner difficulty deterministically; simulated sessions show convergence toward known target ability (≥10 sessions).
2. **Model-agnostic:** same runtime + UI behavior when swapping Anthropic ↔ NVIDIA NIM (config only).
3. **Product surface:** **full polished web UI** connected to the harness — not headless-only. Researchers and (simulated) learners interact through the app; headless runner remains for batch experiments.

**Full send** means: production-quality front-end per [`DESIGN.md`](../../../DESIGN.md), all primary PRD flows exposed in UI where Phase 2 requires them, single runtime core behind both UI and headless paths.

## 2. Build order (still risk-ordered, but UI is in-scope)

Build in layers, but **do not defer the polished UI to a later milestone**:

| Layer | Delivers | Blocks |
|-------|----------|--------|
| **L1 — Runtime API** | `program/apore/` loop, reward math, providers, fixture loader, stable JSON/session contract | everything |
| **L2 — Polished UI** | `program/web/` app calling L1; study session, setup, graph view, provider settings | demos, manual QA |
| **L3 — Headless harness** | simulated student, ≥10 convergence runs, CSV/summary | PRD success criterion 4 |
| **L4 — Graph compile** (if time) | graphify pipeline + DAG persist; until then, wiki-order proxy + fixture DAG from `apore-lite` | calibration burst (FR-5), true DAG traversal (FR-3.1) |

Baseline knowledge for L1–L3: pinned **`apore-lite`** fixture (read-only) so UI and convergence work proceed without waiting on compile.

**Timeline note:** June 9 deadline is aggressive for L1+L2+L3+L4. If scope slips, cut **L4 compile** and **calibration burst** before cutting UI polish or convergence proof.

## 3. Decisions locked in brainstorming

1. **Phase 2 full send = runtime + API + polished UI + headless convergence** (extends PRD option A with product surface).
2. **Baseline knowledgebase = pinned clone of `apore-lite`** behind a thin adapter; baseline artifacts are read-only for the milestone.
3. **Reproducibility guardrail:** `apore-lite` is pinned to a specific commit; every run records the fixture commit hash.
4. **Distribution-safe skeleton:** a fresh copy ships an empty scaffold + templates only. `discrete-math` is **never bundled** into a distributed copy — it is pulled on demand as a testing-only fixture.
5. **Fixture manifest = testing-stage reproduction only**, not production curriculum shipping.
6. **Model-agnostic harness files:** canonical tutor/harness instructions live in `program/AGENTS.md`. `program/CLAUDE.md` (optional) points at that file for Claude-hosted workflows. The Python runtime always loads `program/AGENTS.md` — never a provider-specific filename.
7. **`program/` segregation:** all runnable code and runtime artifacts live under `prototype/program/`. The prototype repo root is dev-only (PRD, DESIGN, specs, Cursor skills). Coding agents implement under `program/`; see root `AGENTS.md` §0 and `program/README.md`.
8. **Full polished UI in scope:** front-end under `program/client/`, design system from `DESIGN.md`, built with **`impeccable`** (layout/components) and **`emil-design-eng`** (motion only). UI talks to runtime only via **`program/apore/api/`** — no duplicate tutor logic in the front-end.
9. **Front-end is platform-agnostic by design.** The deliverable may be a **desktop app, web app, or mobile app (iOS + Android)**. The runtime never moves to the client; all targets are thin clients over the same HTTP/JSON API. Stack is chosen for maximum cross-platform reuse (see §4.6.1). The API contract — not any single platform — is the stable surface.

## 4. Architecture

### 4.1 Layering (per PRD §5.2)

```
program/client/  desktop ┐
                 web     ├──► program/apore/api/ ──► Runtime core ──► Provider adapter ──► Anthropic | NIM
                 mobile  ┘         (HTTP/JSON)          (orchestration)        │
Headless runner ─────────┘                                                    │
                                              └─► Filesystem (protocols, grounding, learner-state.md)
```

Build the runtime core **once**; expose it via a **thin API layer** to every client target (desktop / web / mobile) and via direct Python calls to the headless runner. The client holds **no** tutor or reward logic — it only renders state and collects input (PRD FR-6.2, NFR-4). Because the client may run off-device (mobile, packaged desktop), the API must not assume the client shares the runtime's filesystem or `localhost`.

### 4.2 Responsibility split (critical for cross-model reliability)

- **LLM does judgment:** rate hedging, count hints, assess correctness, interpret response.
- **Runtime does bookkeeping:** reward arithmetic, scalar update, clamping (PRD §5.3, §7).

This keeps the difficulty update deterministic and identical across providers, including weaker open models.

### 4.3 Context assembly contract (PRD §5.3, Pattern A)

Each question cycle, the runtime assembles the prompt from plaintext (paths relative to `PROGRAM_ROOT` = `program/`):
1. **`AGENTS.md`** (`program/AGENTS.md`) — loaded as the provider-agnostic system prompt.
2. Active protocol (`shared/protocols/generate-question.md` or `shared/protocols/extract-signals.md`).
3. Grounding slice — targeted concept content + neighbors (from the baseline knowledgebase).
4. Current `learner-state.md`.

The runtime sends the assembled prompt, parses the response, and **writes results back** to `learner-state.md`.

### 4.4 Repository layout (`program/` = runtime root)

```
prototype/                          ← dev workspace (does not run)
├── PRD.md, DESIGN.md, docs/
├── AGENTS.md                       ← rules for coding agents building the prototype
├── CLAUDE.md                       ← @AGENTS.md (dev workspace)
└── program/                        ← PROGRAM_ROOT — everything here runs
    ├── README.md
    ├── AGENTS.md                   ← tutor harness (runtime system prompt)
    ├── CLAUDE.md                   ← optional @AGENTS.md when cwd is program/
    ├── AGENT.md                    ← RL numeric config
    ├── apore/                      ← Python package (runtime + api)
    ├── client/                     ← polished front-end (portable: web hub → desktop/mobile)
    ├── shared/protocols/
    ├── shared/_templates/
    ├── scripts/
    └── .fixtures/                  ← gitignored; pinned apore-lite clone for tests
```

- **`PROGRAM_ROOT`:** resolve as the directory containing `program/apore/` (i.e. `program/`). All relative paths in the runtime default from here.
- **Dev agents** must not place runnable modules at `prototype/` root; root `AGENTS.md` §0 enforces this.

### 4.5 Harness file convention (model-agnostic)

| File | Role | Who reads it |
|------|------|----------------|
| **`program/AGENTS.md`** | Canonical tutor harness (markdown). Protocols and ICM behavior for **any** provider live here or under `program/shared/protocols/`. | Python runtime (always). |
| **`program/CLAUDE.md`** | Optional thin **Anthropic / Claude Code** entry when working inside `program/`: `@AGENTS.md`. Not loaded by the Python runtime. | Claude Code with cwd `program/`. |
| **`program/AGENT.md`** | RL numeric config only (reward weights, α, difficulty bounds) — **not** the system prompt. Per PRD Appendix B. | Runtime reads for bookkeeping parameters. |
| **`prototype/AGENTS.md`** | Dev/coding-agent guidelines + pointer to `program/` layout. **Not** the runtime system prompt. | Cursor, root `CLAUDE.md`. |

**Why this matters for Milestone A:** PRD success criterion 5 requires swapping Anthropic ↔ NIM with no architecture change. Harness text stays in `program/AGENTS.md`; provider adapters stay transport-only.

**PRD drift note:** PRD §5.3 step 1 still says “Loads `CLAUDE.md`”. Implement as: load **`program/AGENTS.md`**. Update PRD in a later docs pass.

### 4.6 Polished UI (full send)

**Canonical design:** [`DESIGN.md`](../../../DESIGN.md) at prototype root (tokens, typography, components, do/don’t). The web app imports or mirrors these tokens in `program/web/` — no ad-hoc palette.

**Skill routing (mandatory per root `AGENTS.md` §5):**

| Work | Skill |
|------|--------|
| Layout, IA, components, visual hierarchy, anti-patterns | `impeccable` |
| Motion, transitions, choreography | `emil-design-eng` only |

**Tech stack (prototype):**

- **Front-end:** `program/client/` — React + TypeScript + Vite as the **portable hub** (see §4.6.1); tokens from `DESIGN.md`.
- **API:** `program/apore/api/` — FastAPI wrapping the same `apore.runtime.core` entry points the headless runner uses; CORS-enabled, configurable base URL.
- **Dev:** client dev server proxies API requests to the Python server; both run from `program/`.

### 4.6.1 Cross-platform strategy (desktop / web / mobile)

**Chosen primary target (prototype): Desktop app via Tauri.** The web hub is the build base; the June 9 deliverable is a packaged desktop binary. Web and mobile remain viable from the same codebase and are not pursued for the prototype unless time allows.

The architecture keeps all three viable from **one React/TypeScript codebase + one design-token set**, so identity and logic are not rewritten per platform:

| Target | Packaging path | Shared from hub | Prototype |
|--------|----------------|-----------------|-----------|
| **Desktop app** | Wrap hub in **Tauri** (small native binary; Rust + WebView2) | UI + tokens + API client | **Primary** |
| **Web app** | The hub itself (Vite build / PWA) | 100% | Build base (dev) |
| **Mobile (iOS + Android)** | Wrap hub in **Capacitor** (single React codebase → both stores) | UI + tokens + API client | Deferred |

**Desktop-specific notes:**

- **Toolchain:** Tauri needs Rust + the system WebView (WebView2 on Windows, present on Win10/11). Document in `program/client/README.md`.
- **Runtime process:** the Python API still runs as a separate process. For the prototype, dev runs API + client in two terminals (per `program/README.md`). For a one-click desktop deliverable, use a **Tauri sidecar** to launch the bundled uvicorn server — optional for the demo, noted as the productionization path.
- **API base URL** stays configuration (still `localhost` for a co-located desktop build, but not hard-coded — keeps mobile/remote viable).

Rationale for a web-core hub over Flutter/React-Native-native: the existing runtime work, `DESIGN.md` (CSS/OKLCH tokens), and the `impeccable` skill are all web/CSS-oriented; a web hub reaches **all four store/desktop targets** with the most code reuse before June 9. Native-rendered RN/Flutter is a Phase 3 option if mobile feel demands it.

**Portability rules (enforced now, even while building one target):**

1. **API base URL is configuration**, never hard-coded `localhost` — desktop/mobile builds point at a reachable host.
2. **No browser-only or filesystem assumptions in shared UI** (no direct `window`/`document` coupling in logic; no `fs` from client). Capacitor/Tauri shims live at the edge.
3. **Design tokens are the cross-platform contract** — colors, type, spacing from `DESIGN.md` exported as a single source the hub and any wrapper consume.
4. **Auth/identity is a seam, not an afterthought** — the API assumes an untrusted remote client (relevant once mobile ships); for the prototype it stays open but the boundary exists.
5. **Touch + pointer parity** — interactive targets sized for touch (≥44px) so the same components work on mobile without a rebuild.

**UI surfaces (PRD-aligned, Phase 2):**

| Surface | PRD | UI behavior |
|---------|-----|-------------|
| **Study / tutor session** | FR-3, FR-4 | Socratic dialogue, one turn at a time; citations to wiki nodes; easy/ok/hard + correctness capture; live difficulty scalar (read-only display); signal inconsistency flags (FR-4.4). |
| **Calibration burst** | FR-5 | First three questions non-adaptive when DAG depth available; otherwise show “proxy mode” banner when using wiki-order stand-in. |
| **Setup / researcher** | Persona | Select domain/chapter, provider/model config, load fixture or user skeleton, trigger headless batch run, view run status. |
| **Prerequisite graph** | FR-2 | View DAG (`concept-graph.json` or graphify HTML embed); lightweight edge add/remove/redirect; depth recompute; **scalar read-only** (FR-2.3). |
| **Convergence dashboard** | §10 Layer 2 | Per-session trajectory charts, aggregate error trend, export links to CSV/JSON. |
| **Provider settings** | FR-7 | Anthropic vs NIM toggle + model id; no code change required to swap. |

**Explicit UI boundaries:**

- Front-end **never** computes reward or difficulty; it displays values returned by the API after runtime bookkeeping.
- Front-end **never** calls LLM providers directly; all model traffic goes through `apore` adapters.
- “Play with difficulty” in the UI means **graph structure** only (FR-2.3), not editing the learner scalar.

**Quality bar:** matches `DESIGN.md` — warm cream canvas, ink typography, Cursor Orange sparingly for primary actions, hairline depth, JetBrains Mono on code/citations, timeline pastels only inside in-product agent/status affordances (not system chrome).

## 5. Components & file structure

**Runtime (Python)** — under `program/apore/`:

Implementation language: **Python** (matches `apore-lite` and the graphify compile-time dependency). **All paths below are under `program/`.**

- `apore/runtime/core.py` — orchestration loop; owns the per-question sequence.
- `apore/runtime/reward.py` — deterministic reward + difficulty update math (PRD §7). Pure functions, no I/O.
- `apore/runtime/context.py` — context assembly (loads `program/AGENTS.md`, protocols, grounding slice, learner-state; `PROGRAM_ROOT`-relative paths).
- `apore/runtime/paths.py` — resolves `PROGRAM_ROOT` (directory containing `apore/` package).
- `apore/runtime/state.py` — read/write `learner-state.md`; append-only question log.
- `apore/providers/base.py` — provider interface: `invoke(system_prompt, messages, model, config) -> str`.
- `apore/providers/anthropic_adapter.py` — Anthropic Messages API (`system` top-level param).
- `apore/providers/nim_adapter.py` — NVIDIA NIM OpenAI-compatible `/v1/chat/completions`.
- `apore/providers/throttle.py` — central rate limiter + backoff (NIM ~40 RPM).
- `apore/sim/student.py` — simulated-student agent (fixed ability + misconceptions + seed).
- `apore/sim/runner.py` — headless session runner; drives N sessions via the runtime core.
- `apore/sim/convergence.py` — trajectory-error computation + run summary artifacts.
- `apore/fixtures/manifest.json` — fixture source URL, pinned commit, target path, checksum.
- `apore/api/app.py` — FastAPI app: sessions, question cycle, state read, graph read/write, provider config, batch run trigger.
- `apore/api/schemas.py` — request/response models shared with the web app.

**Front-end** — under `program/web/`:

- `web/src/` — React routes/pages: study, setup, graph, runs/dashboard, settings.
- `web/src/styles/` — tokens from `DESIGN.md` (CSS variables or generated theme).
- `web/src/api/` — typed client for `apore/api` endpoints.

**Shared / scripts:**

- `scripts/fetch_fixture.py` — pulls `apore-lite` at the pinned commit into `program/.fixtures/`.
- `shared/protocols/generate-question.md`, `shared/protocols/extract-signals.md`.
- `shared/_templates/` — new-domain / new-chapter scaffolds (no bundled curriculum).
- `AGENTS.md`, `AGENT.md` — harness + RL config (inside `program/` only).

Reward math stays pure and provider-agnostic; UI stays presentation + input collection only.

## 6. The loop (per question)

1. **Select** concept + question type (recall → apply → synthesis) for the current scalar.
2. **Generate** the question (grounded in the concept slice; record concept, type, intended difficulty).
3. **Capture** the learner/simulated-student response + explicit rating (easy/ok/hard), final correctness, hint count.
4. **Extract signals** — LLM emits raw signal scores (explicit rating, correctness, hints, hedging, turns).
5. **Compute** reward `R` and `new_difficulty = clamp(current + α·R)` in the runtime (α = 0.1, scalar clamped `[0.1, 0.9]`, R clamped `[-1, +1]`).
6. **Append** one fully-populated row to the `learner-state.md` question log; update scalar + per-node mastery.

### Reward model (runtime-owned, PRD §7)

- `R = 0.4·explicit_rating + 0.3·correct + 0.2·hint_score + 0.1·implicit_score`, clamped `[-1, +1]`.
- Signal scoring: rating easy=+1 / ok=0 / hard=−1; correct yes=+0.5 / no=−0.5; hints 0=+0.2 / 1–2=0 / 3+=−0.2; hedging 0=+0.1 / 1–2=0 / 3+=−0.1; turns ≤3=+0.1 / 4–6=0 / 7+=−0.1.

## 7. Provider abstraction

- One interface: `(system_prompt, messages, model, config) -> text` (PRD FR-7.1).
- **Anthropic adapter** — Messages API, `system` as top-level param. Primary.
- **NIM adapter** — OpenAI-compatible endpoint at `https://integrate.api.nvidia.com/v1`, `nvapi-…` key.
- Provider + model selected by config; switching requires **no other change** (PRD FR-7.4, NFR-1).
- All provider calls route through the central throttler with backoff.

## 8. Simulated-student harness

- **Profile contract:** `{ ability: float, misconceptions: [str], seed: int }` — fixed per run; ground truth known.
- **Runner:** reuses the runtime core; only the "learner" turn is produced by the simulated-student agent.
- **Run protocol:** ≥10 sessions; each session emits a full per-question log and run metadata.
- **Run metadata recorded per session:** fixture ID, fixture commit hash, provider, model, student profile, seed.

## 9. Convergence evaluation

- Compute difficulty-trajectory error vs target ability over each session.
- Success signal: aggregate error **trends downward across sessions** (not required to be monotonic per question).
- Artifacts: per-session CSV/JSON trajectories + a summary markdown.

## 10. Distribution-safe skeleton + fixture workflow

- A fresh distributed copy ships **`program/`** with scaffold + `shared/_templates/` only — **no `discrete-math`**.
- `program/apore/fixtures/manifest.json` pins the `apore-lite` source + commit.
- `program/scripts/fetch_fixture.py` fetches the pinned baseline into `program/.fixtures/apore-lite/` (gitignored; testing-only).
- The runtime can load grounding from either a user-created domain (skeleton) or a fixture path (experiments).
- Fixture commit hash is logged into run metadata so any testing stage is reproducible.

## 11. Data contracts (per PRD §8)

- **`learner-state.md`** — initialization block, current scalar, per-node mastery map, append-only question log:
  `Q# | session | date | concept | question type | intended difficulty | explicit rating | correct | hints | turns | hedging | reward R | new difficulty`.
- **Run metadata** — `{ fixture_id, fixture_commit, provider, model, profile, seed }` per session.

## 12. Testing strategy

- **Reward math:** pure-function unit tests covering each signal bucket and clamping boundaries (deterministic; no LLM).
- **Provider interface:** adapter contract tests with a stub provider; verify identical bookkeeping regardless of adapter.
- **API contract:** integration tests on `apore/api` — one question cycle returns updated scalar + log row; UI client types stay in sync.
- **Loop integration:** one full simulated session against the stub provider; assert a complete, well-formed log row per question.
- **Convergence:** assert downward aggregate error trend over a multi-session run (stub or recorded fixtures).
- **UI (manual + automated):** critical paths dogfooded in browser (`impeccable` audit on study + setup flows); optional Playwright smoke for study session happy path.

## 13. Out of scope (Phase 2 prototype)

- GRPO fine-tuning / weight updates; IRT; knowledge-tracing model (Phase 3).
- Real human participant studies (simulated students only).
- Multi-domain beyond discrete-math fixture + empty skeleton.
- Rich freeform graph editor; learner-state overlay on graph (Phase 3).
- Post-session factual-consistency audit; full MathTutorBench run (wire harness only if time).
- **May slip if deadline pressure:** full graphify compile pipeline (keep fixture DAG + wiki proxy); full calibration burst until real DAG depth exists.

## 14. Resolved assumptions (override at planning if needed)

- **Initial scalar:** fixed constant `0.5` until calibration burst (FR-5) is wired with real DAG depth; UI shows burst vs proxy mode clearly.
- **Concept selection without a DAG:** use the `apore-lite` chapter wiki ordering as a temporary linear proxy for traversal order. This is explicitly a stand-in for the prerequisite DAG (Milestone B) and is recorded as such in run metadata.

## 15. Operational task for planning

- Pin the exact `apore-lite` commit: resolve current `main` HEAD at planning time, record it in `apore/fixtures/manifest.json`, and treat it as immutable for the milestone.
