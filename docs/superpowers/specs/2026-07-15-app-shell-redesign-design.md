# App Shell Redesign — Design Spec

**Date:** 2026-07-15
**Status:** Approved pending user review
**Scope:** Frontend (`src/client`) + two backend endpoints (`src/apore/api/app.py`)

## Summary

Refactor the prototype frontend from a simple top-nav page app into an
Excalidraw/Cursor-style shell: a top bar holding the app menus, and a
collapsible left sidebar (hamburger) that owns the learning domains. Each
domain lists its session histories (like Cursor's workspaces with recent
agent sessions). Clicking a domain switches the app-wide active learning
context; clicking a past session opens a read-only transcript. Settings
shrinks from a full page to a cog-triggered popover on the top bar's right.

## Motivation

- "What am I learning" (domain + chapter) is currently implicit state hidden
  in dropdowns inside the Study page and a `localStorage` knowledge-source
  key. Promoting it to a visible sidebar makes it first-class.
- Sessions are already persisted to disk (`src/sessions/{uuid}.md` with
  title, `created_at`, `knowledge_source` frontmatter) but are invisible in
  the UI. The sidebar surfaces them as per-domain history.
- The Settings page is one real form (BYOK provider config) padded with
  static text; a popover suffices.

## Layout

A persistent `AppShell` component wraps all routes:

```
┌──────────────────────────────────────────────────────────┐
│ ☰  discrete-math      [Study · Questions · Runs · Graph]  ⚙ │  ← top bar
├───────────────┬──────────────────────────────────────────┤
│ ⊕ New Session │                                          │
│───────────────│                                          │
│ Domains       │            page content                  │
│  discrete-math│            (router outlet)               │
│   Set theory… │                                          │
│   Injective… 22d                                         │
│   More…       │                                          │
│  linear-alg…  │                                          │
│───────────────│                                          │
│ Setup         │                                          │
└───────────────┴──────────────────────────────────────────┘
```

- Sidebar is **docked** (pushes content), collapsible to nothing via the
  hamburger. Collapse state persists in `localStorage`.
- Styling follows `DESIGN.md` tokens (warm cream canvas, near-black ink,
  Cursor Orange primary, hairline borders — light theme, not the dark
  reference screenshots). UI design decisions during implementation go
  through the `impeccable` skill; any motion through `emil-design-eng`.

### Top bar

- **Left:** hamburger toggle + active domain name (context indicator).
- **Center:** menu group — **Study · Questions · Runs · Graph** — router
  links, all scoped to the active domain.
- **Right:** ⚙ cog opening the Settings popover (below).
- `Setup` and `Settings` leave the top bar.

### Sidebar

Top → bottom:

1. **⊕ New Session** — opens the start-session flow (chapter picker scoped
   to the active domain, focus mode, max questions — the fields Study's
   setup form collects today), then lands in Study with the session live.
2. **Domains section** — one entry per domain from `GET /setup/knowledge`.
   - Clicking a domain sets it as the app-wide active domain.
   - Under each domain: its recent sessions, flat (no chapter nesting),
     newest first, capped at 5 with a "More" expander. Each row shows the
     session title, a small chapter label, and a relative age (e.g. `20d`).
   - Clicking a session navigates to its read-only transcript.
3. **Footer:** `Setup` link (interim — removed in phase 3).

### Settings popover

- Anchored to the top-bar cog. Not a route; the `/settings` page is removed.
- Contents: active-provider status line, Anthropic API key, NVIDIA NIM API
  key, model override, Save — the existing BYOK form, compact. Key inputs
  stay masked with the "Configured (hint)" affordance.
- Muted one-line footer absorbs the old About/Fixture cards:
  `v0.1.0-prototype · apore-lite @ 17f4dfa4 · README`. The disabled
  "Fetch fixture" button is dropped (it only pointed at a CLI command).

## State: active domain

- A React context (`ActiveDomainProvider`) owns the active domain id,
  backed by the existing `localStorage` knowledge-source key
  (`knowledge_source`, format `domain:{domainId}/{chapterId}`).
- Switching domains in the sidebar updates the domain part; the chapter part
  is set per-session by the New Session flow.
- Study and Questions read domain/chapter from this context. Study's
  in-page domain/chapter dropdowns are removed (phase 1 for the domain
  dropdown; the chapter picker moves into the New Session flow).
- Sessions whose `knowledge_source` is not `domain:*` (e.g. fixtures) group
  under a muted **Other** section at the bottom of the domains list.

## Backend additions

Both in `src/apore/api/app.py`, reading the same `sessions/` directory the
session runtime already writes.

### `GET /sessions`

- Scans `PROGRAM_ROOT/sessions/*.md`, parses frontmatter only.
- Returns a flat list: `[{session_id, title, created_at, knowledge_source}]`,
  sorted by `created_at` descending. The client groups by domain.
- Malformed or unreadable files are skipped, not fatal.

### `GET /sessions/{session_id}/transcript` (phase 2)

- Reads `sessions/{session_id}.md` from disk — works for past sessions, not
  just those live in the in-memory `sessions` dict.
- Returns metadata (title, created_at, knowledge_source, focus_mode) plus
  the transcript body (the session markdown), which the client renders
  read-only.
- `session_id` is validated as a UUID before touching the filesystem (no
  path traversal). Unknown id → 404.

## Routes (end state of phase 2)

| Route | Content |
|---|---|
| `/` | Home (unchanged, inside shell) |
| `/study` | Study, scoped to active domain |
| `/questions` | Questions, scoped to active domain |
| `/runs`, `/graph` | Existing placeholders |
| `/sessions/:id` | Read-only transcript view (new) |
| `/setup` | Setup page (linked from sidebar footer; removed in phase 3) |
| `/settings` | **Removed** (popover replaces it) |

## Phases

1. **Shell + sidebar.** `AppShell`, top bar, collapsible sidebar with
   domains + session histories (`GET /sessions`), active-domain context,
   New Session flow, Settings popover, Study dropdown removal. Setup page
   still reachable via sidebar footer.
2. **Transcript view.** `GET /sessions/{id}/transcript` + `/sessions/:id`
   read-only page. Until this ships, session rows render but are
   non-navigable.
3. **Setup absorption.** Add-domain / add-chapter / upload-sources /
   compile become "+" flows inside the sidebar; the Setup page and its
   footer link are retired.

Each phase is independently shippable; this spec fully covers phases 1–2
and sets the direction for phase 3 (its detailed UX will be specced when it
starts).

## Testing

- **Backend:** pytest coverage for both endpoints — list is sorted and
  skips malformed files; transcript returns metadata + body; invalid or
  unknown session id → 404/422; no path traversal.
- **Frontend:** verified by driving the app (sidebar collapse persists,
  domain click switches context and Study/Questions follow, New Session
  starts a live study session, settings popover round-trips config).

## Non-goals

- Resuming past sessions (transcripts are read-only).
- Search, automations, or user accounts from the Cursor reference.
- Dark theme.
- Backend changes to session persistence format.
