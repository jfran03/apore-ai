# Functional App v1 — Domains + Live Tutoring Chat

**Date:** 2026-07-06
**Status:** Approved design, pending implementation plan
**Scope:** First functional slice of the Apore desktop product (`product/`), converting the mockup shell into a working app.

## Goal

Make the two load-bearing surfaces real:

1. **Learning Domains** — creating a domain produces a real, self-contained, portable folder on disk; the sidebar lists real domains.
2. **Live tutoring chat** — ChatView runs the actual question/turn tutoring loop against a domain's knowledge, with transcripts persisted per domain and resumable across restarts.

Sources, curriculum graph, and scratchpad remain *honest stubs* (design language kept, all fake data and dead controls removed). They are separate future slices.

## Decisions Already Made

| Decision | Choice |
|---|---|
| First slice | Domains + live tutoring chat |
| Domain layout | Build the per-domain workspace layout now (not an overlay on the legacy global trees) |
| Seed content | Existing discrete-math curriculum is available as a **dev-only testbed seed**; no production import button or UI |
| Session persistence | Full persist + resume: transcripts on disk, sessions continue after backend restart |
| Architecture | Approach A — backend-owned domain workspaces; React stays a thin HTTP client; all file I/O stays in Python |
| Portability | A domain is a folder and the folder is the domain — copyable to another person by hand |

## 1. Filesystem & Domain Model

### Data root

Domains live in a dedicated, user-findable root: **`~/Apore/domains/`** (`C:\Users\<user>\Apore\domains\` on Windows). Overridable with the `APORE_DATA_DIR` environment variable (dev and tests point it at scratch directories). Deliberately not a hidden app-data directory: a person with know-how should be able to locate, copy, and share a domain folder.

### Domain folder layout

```
~/Apore/domains/
  discrete-math-a3f2/          # slug + short random suffix; folder name = domain id
    domain.json                # identity + config (see below)
    sessions/
      <session-id>.json        # one JSON file per session: metadata + state + transcript
    sources/                   # created empty this slice (future: source intake)
    knowledge/                 # compiled curriculum: chapters, concept graphs, wiki
```

`domain.json` fields: schema version, name, learning objective, teaching style id, teaching prompt text, model preference, created_at.

### Portability rules

1. **Self-contained.** Everything a domain needs is inside its folder. `domain.json` carries all metadata; session files carry the full transcript plus the runtime state (difficulty scalar, question budget, pending-grading state) needed to resume. No absolute paths, no references outside the folder.
2. **Discovery by scan.** The backend lists domains by scanning the data root at request time. There is no index file or registry to go stale. Copy a folder in → refresh → it appears. Delete it → it disappears.
3. **Folder name is identity.** Creation generates `slug-suffix` and never overwrites: a name collision on create gets a fresh suffix. A hand-pasted folder that collides is reported by the scan as-is; renaming it is the human's job (no import feature this slice).

### Testbed seeding

A dev-only mechanism copies the existing compiled `product/backend/domains/discrete-math` content into a domain's `knowledge/` folder so the tutoring loop works end-to-end before source intake exists:

- `POST /domains/{id}/seed`, which returns **404 unless `APORE_TESTBED=1`** is set on the backend process (invisible in production, not merely forbidden).
- A backend script (`scripts/`) that does the same from the command line.
- **No UI button.** The only UI trace: when the backend reports testbed mode, the empty-knowledge state may show a hint that seeding is available.

## 2. Backend — API and Runtime Changes

### New module: `apore/domains/`

The domain workspace store. Owns the data root and is the only code that constructs domain paths:

- Resolve the data root (`APORE_DATA_DIR` or `~/Apore/domains/`), creating it on first use.
- Create a domain folder atomically: slugify name + short suffix, write `domain.json`, scaffold `sessions/`, `sources/`, `knowledge/`.
- Scan and list domains, validating each `domain.json`.
- Load a single domain; answer path questions (knowledge dir, sessions dir).
- Seed helper (copy compiled curriculum into `knowledge/`), used by the gated endpoint and the script.

### New HTTP surface (domain-scoped)

```
GET    /domains                                 list domains (fresh scan)
POST   /domains                                 create domain from the create-form payload
GET    /domains/{id}                            domain.json + content summary (chapters, session count)
GET    /domains/{id}/sessions                   list sessions (id, title, timestamps, turn count, status)
POST   /domains/{id}/sessions                   start session against the domain's knowledge/
                                                (body: chapter id; defaults to first ready chapter)
GET    /domains/{id}/sessions/{sid}             full transcript + runtime state
POST   /domains/{id}/sessions/{sid}/question    next question (same runtime core)
POST   /domains/{id}/sessions/{sid}/turn        two-phase turn (same runtime core)
POST   /domains/{id}/seed                       dev-only; 404 unless APORE_TESTBED=1
```

### Runtime changes (kept surgical)

- **Tutoring core untouched.** `runtime/core.py`, `context.py`, `reward.py`, `intent.py` do not change. What changes is resolution: the knowledge layer learns to load chapters/concept graphs from a domain's `knowledge/` folder (same compiled format the seed copies in), and session persistence gains a domain-aware writer.
- **Session file format:** one JSON per session in `domain/sessions/`, containing:
  - metadata: session id, title, knowledge source, created/updated timestamps;
  - runtime state: difficulty scalar, question budget/count, pending-grading state;
  - transcript: append-ordered events — `question`, `learner_message`, `assistant_feedback`, `rating`, `system`.
  Written after **every turn phase**, so a crash loses at most the in-flight turn.
- **Resume:** a domain-scoped session route hit for a session not in the in-memory map rehydrates it from its JSON file (the URL locates the file — no global search). Scalar, budget, and pending state restore; the loop continues where it left off, including mid-turn (feedback given, rating not yet submitted).
- **Legacy routes** (`/sessions`, `/setup/*`, `/runs/batch`) keep working unchanged against the old global trees. Existing tests stay green; batch/sim tooling keeps functioning. Marked deprecated in code comments; retirement is a later slice. The frontend stops using them entirely.
- **Provider config** (`GET`/`PUT /config/provider`) unchanged; the new Settings UI finally calls it.

## 3. Frontend Architecture

### Navigation

Flat `ViewId` state is replaced by domain-aware navigation held in plain React state (a `useNavigation` hook lifted in `App`): `selectedDomainId` (or none) + a view within the domain — `chat(sessionId)`, `sources`, `graph`, `scratchpad` — plus domain-independent `create-domain` and `settings`. No router, no state library.

### Data hooks (one per concern, style of existing `useBackend`)

- `useDomains()` — list + refresh; powers the sidebar.
- `useDomainSessions(domainId)` — session listing for the Session History folder.
- `useTutorSession(domainId, sessionId)` — the chat engine: transcript, turn-loop phase machine, `sendMessage` / `rate` / `nextQuestion`, resume-on-open. The one genuinely stateful hook.

### Component changes

- **Sidebar** — renders all real domains as cards. Session History lists real session files with type icons; click opens in ChatView. Sources folder lists the domain's real `sources/` contents (honestly empty). All hardcoded fallback data deleted.
- **CreateDomainView** — form is wired: name, objective, teaching style cards (kept), editable teaching prompt, model preference derived from what the provider config actually offers (fake `gpt-4.1`/`gemini-pro` options removed). Submit → `POST /domains` → navigate into the new domain. `BackendOverview` smoke-test panel retired; connection status stays in the titlebar.
- **Settings (new, modal)** — provider key entry (Anthropic / NIM) over `GET`/`PUT /config/provider`, masked key display, "no provider configured" warning.
- **SourcesView / GraphView / ScratchpadView** — honest stubs: design language kept, real (empty) folder state shown, clear "next milestone" note. Fake pipeline pills, fake graph nodes, fake strokes removed. **Rule: a control either works or doesn't render.**
- **Empty states are first-class:** no domains → create prompt; empty `knowledge/` → "no curriculum compiled yet" with chat entry disabled (dev-seed hint only when backend reports testbed mode).

## 4. Live Chat — Turn-Loop UX

The UI surfaces the structured loop faithfully; it does not pretend to be free chat.

- **Starting.** "New session" sits at the top of Session History. Multiple ready chapters → small chapter picker (defaults to first ready); single chapter → zero friction. Create → first question auto-requested.
- **Turn rendering.** Assistant question block → learner prompt card → run indicator while the backend works → assistant feedback block. The composer is a plain text box; `intent.py` classifies server-side, so a help request ("I'm stuck") yields a hint without consuming a graded attempt.
- **Explicit rating, blocking by design.** After graded feedback, inline chips (Easy / Okay / Hard) attach to the feedback block; the composer disables with a hint until rated. Rating finalizes the turn; the scalar update renders as a quiet system line (`difficulty 0.51 → 0.54`); the next question arrives. Mirrors the backend two-phase contract — no hidden auto-rating.
- **Resume.** Opening a past session loads the transcript and lands exactly where it left off, including mid-turn (rating chips waiting). Budget exhausted → completion summary + "start new session."
- **Failure behavior.** No provider key → composer replaced by an inline notice linking to Settings; shell stays usable. Failed LLM call → error block in transcript with retry; completed events are already on disk. Backend offline → offline banner + disabled composer until reconnect.

## 5. Error Handling & Testing

### Backend error contract

- Domain store is the validation choke point: malformed `domain.json` / half-copied folder → that domain listed as `status: "invalid"` with a reason; the scan never crashes on one bad folder.
- Unknown domain/session ids → 404.
- Seed endpoint without `APORE_TESTBED=1` → 404 (invisible).
- Create-name collision → fresh suffix; never overwrite.
- Corrupt/truncated session JSON on rehydration → 409 with readable message; file left untouched for inspection.

### Testing

- **Backend (pytest, extends existing suite):**
  - Unit: domain store — create/scan/collision/invalid-folder against a tmp `APORE_DATA_DIR`.
  - Integration: full domain-scoped loop with the **stub provider** — create → seed → session → question → answer → rate → clear in-memory state → resume. No API keys needed.
  - Existing legacy-route tests stay green untouched (regression net for the runtime refactor).
- **Frontend:** gate is `tsc` + production build. **Vitest for exactly one target:** the `useTutorSession` state machine (phase transitions, resume-mid-turn, error states). No broader test infra this slice.
- **Manual end-to-end script:** backend with `APORE_TESTBED=1` + stub provider → create domain → seed → chat several turns → quit → reopen → resume → copy the domain folder under a new name → verify it appears and opens.

## Out of Scope (future slices)

- Source intake pipeline (files, URLs, video transcription).
- Curriculum graph editing and the curriculum-builder agent.
- tldraw scratchpad and AI vision layer.
- Python-sidecar bundling in Tauri; app icons; CSP hardening.
- Legacy route retirement and migration of the sim/batch tooling to domain workspaces.
- Any domain import/export *feature* (portability is by-hand folder copy only).
