# App Shell Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the simple top-nav layout with an Excalidraw/Cursor-style shell — top-bar menus, a collapsible left sidebar owning learning domains with per-domain session histories, a settings popover, and a read-only session transcript view.

**Architecture:** Two new read-only FastAPI endpoints expose persisted session files (`GET /sessions`, `GET /sessions/{id}/transcript`). On the client, a new `shell/` layer (`AppShell`, `TopBar`, `Sidebar`, `SettingsPopover`, `ActiveDomainContext`) wraps all routes via a react-router layout route. The active domain is a React context backed by the existing `apore.knowledge_source` localStorage key, so Study/Questions keep working off the same state they already read.

**Tech Stack:** FastAPI + Pydantic v2 + pytest (backend, `src/`); React 18 + react-router-dom 6 + Vite 5 + plain CSS with design tokens (client, `src/client/`).

**Spec:** `docs/superpowers/specs/2026-07-15-app-shell-redesign-design.md`

## Global Constraints

- Backend commands run from `src/` (working directory): `python -m pytest tests/api/ -v`.
- Client commands run from `src/client/`: `npm run build` (runs `tsc` then `vite build` — this is the type-check gate; there is no JS test framework in this repo).
- All new CSS uses the tokens in `src/client/src/styles/tokens.css` (canonical per `DESIGN.md`): warm cream canvas, hairline borders, Cursor Orange `--color-primary` for active/primary only.
- Per `AGENTS.md` §5: before implementing UI tasks (Tasks 5–9), invoke the `impeccable` skill to sanity-check the visual decisions; there is no animation work in this plan, so `emil-design-eng` is not needed.
- localStorage keys: `apore.knowledge_source` (existing, format `domain:{domainId}/{chapterId}`), `apore.sidebar_collapsed` (new, `'1'`/`'0'`).
- Session files live in `src/sessions/{uuid}.md` with an H1 title and a `## Session` key-value block (`id`, `created_at`, `knowledge_source`, `focus_mode`, `max_questions`). Non-session files (e.g. `_bank_gen.md`) share the directory — filter by UUID filename.
- Surgical changes only: do not touch the Questions page's knowledge-source dropdown (it already reads/writes the shared localStorage key, so it follows domain switches on next mount).
- Commit after every task; message style `feat(...)`/`refactor(...)` as shown per task.

---

### Task 1: Backend — `GET /sessions` session summaries

**Files:**
- Modify: `src/apore/api/schemas.py` (append at end of file)
- Modify: `src/apore/api/app.py:81` (add `SESSIONS_DIR`), `src/apore/api/app.py:387` (use it), new endpoint after `get_session_state` (~line 731)
- Test: `src/tests/api/test_sessions_list.py` (create)

**Interfaces:**
- Consumes: `apore.runtime.state.read_title(path) -> str`, `state.read_session_meta(path) -> dict[str, str]` (existing).
- Produces: `GET /sessions` → `{"sessions": [{"session_id", "title", "created_at", "knowledge_source"}]}` sorted `created_at` descending; module constant `app_module.SESSIONS_DIR: Path` (monkeypatchable in tests; Task 2 reuses both).

- [ ] **Step 1: Write the failing tests**

Create `src/tests/api/test_sessions_list.py`:

```python
"""Tests for GET /sessions (persisted session summaries)."""

import uuid

import pytest
from fastapi.testclient import TestClient

import apore.api.app as app_module
from apore.api.app import app
from apore.runtime import state

client = TestClient(app)


@pytest.fixture()
def sessions_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "SESSIONS_DIR", tmp_path)
    return tmp_path


def _write_session(
    dirpath,
    *,
    title: str,
    created_at: str,
    knowledge_source: str = "domain:_pytest/01-intro",
) -> str:
    session_id = str(uuid.uuid4())
    state.initialize(
        dirpath / f"{session_id}.md",
        title=title,
        session_id=session_id,
        created_at=created_at,
        knowledge_source=knowledge_source,
        focus_mode="adaptive",
        max_questions=10,
    )
    return session_id


def test_list_sessions_sorted_newest_first(sessions_dir):
    _write_session(sessions_dir, title="Older", created_at="2026-06-01T00:00:00+00:00")
    _write_session(sessions_dir, title="Newer", created_at="2026-07-01T00:00:00+00:00")

    resp = client.get("/sessions")

    assert resp.status_code == 200
    sessions = resp.json()["sessions"]
    assert [s["title"] for s in sessions] == ["Newer", "Older"]
    assert sessions[0]["knowledge_source"] == "domain:_pytest/01-intro"
    uuid.UUID(sessions[0]["session_id"])  # parseable id


def test_list_sessions_skips_non_uuid_and_malformed(sessions_dir):
    # Non-session file that legitimately shares the directory
    (sessions_dir / "_bank_gen.md").write_text("# Not a session\n", encoding="utf-8")
    # UUID-named file without a ## Session block
    (sessions_dir / f"{uuid.uuid4()}.md").write_text("garbage\n", encoding="utf-8")
    good_id = _write_session(
        sessions_dir, title="Good", created_at="2026-07-01T00:00:00+00:00"
    )

    resp = client.get("/sessions")

    assert resp.status_code == 200
    assert [s["session_id"] for s in resp.json()["sessions"]] == [good_id]


def test_list_sessions_empty_dir(sessions_dir):
    resp = client.get("/sessions")
    assert resp.status_code == 200
    assert resp.json() == {"sessions": []}
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `src/`): `python -m pytest tests/api/test_sessions_list.py -v`
Expected: FAIL — `AttributeError: <module 'apore.api.app'> does not have the attribute 'SESSIONS_DIR'` (monkeypatch of a missing attribute).

- [ ] **Step 3: Implement**

In `src/apore/api/schemas.py`, append at the end of the file:

```python
class SessionSummary(BaseModel):
    session_id: str
    title: str
    created_at: str
    knowledge_source: str


class SessionListResponse(BaseModel):
    sessions: list[SessionSummary]
```

In `src/apore/api/app.py`:

1. Add the two new schema names to the existing `from apore.api.schemas import (...)` block (alphabetical position, after `QuestionResponse`):

```python
    SessionListResponse,
    SessionStateResponse,
    SessionSummary,
```

(`SessionStateResponse` is already there — the diff adds `SessionListResponse` and `SessionSummary` around it.)

2. Directly under `PROGRAM_ROOT = Path(__file__).resolve().parent.parent.parent` (line 81), add:

```python
SESSIONS_DIR = PROGRAM_ROOT / "sessions"
```

3. In `create_session` (line 387), replace:

```python
    state_path = PROGRAM_ROOT / "sessions" / f"{session_id}.md"
```

with:

```python
    state_path = SESSIONS_DIR / f"{session_id}.md"
```

4. Immediately after the `get_session_state` endpoint (after ~line 731, before `@app.get("/setup/knowledge", ...)`), add:

```python
@app.get("/sessions", response_model=SessionListResponse)
def list_sessions() -> SessionListResponse:
    """Summaries of persisted sessions, newest first (spec: sidebar histories)."""
    summaries: list[SessionSummary] = []
    if SESSIONS_DIR.is_dir():
        for path in SESSIONS_DIR.glob("*.md"):
            try:
                uuid.UUID(path.stem)
            except ValueError:
                continue
            try:
                meta = state.read_session_meta(path)
                title = state.read_title(path)
            except OSError:
                continue
            if not all(k in meta for k in ("id", "created_at", "knowledge_source")):
                continue
            summaries.append(
                SessionSummary(
                    session_id=meta["id"],
                    title=title,
                    created_at=meta["created_at"],
                    knowledge_source=meta["knowledge_source"],
                )
            )
    summaries.sort(key=lambda s: s.created_at, reverse=True)
    return SessionListResponse(sessions=summaries)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/api/test_sessions_list.py -v`
Expected: 3 passed.

- [ ] **Step 5: Run the full API suite (regression on the `SESSIONS_DIR` refactor)**

Run: `python -m pytest tests/api/ -v`
Expected: all pass (session-creation tests still write via `SESSIONS_DIR`).

- [ ] **Step 6: Commit**

```bash
git add apore/api/schemas.py apore/api/app.py tests/api/test_sessions_list.py
git commit -m "feat(api): GET /sessions lists persisted session summaries"
```

---

### Task 2: Backend — `GET /sessions/{session_id}/transcript`

**Files:**
- Modify: `src/apore/api/schemas.py` (append)
- Modify: `src/apore/api/app.py` (import + endpoint directly under `list_sessions`)
- Test: `src/tests/api/test_sessions_list.py` (append)

**Interfaces:**
- Consumes: `SESSIONS_DIR`, `state.read_title`, `state.read_session_meta` (Task 1).
- Produces: `GET /sessions/{session_id}/transcript` → `{"session_id", "title", "created_at", "knowledge_source", "focus_mode", "max_questions", "body"}`; 404 for invalid-UUID or unknown ids. The client type in Task 3 mirrors these fields.

- [ ] **Step 1: Write the failing tests**

Append to `src/tests/api/test_sessions_list.py`:

```python
def test_get_transcript_returns_meta_and_body(sessions_dir):
    session_id = _write_session(
        sessions_dir, title="Set Theory Warm-up", created_at="2026-07-01T00:00:00+00:00"
    )

    resp = client.get(f"/sessions/{session_id}/transcript")

    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == session_id
    assert data["title"] == "Set Theory Warm-up"
    assert data["created_at"] == "2026-07-01T00:00:00+00:00"
    assert data["knowledge_source"] == "domain:_pytest/01-intro"
    assert data["focus_mode"] == "adaptive"
    assert data["max_questions"] == 10
    assert "## Session" in data["body"]
    assert "## Question Log" in data["body"]


def test_get_transcript_unknown_uuid_404(sessions_dir):
    resp = client.get(f"/sessions/{uuid.uuid4()}/transcript")
    assert resp.status_code == 404


def test_get_transcript_invalid_id_404_no_traversal(sessions_dir):
    # Not a UUID -> rejected before any filesystem access
    resp = client.get("/sessions/..%2F..%2Fpyproject/transcript")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/api/test_sessions_list.py -v`
Expected: `test_get_transcript_returns_meta_and_body` FAILS on `resp.status_code == 200` (route not defined → FastAPI returns 404). The two 404 tests pass vacuously for the same reason — that's expected; the meaningful red test is the first one.

- [ ] **Step 3: Implement**

In `src/apore/api/schemas.py`, append:

```python
class SessionTranscriptResponse(BaseModel):
    session_id: str
    title: str
    created_at: str
    knowledge_source: str
    focus_mode: str
    max_questions: int
    body: str
```

In `src/apore/api/app.py`, add `SessionTranscriptResponse` to the schemas import block (after `SessionSummary`), then add directly under `list_sessions`:

```python
@app.get("/sessions/{session_id}/transcript", response_model=SessionTranscriptResponse)
def get_session_transcript(session_id: str) -> SessionTranscriptResponse:
    """Read-only transcript of a persisted session (works after server restart)."""
    try:
        uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Session not found")
    path = SESSIONS_DIR / f"{session_id}.md"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Session not found")
    meta = state.read_session_meta(path)
    try:
        max_questions = int(meta.get("max_questions", "0"))
    except ValueError:
        max_questions = 0
    return SessionTranscriptResponse(
        session_id=session_id,
        title=state.read_title(path),
        created_at=meta.get("created_at", ""),
        knowledge_source=meta.get("knowledge_source", ""),
        focus_mode=meta.get("focus_mode", "adaptive"),
        max_questions=max_questions,
        body=path.read_text(encoding="utf-8"),
    )
```

Note: this route must be declared in the module *after* `get_session_state` exists anyway; FastAPI matches `/sessions/{id}/state` and `/sessions/{id}/transcript` independently, so ordering between them doesn't matter.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/api/test_sessions_list.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add apore/api/schemas.py apore/api/app.py tests/api/test_sessions_list.py
git commit -m "feat(api): GET /sessions/{id}/transcript serves persisted session markdown"
```

---

### Task 3: Client — API types and fetchers for sessions

**Files:**
- Modify: `src/client/src/api/types.ts` (append)
- Modify: `src/client/src/api/client.ts` (append)

**Interfaces:**
- Consumes: Task 1–2 endpoints; existing `apiFetch<T>` helper in `client.ts`.
- Produces: `listSessions(): Promise<SessionListResponse>`, `getSessionTranscript(sessionId: string): Promise<SessionTranscript>`, and types `SessionSummary { session_id; title; created_at; knowledge_source }`, `SessionListResponse { sessions: SessionSummary[] }`, `SessionTranscript { session_id; title; created_at; knowledge_source; focus_mode; max_questions; body }` — used by Tasks 6–7.

- [ ] **Step 1: Add types**

Append to `src/client/src/api/types.ts`:

```typescript
export interface SessionSummary {
  session_id: string;
  title: string;
  created_at: string;
  knowledge_source: string;
}

export interface SessionListResponse {
  sessions: SessionSummary[];
}

export interface SessionTranscript {
  session_id: string;
  title: string;
  created_at: string;
  knowledge_source: string;
  focus_mode: string;
  max_questions: number;
  body: string;
}
```

- [ ] **Step 2: Add fetchers**

In `src/client/src/api/client.ts`, add `SessionListResponse` and `SessionTranscript` to the `import type { ... } from './types'` list, then append at the end of the file:

```typescript
export async function listSessions(): Promise<SessionListResponse> {
  return apiFetch<SessionListResponse>('/sessions');
}

export async function getSessionTranscript(sessionId: string): Promise<SessionTranscript> {
  return apiFetch<SessionTranscript>(`/sessions/${encodeURIComponent(sessionId)}/transcript`);
}
```

- [ ] **Step 3: Type-check**

Run (from `src/client/`): `npm run build`
Expected: `tsc` passes, vite build succeeds.

- [ ] **Step 4: Commit**

```bash
git add src/api/types.ts src/api/client.ts
git commit -m "feat(client): session list and transcript API bindings"
```

---

### Task 4: Client — ActiveDomainContext

**Files:**
- Create: `src/client/src/shell/ActiveDomainContext.tsx`

**Interfaces:**
- Consumes: `getKnowledgeCatalog`, `getStoredKnowledgeSource`, `setStoredKnowledgeSource` from `../api/client`; `KnowledgeCatalog`, `KnowledgeDomain` from `../api/types`.
- Produces (used by Tasks 5, 7, 8, 9):
  - `ActiveDomainProvider({ children })` — fetches the catalog once, owns active domain id.
  - `useActiveDomain(): { catalog: KnowledgeCatalog | null; catalogError: string | null; activeDomainId: string | null; activeDomain: KnowledgeDomain | null; setActiveDomainId: (domainId: string) => void }`.
  - `parseKnowledgeSource(source: string): { domainId: string; chapterId: string } | null` (exported; replaces Study's local copy in Task 9).

- [ ] **Step 1: Implement**

Create `src/client/src/shell/ActiveDomainContext.tsx`:

```tsx
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import {
  getKnowledgeCatalog,
  getStoredKnowledgeSource,
  setStoredKnowledgeSource,
} from '../api/client';
import type { KnowledgeCatalog, KnowledgeDomain } from '../api/types';

export function parseKnowledgeSource(
  source: string,
): { domainId: string; chapterId: string } | null {
  if (!source.startsWith('domain:')) return null;
  const rest = source.slice('domain:'.length);
  const [domainId, chapterId] = rest.split('/', 2);
  if (!domainId || !chapterId) return null;
  return { domainId, chapterId };
}

interface ActiveDomainValue {
  catalog: KnowledgeCatalog | null;
  catalogError: string | null;
  activeDomainId: string | null;
  activeDomain: KnowledgeDomain | null;
  setActiveDomainId: (domainId: string) => void;
}

const ActiveDomainContext = createContext<ActiveDomainValue | null>(null);

export function ActiveDomainProvider({ children }: { children: ReactNode }) {
  const [catalog, setCatalog] = useState<KnowledgeCatalog | null>(null);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [activeDomainId, setActiveDomainIdState] = useState<string | null>(
    () => parseKnowledgeSource(getStoredKnowledgeSource())?.domainId ?? null,
  );

  useEffect(() => {
    getKnowledgeCatalog()
      .then(setCatalog)
      .catch((err) =>
        setCatalogError(err instanceof Error ? err.message : 'Failed to load catalog'),
      );
  }, []);

  // Fall back to the first catalog domain when the stored one no longer exists.
  useEffect(() => {
    if (!catalog?.domains.length) return;
    if (!activeDomainId || !catalog.domains.some((d) => d.id === activeDomainId)) {
      setActiveDomainIdState(catalog.domains[0].id);
    }
  }, [catalog, activeDomainId]);

  const setActiveDomainId = useCallback(
    (domainId: string) => {
      setActiveDomainIdState(domainId);
      const firstChapter = catalog?.domains.find((d) => d.id === domainId)?.chapters[0];
      if (firstChapter) {
        setStoredKnowledgeSource(firstChapter.knowledge_source);
      }
    },
    [catalog],
  );

  const activeDomain = catalog?.domains.find((d) => d.id === activeDomainId) ?? null;

  const value = useMemo<ActiveDomainValue>(
    () => ({ catalog, catalogError, activeDomainId, activeDomain, setActiveDomainId }),
    [catalog, catalogError, activeDomainId, activeDomain, setActiveDomainId],
  );

  return <ActiveDomainContext.Provider value={value}>{children}</ActiveDomainContext.Provider>;
}

export function useActiveDomain(): ActiveDomainValue {
  const ctx = useContext(ActiveDomainContext);
  if (!ctx) throw new Error('useActiveDomain must be used within ActiveDomainProvider');
  return ctx;
}
```

- [ ] **Step 2: Type-check**

Run: `npm run build`
Expected: passes (the module is not imported anywhere yet; that's fine).

- [ ] **Step 3: Commit**

```bash
git add src/shell/ActiveDomainContext.tsx
git commit -m "feat(client): active-domain context backed by stored knowledge source"
```

---

### Task 5: Client — AppShell, TopBar, Sidebar (domains only), routing rewire

Invoke the `impeccable` skill before this task (AGENTS.md §5) — it covers the shell's layout/hierarchy decisions; the CSS below is the baseline to refine against DESIGN.md, not to replace with a new design.

**Files:**
- Create: `src/client/src/shell/AppShell.tsx`, `src/client/src/shell/TopBar.tsx`, `src/client/src/shell/Sidebar.tsx`, `src/client/src/styles/shell.css`
- Modify: `src/client/src/App.tsx` (layout route + provider), `src/client/src/styles/components.css:1-57` (delete the `.nav` block)
- Delete: `src/client/src/components/Nav.tsx`

**Interfaces:**
- Consumes: `useActiveDomain` (Task 4); react-router `Outlet`, `NavLink`, `Link`.
- Produces: `AppShell` layout route component (children render in `<Outlet/>`); `TopBar({ collapsed, onToggleSidebar })` with an empty `.topbar__right` slot (Task 8 fills it); `Sidebar()` with a `sidebar__section` domains block (Task 7 extends it with session lists). CSS classes `shell*`, `topbar*`, `sidebar*` in `shell.css`.

- [ ] **Step 1: Create `src/client/src/styles/shell.css`**

```css
/* App shell: top bar + collapsible docked sidebar + scrollable content */
.shell {
  display: flex;
  flex-direction: column;
  flex: 1;
  height: 100dvh;
  min-height: 0;
}

.shell__body {
  display: flex;
  flex: 1;
  min-height: 0;
}

.shell__content {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0;
  overflow-y: auto;
}

/* Top bar */
.topbar {
  display: flex;
  align-items: center;
  height: 56px;
  flex-shrink: 0;
  padding: 0 var(--spacing-base);
  background-color: var(--color-canvas);
  border-bottom: 1px solid var(--color-hairline);
}

.topbar__left,
.topbar__right {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  flex: 1;
  min-width: 0;
}

.topbar__right {
  justify-content: flex-end;
}

.topbar__hamburger,
.topbar__iconbtn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border: none;
  background: transparent;
  border-radius: var(--radius-sm);
  font-size: var(--font-size-title-md);
  color: var(--color-ink);
}

.topbar__hamburger:hover,
.topbar__iconbtn:hover {
  background-color: var(--color-hairline-soft);
}

.topbar__domain {
  font-size: var(--font-size-body-sm);
  font-weight: var(--font-weight-medium);
  color: var(--color-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.topbar__menu {
  display: flex;
  align-items: center;
  gap: var(--spacing-xxs);
  padding: var(--spacing-xxs);
  border: 1px solid var(--color-hairline);
  border-radius: var(--radius-md);
  background-color: var(--color-surface-card);
}

.topbar__link {
  display: flex;
  align-items: center;
  min-height: 36px;
  padding: 0 var(--spacing-sm);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-body-sm);
  font-weight: var(--font-weight-medium);
  color: var(--color-body);
}

.topbar__link:hover {
  background-color: var(--color-hairline-soft);
  color: var(--color-ink);
  text-decoration: none;
}

.topbar__link--active {
  color: var(--color-primary);
  background-color: var(--color-hairline-soft);
}

/* Sidebar */
.sidebar {
  display: flex;
  flex-direction: column;
  width: 264px;
  flex-shrink: 0;
  min-height: 0;
  border-right: 1px solid var(--color-hairline);
  background-color: var(--color-canvas-soft);
}

.sidebar__top {
  padding: var(--spacing-sm);
  border-bottom: 1px solid var(--color-hairline-soft);
}

.sidebar__new-session {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  min-height: 40px;
  padding: 0 var(--spacing-sm);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-body-sm);
  font-weight: var(--font-weight-medium);
  color: var(--color-ink);
}

.sidebar__new-session:hover {
  background-color: var(--color-hairline-soft);
  text-decoration: none;
  color: var(--color-ink);
}

.sidebar__section {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: var(--spacing-sm);
}

.sidebar__section-title {
  font-size: var(--font-size-caption);
  font-weight: var(--font-weight-medium);
  color: var(--color-muted);
  padding: var(--spacing-xs) var(--spacing-sm);
}

.sidebar__domains {
  list-style: none;
}

.sidebar__domain {
  display: flex;
  align-items: center;
  width: 100%;
  min-height: 36px;
  padding: 0 var(--spacing-sm);
  border: none;
  background: transparent;
  border-radius: var(--radius-sm);
  font-family: var(--font-sans);
  font-size: var(--font-size-body-sm);
  font-weight: var(--font-weight-medium);
  color: var(--color-body);
  text-align: left;
}

.sidebar__domain:hover {
  background-color: var(--color-hairline-soft);
  color: var(--color-ink);
}

.sidebar__domain--active {
  color: var(--color-primary);
  background-color: var(--color-hairline-soft);
}

.sidebar__error {
  font-size: var(--font-size-caption);
  color: var(--color-semantic-error);
  padding: 0 var(--spacing-sm);
}

.sidebar__footer {
  padding: var(--spacing-sm);
  border-top: 1px solid var(--color-hairline-soft);
}

.sidebar__footer-link {
  display: flex;
  align-items: center;
  min-height: 36px;
  padding: 0 var(--spacing-sm);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-body-sm);
  color: var(--color-body);
}

.sidebar__footer-link:hover {
  background-color: var(--color-hairline-soft);
  color: var(--color-ink);
  text-decoration: none;
}
```

- [ ] **Step 2: Create `src/client/src/shell/TopBar.tsx`**

```tsx
import { NavLink } from 'react-router-dom';
import { useActiveDomain } from './ActiveDomainContext';

const MENU_ITEMS = [
  { to: '/study', label: 'Study' },
  { to: '/questions', label: 'Questions' },
  { to: '/runs', label: 'Runs' },
  { to: '/graph', label: 'Graph' },
] as const;

interface TopBarProps {
  collapsed: boolean;
  onToggleSidebar: () => void;
}

export function TopBar({ collapsed, onToggleSidebar }: TopBarProps) {
  const { activeDomainId } = useActiveDomain();
  return (
    <header className="topbar">
      <div className="topbar__left">
        <button
          type="button"
          className="topbar__hamburger"
          onClick={onToggleSidebar}
          aria-label={collapsed ? 'Open sidebar' : 'Close sidebar'}
          aria-expanded={!collapsed}
        >
          ☰
        </button>
        <span className="topbar__domain">{activeDomainId ?? '—'}</span>
      </div>
      <nav className="topbar__menu" aria-label="Main navigation">
        {MENU_ITEMS.map(({ to, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `topbar__link${isActive ? ' topbar__link--active' : ''}`
            }
          >
            {label}
          </NavLink>
        ))}
      </nav>
      <div className="topbar__right">{/* Settings cog lands here in Task 8 */}</div>
    </header>
  );
}
```

- [ ] **Step 3: Create `src/client/src/shell/Sidebar.tsx`** (domains only — Task 7 adds session histories)

```tsx
import { Link } from 'react-router-dom';
import { useActiveDomain } from './ActiveDomainContext';

export function Sidebar() {
  const { catalog, catalogError, activeDomainId, setActiveDomainId } = useActiveDomain();

  return (
    <aside className="sidebar" aria-label="Learning domains">
      <div className="sidebar__top">
        <Link to="/study" className="sidebar__new-session">
          <span aria-hidden="true">⊕</span> New Session
        </Link>
      </div>
      <div className="sidebar__section">
        <p className="sidebar__section-title">Domains</p>
        {catalogError && <p className="sidebar__error">{catalogError}</p>}
        <ul className="sidebar__domains">
          {catalog?.domains.map((d) => (
            <li key={d.id}>
              <button
                type="button"
                className={`sidebar__domain${
                  d.id === activeDomainId ? ' sidebar__domain--active' : ''
                }`}
                onClick={() => setActiveDomainId(d.id)}
              >
                {d.id}
              </button>
            </li>
          ))}
        </ul>
      </div>
      <div className="sidebar__footer">
        <Link to="/setup" className="sidebar__footer-link">
          Setup
        </Link>
      </div>
    </aside>
  );
}
```

- [ ] **Step 4: Create `src/client/src/shell/AppShell.tsx`**

```tsx
import { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { TopBar } from './TopBar';
import { Sidebar } from './Sidebar';
import '../styles/shell.css';

const SIDEBAR_COLLAPSED_KEY = 'apore.sidebar_collapsed';

export function AppShell() {
  const [collapsed, setCollapsed] = useState(
    () => localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === '1',
  );

  const toggleSidebar = () => {
    setCollapsed((prev) => {
      localStorage.setItem(SIDEBAR_COLLAPSED_KEY, prev ? '0' : '1');
      return !prev;
    });
  };

  return (
    <div className="shell">
      <TopBar collapsed={collapsed} onToggleSidebar={toggleSidebar} />
      <div className="shell__body">
        {!collapsed && <Sidebar />}
        <div className="shell__content">
          <Outlet />
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Rewire `src/client/src/App.tsx`**

Replace the whole file with:

```tsx
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { MotionConfig } from 'framer-motion';
import { AppShell } from './shell/AppShell';
import { ActiveDomainProvider } from './shell/ActiveDomainContext';
import { Home } from './pages/Home';
import { Study } from './pages/Study';
import { Setup } from './pages/Setup';
import { Settings } from './pages/Settings';
import { Questions } from './pages/Questions';
import './styles/global.css';
import './styles/components.css';

export function App() {
  return (
    <MotionConfig reducedMotion="user">
      <BrowserRouter>
        <ActiveDomainProvider>
          <Routes>
            <Route element={<AppShell />}>
              <Route path="/" element={<Home />} />
              <Route path="/setup" element={<Setup />} />
              <Route path="/questions" element={<Questions />} />
              <Route path="/study" element={<Study />} />
              <Route path="/settings" element={<Settings />} />
              <Route
                path="/runs"
                element={<PlaceholderPage title="Runs" note="Run history — coming soon." />}
              />
              <Route
                path="/graph"
                element={<PlaceholderPage title="Graph" note="Knowledge graph — coming soon." />}
              />
            </Route>
          </Routes>
        </ActiveDomainProvider>
      </BrowserRouter>
    </MotionConfig>
  );
}

function PlaceholderPage({ title, note }: { title: string; note: string }) {
  return (
    <main className="page">
      <h1 className="page__title">{title}</h1>
      <p className="page__subtitle">{note}</p>
    </main>
  );
}
```

(The `/settings` route and `Settings` import survive until Task 8 replaces them with the popover.)

- [ ] **Step 6: Delete `src/client/src/components/Nav.tsx` and the `.nav` CSS**

Delete the file, and remove the `.nav` block from `src/client/src/styles/components.css` (lines 1–57, everything from `/* Nav */` through the `.nav__link--active:hover` rule — the file then starts at `/* Card */`).

- [ ] **Step 7: Type-check and verify in the browser**

Run: `npm run build` — expected: passes.
Then run the app (backend from `src/`: `python -m uvicorn apore.api.app:app --port 8000`; client from `src/client/`: `npm run dev`) and verify: top bar shows hamburger + active domain + centered menu; sidebar lists domains from the catalog; clicking a domain highlights it and updates the top-bar label; hamburger collapses/expands and the state survives a reload; New Session lands on `/study`; Setup opens from the footer link.

- [ ] **Step 8: Commit**

```bash
git add src/shell/ src/styles/shell.css src/App.tsx src/styles/components.css
git rm src/components/Nav.tsx
git commit -m "refactor(client): Excalidraw-style app shell with top-bar menus and domain sidebar"
```

---

### Task 6: Client — read-only session transcript page

**Files:**
- Create: `src/client/src/pages/SessionTranscript.tsx`
- Modify: `src/client/src/App.tsx` (route), `src/client/src/styles/components.css` (append transcript styles)

**Interfaces:**
- Consumes: `getSessionTranscript` + `SessionTranscript` (Task 3); route param `id`.
- Produces: `SessionTranscriptPage` at route `/sessions/:id` — the target of Task 7's session links.

- [ ] **Step 1: Create `src/client/src/pages/SessionTranscript.tsx`**

```tsx
import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { getSessionTranscript } from '../api/client';
import type { SessionTranscript } from '../api/types';

export function SessionTranscriptPage() {
  const { id } = useParams<{ id: string }>();
  const [transcript, setTranscript] = useState<SessionTranscript | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    setTranscript(null);
    setError(null);
    getSessionTranscript(id)
      .then(setTranscript)
      .catch((err) =>
        setError(err instanceof Error ? err.message : 'Failed to load session'),
      );
  }, [id]);

  if (error) {
    return (
      <main className="page">
        <h1 className="page__title">Session</h1>
        <p className="page__subtitle">{error}</p>
      </main>
    );
  }

  if (!transcript) {
    return (
      <main className="page">
        <p className="page__subtitle">Loading session…</p>
      </main>
    );
  }

  return (
    <main className="page">
      <h1 className="page__title">{transcript.title}</h1>
      <p className="page__subtitle">
        {transcript.knowledge_source} · {new Date(transcript.created_at).toLocaleString()} ·{' '}
        {transcript.focus_mode} · {transcript.max_questions} questions
      </p>
      <div className="card transcript">
        <pre className="transcript__pre">{transcript.body}</pre>
      </div>
    </main>
  );
}
```

- [ ] **Step 2: Add the route**

In `src/client/src/App.tsx`, import the page:

```tsx
import { SessionTranscriptPage } from './pages/SessionTranscript';
```

and add inside the `<Route element={<AppShell />}>` block (after the `/study` route):

```tsx
<Route path="/sessions/:id" element={<SessionTranscriptPage />} />
```

- [ ] **Step 3: Append transcript styles to `src/client/src/styles/components.css`**

```css
/* Session transcript (read-only) */
.transcript {
  margin-top: var(--spacing-lg);
  overflow-x: auto;
}

.transcript__pre {
  font-family: var(--font-mono);
  font-size: var(--font-size-code);
  line-height: 1.6;
  color: var(--color-ink);
  white-space: pre-wrap;
}
```

- [ ] **Step 4: Type-check and verify**

Run: `npm run build` — expected: passes.
With both servers running, open `/sessions/4727ceb6-0e8c-4e7a-8ab2-6d1617fdb598` (the checked-in session) — expected: title "Discrete Math Set Theory Basics", meta line, and the markdown body in a card. Open `/sessions/not-a-uuid` — expected: the error state with "Session not found".

- [ ] **Step 5: Commit**

```bash
git add src/pages/SessionTranscript.tsx src/App.tsx src/styles/components.css
git commit -m "feat(client): read-only session transcript page"
```

---

### Task 7: Client — per-domain session histories in the sidebar

Invoke the `impeccable` skill before this task (list-row hierarchy, truncation, age badges).

**Files:**
- Modify: `src/client/src/shell/Sidebar.tsx` (replace file), `src/client/src/styles/shell.css` (append)

**Interfaces:**
- Consumes: `listSessions` + `SessionSummary` (Task 3), `parseKnowledgeSource` + `useActiveDomain` (Task 4), route `/sessions/:id` (Task 6).
- Produces: final Sidebar — sessions grouped under their domain (newest first, 5 shown, "More" expander), non-`domain:*` sessions under a trailing "Other" group, each row linking to its transcript.

- [ ] **Step 1: Replace `src/client/src/shell/Sidebar.tsx`**

```tsx
import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { listSessions } from '../api/client';
import type { SessionSummary } from '../api/types';
import { parseKnowledgeSource, useActiveDomain } from './ActiveDomainContext';

const VISIBLE_SESSIONS = 5;

export function formatRelativeAge(iso: string): string {
  const then = Date.parse(iso);
  if (Number.isNaN(then)) return '';
  const seconds = Math.max(0, (Date.now() - then) / 1000);
  const days = seconds / 86400;
  if (days < 1) {
    const hours = Math.floor(seconds / 3600);
    return hours < 1 ? 'now' : `${hours}h`;
  }
  if (days < 30) return `${Math.floor(days)}d`;
  return `${Math.floor(days / 30)}mo`;
}

function SessionRows({ sessions }: { sessions: SessionSummary[] }) {
  const [showAll, setShowAll] = useState(false);
  const visible = showAll ? sessions : sessions.slice(0, VISIBLE_SESSIONS);

  return (
    <ul className="sidebar__sessions">
      {visible.map((s) => {
        const chapterId = parseKnowledgeSource(s.knowledge_source)?.chapterId;
        return (
          <li key={s.session_id}>
            <Link to={`/sessions/${s.session_id}`} className="sidebar__session">
              <span className="sidebar__session-title" title={s.title}>
                {s.title}
              </span>
              {chapterId && <span className="sidebar__session-chapter">{chapterId}</span>}
              <span className="sidebar__session-age">{formatRelativeAge(s.created_at)}</span>
            </Link>
          </li>
        );
      })}
      {!showAll && sessions.length > VISIBLE_SESSIONS && (
        <li>
          <button
            type="button"
            className="sidebar__more"
            onClick={() => setShowAll(true)}
          >
            More…
          </button>
        </li>
      )}
    </ul>
  );
}

export function Sidebar() {
  const { catalog, catalogError, activeDomainId, setActiveDomainId } = useActiveDomain();
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [sessionsError, setSessionsError] = useState<string | null>(null);

  useEffect(() => {
    listSessions()
      .then((res) => setSessions(res.sessions))
      .catch((err) =>
        setSessionsError(err instanceof Error ? err.message : 'Failed to load sessions'),
      );
  }, []);

  const grouped = useMemo(() => {
    const byDomain = new Map<string, SessionSummary[]>();
    const other: SessionSummary[] = [];
    for (const s of sessions) {
      const parsed = parseKnowledgeSource(s.knowledge_source);
      if (parsed) {
        const list = byDomain.get(parsed.domainId) ?? [];
        list.push(s);
        byDomain.set(parsed.domainId, list);
      } else {
        other.push(s);
      }
    }
    return { byDomain, other };
  }, [sessions]);

  return (
    <aside className="sidebar" aria-label="Learning domains">
      <div className="sidebar__top">
        <Link to="/study" className="sidebar__new-session">
          <span aria-hidden="true">⊕</span> New Session
        </Link>
      </div>
      <div className="sidebar__section">
        <p className="sidebar__section-title">Domains</p>
        {catalogError && <p className="sidebar__error">{catalogError}</p>}
        {sessionsError && <p className="sidebar__error">{sessionsError}</p>}
        <ul className="sidebar__domains">
          {catalog?.domains.map((d) => (
            <li key={d.id}>
              <button
                type="button"
                className={`sidebar__domain${
                  d.id === activeDomainId ? ' sidebar__domain--active' : ''
                }`}
                onClick={() => setActiveDomainId(d.id)}
              >
                {d.id}
              </button>
              <SessionRows sessions={grouped.byDomain.get(d.id) ?? []} />
            </li>
          ))}
        </ul>
        {grouped.other.length > 0 && (
          <>
            <p className="sidebar__section-title">Other</p>
            <SessionRows sessions={grouped.other} />
          </>
        )}
      </div>
      <div className="sidebar__footer">
        <Link to="/setup" className="sidebar__footer-link">
          Setup
        </Link>
      </div>
    </aside>
  );
}
```

- [ ] **Step 2: Append session-row styles to `src/client/src/styles/shell.css`**

```css
/* Sidebar session histories */
.sidebar__sessions {
  list-style: none;
  padding-left: var(--spacing-base);
}

.sidebar__session {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  min-height: 32px;
  padding: 0 var(--spacing-sm);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-caption);
  color: var(--color-body);
}

.sidebar__session:hover {
  background-color: var(--color-hairline-soft);
  color: var(--color-ink);
  text-decoration: none;
}

.sidebar__session-title {
  flex: 1;
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sidebar__session-chapter {
  color: var(--color-muted-soft);
  font-family: var(--font-mono);
  font-size: 11px;
  white-space: nowrap;
}

.sidebar__session-age {
  color: var(--color-muted);
  white-space: nowrap;
}

.sidebar__more {
  display: flex;
  align-items: center;
  min-height: 32px;
  padding: 0 var(--spacing-sm);
  border: none;
  background: transparent;
  border-radius: var(--radius-sm);
  font-family: var(--font-sans);
  font-size: var(--font-size-caption);
  color: var(--color-muted);
}

.sidebar__more:hover {
  background-color: var(--color-hairline-soft);
  color: var(--color-ink);
}
```

- [ ] **Step 3: Type-check and verify**

Run: `npm run build` — expected: passes.
In the browser: the checked-in session appears under `discrete-math` with a chapter label and age badge; clicking it opens the transcript page; complete a quick 1-question stub session and confirm it appears at the top of the list after a reload.

- [ ] **Step 4: Commit**

```bash
git add src/shell/Sidebar.tsx src/styles/shell.css
git commit -m "feat(client): per-domain session histories in the sidebar"
```

---

### Task 8: Client — Settings popover, retire the Settings page

Invoke the `impeccable` skill before this task (popover sizing/density).

**Files:**
- Create: `src/client/src/shell/SettingsPopover.tsx`
- Modify: `src/client/src/shell/TopBar.tsx` (mount in `.topbar__right`), `src/client/src/App.tsx` (drop `/settings` route + import), `src/client/src/pages/Home.tsx` (drop the `/settings` link), `src/client/src/styles/shell.css` (append)
- Delete: `src/client/src/pages/Settings.tsx`

**Interfaces:**
- Consumes: `getProviderConfig`, `setProviderConfig`, `ProviderConfig`, `ProviderConfigUpdate` (existing).
- Produces: `SettingsPopover()` — self-contained cog button + anchored panel.

- [ ] **Step 1: Create `src/client/src/shell/SettingsPopover.tsx`**

```tsx
import { useEffect, useRef, useState } from 'react';
import { getProviderConfig, setProviderConfig } from '../api/client';
import type { ProviderConfig, ProviderConfigUpdate } from '../api/types';

export function SettingsPopover() {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onMouseDown(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false);
    }
    document.addEventListener('mousedown', onMouseDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('mousedown', onMouseDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [open]);

  return (
    <div className="settings" ref={containerRef}>
      <button
        type="button"
        className="topbar__iconbtn"
        aria-label="Settings"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        ⚙
      </button>
      {open && <SettingsPanel />}
    </div>
  );
}

function SettingsPanel() {
  const [config, setConfig] = useState<ProviderConfig | null>(null);
  const [anthropicKey, setAnthropicKey] = useState('');
  const [nimKey, setNimKey] = useState('');
  const [model, setModel] = useState('');
  const [anthropicTouched, setAnthropicTouched] = useState(false);
  const [nimTouched, setNimTouched] = useState(false);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function refresh() {
    try {
      const cfg = await getProviderConfig();
      setConfig(cfg);
      setModel(cfg.model);
      setAnthropicKey('');
      setNimKey('');
      setAnthropicTouched(false);
      setNimTouched(false);
      setLoadError(null);
    } catch (err: unknown) {
      setLoadError(err instanceof Error ? err.message : 'Failed to load config');
    }
  }

  async function handleSave() {
    setSaveStatus('saving');
    try {
      const payload: ProviderConfigUpdate = { model };
      if (anthropicTouched) payload.anthropic_api_key = anthropicKey;
      if (nimTouched) payload.nim_api_key = nimKey;
      await setProviderConfig(payload);
      await refresh();
      setSaveStatus('saved');
      setTimeout(() => setSaveStatus('idle'), 2000);
    } catch {
      setSaveStatus('error');
    }
  }

  const activeProviderLabel = config?.active_provider
    ? `${config.active_provider} (${config.active_model ?? 'default model'})`
    : 'No provider configured';

  return (
    <div className="settings__panel" role="dialog" aria-label="Settings">
      {loadError && <p className="settings__error">Could not load config: {loadError}</p>}
      <p className="settings__status">
        Active provider: <strong>{activeProviderLabel}</strong>
      </p>

      <label className="settings__field">
        <span className="settings__label">Anthropic API key</span>
        <input
          type="password"
          className="settings__input"
          value={anthropicKey}
          onChange={(e) => {
            setAnthropicTouched(true);
            setAnthropicKey(e.target.value);
          }}
          placeholder="sk-ant-..."
          spellCheck={false}
          autoComplete="off"
        />
        <span className="settings__hint">
          {config?.anthropic_api_key_set
            ? `Configured (${config.anthropic_api_key_hint ?? 'hidden'})`
            : 'Not configured'}
        </span>
      </label>

      <label className="settings__field">
        <span className="settings__label">NVIDIA NIM API key</span>
        <input
          type="password"
          className="settings__input"
          value={nimKey}
          onChange={(e) => {
            setNimTouched(true);
            setNimKey(e.target.value);
          }}
          placeholder="nvapi-..."
          spellCheck={false}
          autoComplete="off"
        />
        <span className="settings__hint">
          {config?.nim_api_key_set
            ? `Configured (${config.nim_api_key_hint ?? 'hidden'})`
            : 'Not configured'}
        </span>
      </label>

      <label className="settings__field">
        <span className="settings__label">Model override (optional)</span>
        <input
          type="text"
          className="settings__input"
          value={model}
          onChange={(e) => setModel(e.target.value)}
          spellCheck={false}
        />
      </label>

      <div className="settings__actions">
        <button
          type="button"
          className="btn btn--primary"
          onClick={handleSave}
          disabled={saveStatus === 'saving'}
        >
          {saveStatus === 'saving' ? 'Saving…' : saveStatus === 'saved' ? 'Saved' : 'Save'}
        </button>
        {saveStatus === 'error' && (
          <span className="settings__error">Save failed — is the server running?</span>
        )}
      </div>

      <p className="settings__meta">
        v0.1.0-prototype · apore-lite @ 17f4dfa4 ·{' '}
        <a
          href="https://github.com/apore-research/prototype#readme"
          target="_blank"
          rel="noreferrer"
        >
          README
        </a>
      </p>
    </div>
  );
}
```

- [ ] **Step 2: Mount the cog in `src/client/src/shell/TopBar.tsx`**

Add the import:

```tsx
import { SettingsPopover } from './SettingsPopover';
```

and replace the right slot:

```tsx
      <div className="topbar__right">
        <SettingsPopover />
      </div>
```

- [ ] **Step 3: Remove the Settings page**

- In `src/client/src/App.tsx`: delete the `import { Settings } from './pages/Settings';` line and the `<Route path="/settings" element={<Settings />} />` line.
- In `src/client/src/pages/Home.tsx`: delete the `<Link to="/settings" className="btn btn--ghost">Settings</Link>` element (keep "Start studying").
- Delete `src/client/src/pages/Settings.tsx`.

- [ ] **Step 4: Append popover styles to `src/client/src/styles/shell.css`**

```css
/* Settings popover */
.settings {
  position: relative;
}

.settings__panel {
  position: absolute;
  top: calc(100% + var(--spacing-xs));
  right: 0;
  z-index: 20;
  width: 320px;
  padding: var(--spacing-base);
  background-color: var(--color-surface-card);
  border: 1px solid var(--color-hairline);
  border-radius: var(--radius-lg);
  box-shadow: 0 8px 24px rgba(38, 37, 30, 0.08);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.settings__status {
  font-size: var(--font-size-body-sm);
  color: var(--color-body);
}

.settings__field {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xxs);
}

.settings__label {
  font-size: var(--font-size-caption);
  font-weight: var(--font-weight-medium);
  color: var(--color-body);
}

.settings__input {
  height: 36px;
  padding: 0 var(--spacing-xs);
  border: 1px solid var(--color-hairline);
  border-radius: var(--radius-sm);
  font-family: var(--font-mono);
  font-size: var(--font-size-caption);
  color: var(--color-ink);
  background: var(--color-canvas-soft);
  outline: none;
  width: 100%;
}

.settings__hint {
  font-size: var(--font-size-caption);
  color: var(--color-muted);
}

.settings__actions {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.settings__error {
  font-size: var(--font-size-caption);
  color: var(--color-semantic-error);
}

.settings__meta {
  font-size: var(--font-size-caption);
  color: var(--color-muted);
  border-top: 1px solid var(--color-hairline-soft);
  padding-top: var(--spacing-sm);
}
```

- [ ] **Step 5: Type-check and verify**

Run: `npm run build` — expected: passes (would fail if anything still imports `pages/Settings`).
In the browser: cog opens the panel; saving a model override round-trips (status flips to "Saved", hint lines refresh); outside-click and Escape close it; `/settings` now renders a blank content area (no route) — acceptable, nothing links to it anymore.

- [ ] **Step 6: Commit**

```bash
git add src/shell/SettingsPopover.tsx src/shell/TopBar.tsx src/App.tsx src/pages/Home.tsx src/styles/shell.css
git rm src/pages/Settings.tsx
git commit -m "refactor(client): settings popover on the top bar replaces the Settings page"
```

---

### Task 9: Client — Study preamble reads the active domain (domain dropdown removed)

Invoke the `impeccable` skill before this task (preamble hierarchy after the dropdown is gone).

**Files:**
- Modify: `src/client/src/pages/Study.tsx`

**Interfaces:**
- Consumes: `useActiveDomain`, `parseKnowledgeSource` (Task 4); `setStoredKnowledgeSource` (existing).
- Produces: Study preamble = the "New Session flow" from the spec — chapter (scoped to active domain) + focus + length; starting a session persists the chosen chapter to the shared knowledge-source key.

- [ ] **Step 1: Rewire Study.tsx**

All edits are in `src/client/src/pages/Study.tsx`:

1. Replace the api-client import block (lines 2–9) with:

```tsx
import {
  createSession,
  fetchQuestion,
  postTurn,
  getSessionState,
  getStoredKnowledgeSource,
  setStoredKnowledgeSource,
} from '../api/client';
```

and change the types import (line 10) to drop the now-unused catalog type:

```tsx
import type { QuestionResponse, TurnResponse } from '../api/types';
```

then add below it:

```tsx
import { parseKnowledgeSource, useActiveDomain } from '../shell/ActiveDomainContext';
```

2. Delete the local `parseKnowledgeSource` function (lines 71–77) — the context module now provides it.

3. In the `Study` component, replace the catalog/domain state (lines 116–121):

```tsx
  const [catalog, setCatalog] = useState<KnowledgeCatalog | null>(null);
  const [catalogError, setCatalogError] = useState<string | null>(null);

  const stored = parseKnowledgeSource(getStoredKnowledgeSource());
  const [domainId, setDomainId] = useState(stored?.domainId ?? 'discrete-math');
  const [chapterId, setChapterId] = useState(stored?.chapterId ?? '01-set-theory');
```

with:

```tsx
  const { activeDomain, catalogError } = useActiveDomain();

  const stored = parseKnowledgeSource(getStoredKnowledgeSource());
  const [chapterId, setChapterId] = useState(stored?.chapterId ?? '01-set-theory');
```

4. Delete the catalog-fetch effect (lines 135–141) and the domain-fallback effect (lines 143–149). Replace the chapter-fallback effect (lines 151–158) with:

```tsx
  useEffect(() => {
    if (!activeDomain?.chapters.length) return;
    if (!activeDomain.chapters.some((c) => c.id === chapterId)) {
      setChapterId(activeDomain.chapters[0].id);
    }
  }, [activeDomain, chapterId]);
```

5. Replace the selected-domain lookups (lines 160–161):

```tsx
  const selectedDomain = catalog?.domains.find((d) => d.id === domainId);
  const selectedChapter = selectedDomain?.chapters.find((c) => c.id === chapterId);
```

with:

```tsx
  const selectedChapter = activeDomain?.chapters.find((c) => c.id === chapterId);
```

6. In `handleStartSession`, persist the chapter choice — after the `if (!selectedChapter || !canStart) return;` guard, add:

```tsx
    setStoredKnowledgeSource(selectedChapter.knowledge_source);
```

7. In the preamble JSX: delete the whole Domain `<section>` (lines 545–561, `study-domain-heading`), and in the Chapter section change `selectedDomain?.chapters.map` to `activeDomain?.chapters.map`. Update the subtitle copy (line 540) to mention the domain:

```tsx
          <p className="study-start__sub">
            New session in <strong>{activeDomain?.id ?? '…'}</strong> — choose a chapter,
            focus, and session length.
          </p>
```

- [ ] **Step 2: Type-check and verify**

Run: `npm run build` — expected: passes with no unused-import errors.
In the browser: switch domains in the sidebar → the Study preamble's chapter list follows; start a stub session → it runs as before, and after completion the session appears in the sidebar under the right domain (reload to refresh the list); open Questions → it loads the bank for the chapter you just studied.

- [ ] **Step 3: Commit**

```bash
git add src/pages/Study.tsx
git commit -m "refactor(client): study preamble scoped to active domain from sidebar"
```

---

### Task 10: End-to-end verification pass

**Files:** none (verification only; fix regressions if found).

- [ ] **Step 1: Full backend suite**

Run (from `src/`): `python -m pytest`
Expected: all pass.

- [ ] **Step 2: Client build**

Run (from `src/client/`): `npm run build`
Expected: passes.

- [ ] **Step 3: Drive the app** (backend `python -m uvicorn apore.api.app:app --port 8000`, client `npm run dev`)

Walk the spec's frontend checklist:
1. Sidebar collapse toggles via hamburger and persists across reload.
2. Domain click switches the active context: top-bar label, Study preamble chapters, Questions bank all follow.
3. New Session → Study preamble → start a 1-question stub session → complete it → session appears in the sidebar under its domain with title/chapter/age.
4. Clicking the session row opens its read-only transcript.
5. Settings cog: keys/model round-trip; popover closes on outside click and Escape.
6. Setup opens from the sidebar footer link; Runs/Graph placeholders render inside the shell.

- [ ] **Step 4: Commit any verification fixes**

```bash
git status
# commit fixes individually if any were needed
```
