# Functional App v1 (Domains + Live Tutoring Chat) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the Apore product frontend from a mockup into a functional desktop app: portable per-domain workspace folders plus a live, persisted, resumable tutoring chat over the existing Python runtime.

**Architecture:** The Python backend grows a domain-workspace layer (`apore/domains/`) that owns a user-findable data root (`~/Apore/domains/`, env-overridable), and a domain-scoped API router that wraps the existing tutoring flow (extracted unchanged into `apore/api/session_flow.py`) with per-session transcript/resume persistence. The React frontend becomes an honest client: real domain list, wired create form, live transcript ChatView over the question/turn loop, settings modal, and visibly-stubbed sources/graph/scratchpad views.

**Tech Stack:** Python 3.11 + FastAPI + pydantic v2 + pytest (backend); React 18 + TypeScript + Vite (frontend); Vitest (new, dev-only) for the chat state machine. No new frontend runtime dependencies.

**Spec:** `docs/superpowers/specs/2026-07-06-functional-app-v1-design.md`

**Two deliberate refinements vs the spec** (discovered while reading the runtime; both preserve spec intent):

1. **Session persistence is a folder per session** — `domain/sessions/<sid>/session.json` (metadata + transcript + resume snapshot) plus `domain/sessions/<sid>/learner-state.md` (the runtime's existing markdown state file, unchanged). The spec said "one JSON per session," but the runtime core reads/writes the markdown state file directly and the spec also says "tutoring core untouched" — the folder keeps both true, and both files are inspectable.
2. **The real turn loop has more phases than the spec's section 4** — after rating, the backend enters a `reflection` phase (optional follow-up chat on the closed question) that ends with a `continue` action. The chat UI honors it: after rating, the learner can chat about the question, then press **Continue** for the next one.

## Global Constraints

- Data root: `APORE_DATA_DIR` env var, else `~/Apore/domains/`. All domain paths are built ONLY by `apore/domains/store.py`.
- A domain folder is fully self-contained: no absolute paths and no references outside the folder are ever written into it.
- Domain discovery is a directory scan at request time; there is no registry/index file.
- Seed endpoint returns **404** (not 403) unless env `APORE_TESTBED=1`. No seed UI button ever.
- All file I/O stays in Python. The React app talks HTTP only.
- Legacy routes (`/sessions`, `/setup/*`, `/runs/batch`) keep exact current behavior; all existing tests must stay green after every task.
- Frontend honest-UI rule: a control either works or does not render. No fake data, no dead buttons.
- Existing runtime modules `core.py`, `context.py`, `reward.py`, `intent.py`, `state.py` are not modified (one exception: a 2-line prefix addition in `session_meta.py`, Task 6).
- Backend tests: run `python -m pytest tests -q` from `product/backend`. Frontend gates: `npm run build` (runs `tsc`) from `product/frontend`.
- Commit after every task (steps include the commands).

## File Structure (end state)

```
product/backend/apore/domains/          NEW package — workspace layer
  __init__.py
  store.py          data root, DomainRecord, create/list/load
  seed.py           copy compiled curriculum into a workspace domain
  sessionfile.py    session.json read/write: transcript events + resume snapshot
product/backend/apore/api/
  session_flow.py   NEW — SessionState + run_question/run_turn extracted from app.py
  domain_routes.py  NEW — /domains router (domain CRUD, sessions, seed)
  schemas.py        MODIFIED — workspace schemas appended
  app.py            MODIFIED — delegates to session_flow, includes router, /health testbed flag
product/backend/scripts/seed_domain.py  NEW — CLI seeding
product/backend/tests/domains/          NEW test package (store, seed, sessionfile, api, resume)
product/frontend/src/
  types.ts          MODIFIED — AppView navigation union (ViewId deleted)
  api/types.ts      MODIFIED — workspace + turn-loop types appended
  api/client.ts     MODIFIED — domain/session/turn/provider functions
  chat/machine.ts   NEW — pure chat state machine (Vitest-tested)
  chat/machine.test.ts NEW
  hooks/useDomains.ts        NEW
  hooks/useDomainSessions.ts NEW
  hooks/useTutorSession.ts   NEW — wires machine to API
  components/SettingsModal.tsx NEW
  components/Sidebar.tsx     REWRITTEN — real multi-domain tree
  components/Workspace.tsx   MODIFIED — AppView switch, honest tab bar
  components/views/ChatView.tsx        REWRITTEN — live transcript
  components/views/CreateDomainView.tsx MODIFIED — wired form
  components/views/SourcesView.tsx     REWRITTEN — honest stub
  components/views/GraphView.tsx       REWRITTEN — honest stub
  components/views/ScratchpadView.tsx  REWRITTEN — honest stub
  components/BackendOverview.tsx       DELETED
  styles/theme.css  MODIFIED — chat chips/modal styles appended
```

---

### Task 1: Domain store (`apore/domains/store.py`)

**Files:**
- Create: `product/backend/apore/domains/__init__.py` (empty)
- Create: `product/backend/apore/domains/store.py`
- Create: `product/backend/tests/domains/__init__.py` (empty)
- Create: `product/backend/tests/domains/test_store.py`

**Interfaces:**
- Consumes: nothing (leaf module).
- Produces (used by Tasks 2, 3, 5, 6, 7, 8):
  - `get_data_root() -> Path` — env `APORE_DATA_DIR` or `Path.home()/"Apore"/"domains"`; created on first call.
  - `@dataclass DomainRecord: domain_id: str; name: str; objective: str; teaching_style: str; teaching_prompt: str; model_preference: str; created_at: str; path: Path`
  - `@dataclass InvalidDomain: domain_id: str; reason: str`
  - `create_domain(*, name, objective, teaching_style, teaching_prompt, model_preference) -> DomainRecord`
  - `list_domains() -> tuple[list[DomainRecord], list[InvalidDomain]]`
  - `load_domain(domain_id: str) -> DomainRecord` (raises `FileNotFoundError` / `ValueError`)
  - `sessions_dir(rec) -> Path`, `sources_dir(rec) -> Path`, `knowledge_dir(rec) -> Path`, `chapters_dir(rec) -> Path` (= `knowledge/chapters`)

- [ ] **Step 1: Write the failing tests**

`product/backend/tests/domains/test_store.py`:

```python
"""Domain workspace store tests. All tests run against a tmp APORE_DATA_DIR."""

import json

import pytest

from apore.domains import store


@pytest.fixture(autouse=True)
def data_root(tmp_path, monkeypatch):
    monkeypatch.setenv("APORE_DATA_DIR", str(tmp_path))
    return tmp_path


def _create(name="Discrete Math"):
    return store.create_domain(
        name=name,
        objective="Learn discrete mathematics for proof-based CS.",
        teaching_style="socratic",
        teaching_prompt="Teach through Socratic questioning.",
        model_preference="auto",
    )


def test_create_domain_scaffolds_folder(data_root):
    rec = _create()
    assert rec.path.parent == data_root
    assert rec.path.name == rec.domain_id
    assert rec.domain_id.startswith("discrete-math-")
    assert (rec.path / "domain.json").is_file()
    assert (rec.path / "sessions").is_dir()
    assert (rec.path / "sources").is_dir()
    assert (rec.path / "knowledge").is_dir()
    payload = json.loads((rec.path / "domain.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["name"] == "Discrete Math"
    assert payload["teaching_style"] == "socratic"
    assert payload["created_at"]


def test_create_domain_collision_gets_fresh_suffix():
    a = _create()
    b = _create()
    assert a.domain_id != b.domain_id


def test_list_domains_scans_root():
    a = _create("Alpha")
    b = _create("Beta")
    domains, invalid = store.list_domains()
    assert {d.domain_id for d in domains} == {a.domain_id, b.domain_id}
    assert invalid == []


def test_list_domains_reports_invalid_folder(data_root):
    _create("Good")
    bad = data_root / "hand-pasted"
    bad.mkdir()
    (bad / "domain.json").write_text("{not json", encoding="utf-8")
    naked = data_root / "no-manifest"
    naked.mkdir()

    domains, invalid = store.list_domains()
    assert len(domains) == 1
    reasons = {i.domain_id: i.reason for i in invalid}
    assert "hand-pasted" in reasons
    assert "no-manifest" in reasons


def test_load_domain_roundtrip():
    rec = _create()
    loaded = store.load_domain(rec.domain_id)
    assert loaded.name == rec.name
    assert loaded.objective == rec.objective
    assert loaded.path == rec.path


def test_load_domain_missing_raises():
    with pytest.raises(FileNotFoundError):
        store.load_domain("nope-0000")


def test_path_helpers():
    rec = _create()
    assert store.sessions_dir(rec) == rec.path / "sessions"
    assert store.sources_dir(rec) == rec.path / "sources"
    assert store.chapters_dir(rec) == rec.path / "knowledge" / "chapters"


def test_slug_is_filesystem_safe():
    rec = _create(name="  Näive / Set: Theory!  ")
    assert rec.domain_id == rec.path.name
    # slug chars only: lowercase alnum + hyphen
    slug = rec.domain_id.rsplit("-", 1)[0]
    assert all(c.isalnum() or c == "-" for c in slug)
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `product/backend`): `python -m pytest tests/domains/test_store.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'apore.domains'`

- [ ] **Step 3: Implement the store**

`product/backend/apore/domains/__init__.py`: empty file.

`product/backend/apore/domains/store.py`:

```python
"""Domain workspace store.

A domain is a self-contained folder under the data root. The folder name is
the domain id. Everything the domain needs lives inside the folder; discovery
is a directory scan — there is no registry to go stale. This module is the
only code allowed to construct domain paths.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class DomainRecord:
    domain_id: str
    name: str
    objective: str
    teaching_style: str
    teaching_prompt: str
    model_preference: str
    created_at: str
    path: Path


@dataclass(frozen=True)
class InvalidDomain:
    domain_id: str
    reason: str


def get_data_root() -> Path:
    override = os.environ.get("APORE_DATA_DIR")
    root = Path(override) if override else Path.home() / "Apore" / "domains"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _slugify(name: str) -> str:
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return text or "domain"


def create_domain(
    *,
    name: str,
    objective: str,
    teaching_style: str,
    teaching_prompt: str,
    model_preference: str,
) -> DomainRecord:
    root = get_data_root()
    slug = _slugify(name)
    for _ in range(20):
        domain_id = f"{slug}-{secrets.token_hex(2)}"
        path = root / domain_id
        try:
            path.mkdir()
        except FileExistsError:
            continue
        break
    else:  # pragma: no cover - 20 hex collisions
        raise RuntimeError("Could not allocate a unique domain folder")

    created_at = datetime.now(timezone.utc).isoformat()
    record = DomainRecord(
        domain_id=domain_id,
        name=name.strip() or domain_id,
        objective=objective.strip(),
        teaching_style=teaching_style,
        teaching_prompt=teaching_prompt,
        model_preference=model_preference,
        created_at=created_at,
        path=path,
    )
    (path / "sessions").mkdir()
    (path / "sources").mkdir()
    (path / "knowledge").mkdir()
    _write_manifest(record)
    return record


def _write_manifest(record: DomainRecord) -> None:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "name": record.name,
        "objective": record.objective,
        "teaching_style": record.teaching_style,
        "teaching_prompt": record.teaching_prompt,
        "model_preference": record.model_preference,
        "created_at": record.created_at,
    }
    (record.path / "domain.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )


def _load_record(path: Path) -> DomainRecord:
    manifest = path / "domain.json"
    if not manifest.is_file():
        raise ValueError("missing domain.json")
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"unreadable domain.json: {exc}") from exc
    if not isinstance(payload, dict) or "name" not in payload:
        raise ValueError("domain.json is missing required fields")
    return DomainRecord(
        domain_id=path.name,
        name=str(payload.get("name") or path.name),
        objective=str(payload.get("objective") or ""),
        teaching_style=str(payload.get("teaching_style") or "socratic"),
        teaching_prompt=str(payload.get("teaching_prompt") or ""),
        model_preference=str(payload.get("model_preference") or "auto"),
        created_at=str(payload.get("created_at") or ""),
        path=path,
    )


def list_domains() -> tuple[list[DomainRecord], list[InvalidDomain]]:
    root = get_data_root()
    records: list[DomainRecord] = []
    invalid: list[InvalidDomain] = []
    for entry in sorted(root.iterdir()):
        if not entry.is_dir():
            continue
        try:
            records.append(_load_record(entry))
        except ValueError as exc:
            invalid.append(InvalidDomain(domain_id=entry.name, reason=str(exc)))
    return records, invalid


def load_domain(domain_id: str) -> DomainRecord:
    path = get_data_root() / domain_id
    if not path.is_dir():
        raise FileNotFoundError(f"Domain {domain_id!r} not found")
    return _load_record(path)


def sessions_dir(record: DomainRecord) -> Path:
    return record.path / "sessions"


def sources_dir(record: DomainRecord) -> Path:
    return record.path / "sources"


def knowledge_dir(record: DomainRecord) -> Path:
    return record.path / "knowledge"


def chapters_dir(record: DomainRecord) -> Path:
    return record.path / "knowledge" / "chapters"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/domains/test_store.py -q`
Expected: all PASS. Then run the full suite to confirm nothing broke: `python -m pytest tests -q` — all PASS.

- [ ] **Step 5: Commit**

```bash
git add product/backend/apore/domains product/backend/tests/domains
git commit -m "feat(backend): domain workspace store with portable folder layout"
```

---

### Task 2: Workspace knowledge resolution + seed helper + CLI

**Files:**
- Modify: `product/backend/apore/knowledge/chapter.py` (`_parse_knowledge_source`, `resolve_chapter`)
- Create: `product/backend/apore/domains/seed.py`
- Create: `product/backend/scripts/seed_domain.py`
- Create: `product/backend/tests/domains/test_seed_and_resolve.py`

**Interfaces:**
- Consumes: `store.load_domain`, `store.chapters_dir` (Task 1).
- Produces:
  - Knowledge source format `workspace:<domain_id>/<chapter_id>` accepted by `resolve_chapter(knowledge_source, program_root)`, resolving to `<data_root>/<domain_id>/knowledge/chapters/<chapter_id>`.
  - `seed.seed_domain(record: DomainRecord, *, program_root: Path, source_domain_id: str = "discrete-math") -> list[str]` — returns copied chapter ids; raises `FileNotFoundError` if the source domain has no chapters; skips chapters that already exist in the workspace.

- [ ] **Step 1: Write the failing tests**

`product/backend/tests/domains/test_seed_and_resolve.py`:

```python
import pytest

from apore.domains import seed, store
from apore.knowledge.chapter import resolve_chapter
import apore.api.app as app_module

PROGRAM_ROOT = app_module.PROGRAM_ROOT


@pytest.fixture(autouse=True)
def data_root(tmp_path, monkeypatch):
    monkeypatch.setenv("APORE_DATA_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture()
def domain():
    return store.create_domain(
        name="Testbed",
        objective="obj",
        teaching_style="socratic",
        teaching_prompt="p",
        model_preference="auto",
    )


def test_seed_copies_chapters_into_workspace(domain):
    # The pytest curriculum fixture is guaranteed present by tests/api/conftest
    # for api tests; here we seed from the real discrete-math tree if present,
    # else from the _pytest tree the api conftest creates.
    source = "discrete-math"
    if not (PROGRAM_ROOT / "domains" / source / "chapters").is_dir():
        source = "_pytest"
    chapters = seed.seed_domain(
        domain, program_root=PROGRAM_ROOT, source_domain_id=source
    )
    assert chapters
    for chapter_id in chapters:
        chapter_root = store.chapters_dir(domain) / chapter_id
        assert chapter_root.is_dir()


def test_seed_missing_source_raises(domain):
    with pytest.raises(FileNotFoundError):
        seed.seed_domain(
            domain, program_root=PROGRAM_ROOT, source_domain_id="no-such-domain"
        )


def test_seed_skips_existing_chapters(domain):
    source = "discrete-math"
    if not (PROGRAM_ROOT / "domains" / source / "chapters").is_dir():
        source = "_pytest"
    first = seed.seed_domain(domain, program_root=PROGRAM_ROOT, source_domain_id=source)
    second = seed.seed_domain(domain, program_root=PROGRAM_ROOT, source_domain_id=source)
    assert first
    assert second == []


def test_resolve_workspace_chapter(domain):
    chapter_root = store.chapters_dir(domain) / "01-intro"
    chapter_root.mkdir(parents=True)
    (chapter_root / "concept-graph.json").write_text("{}", encoding="utf-8")
    ctx = resolve_chapter(f"workspace:{domain.domain_id}/01-intro", PROGRAM_ROOT)
    assert ctx.chapter_root == chapter_root
    assert ctx.knowledge_source == f"workspace:{domain.domain_id}/01-intro"


def test_resolve_workspace_missing_chapter_raises(domain):
    with pytest.raises(FileNotFoundError):
        resolve_chapter(f"workspace:{domain.domain_id}/nope", PROGRAM_ROOT)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/domains/test_seed_and_resolve.py -q`
Expected: FAIL (`cannot import name 'seed'`, and `ValueError: Unknown knowledge_source` for the resolve tests).

- [ ] **Step 3: Implement**

`product/backend/apore/domains/seed.py`:

```python
"""Copy compiled curriculum into a workspace domain (testbed only).

Production has no UI path to this; it exists so the tutoring loop can be
exercised end-to-end before source intake ships.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from apore.domains.store import DomainRecord, chapters_dir


def seed_domain(
    record: DomainRecord,
    *,
    program_root: Path,
    source_domain_id: str = "discrete-math",
) -> list[str]:
    source_chapters = program_root / "domains" / source_domain_id / "chapters"
    if not source_chapters.is_dir():
        raise FileNotFoundError(
            f"No compiled curriculum at {source_chapters}"
        )
    dest_root = chapters_dir(record)
    dest_root.mkdir(parents=True, exist_ok=True)

    copied: list[str] = []
    for chapter in sorted(p for p in source_chapters.iterdir() if p.is_dir()):
        dest = dest_root / chapter.name
        if dest.exists():
            continue
        shutil.copytree(chapter, dest)
        copied.append(chapter.name)
    return copied
```

In `product/backend/apore/knowledge/chapter.py`, extend `_parse_knowledge_source` — add before the final `raise`:

```python
    if source.startswith("workspace:"):
        rest = source.split(":", 1)[1]
        if "/" not in rest:
            raise ValueError(
                f"workspace knowledge source must be workspace:{{id}}/{{chapter}}, got {source!r}"
            )
        domain_id, chapter_id = rest.split("/", 1)
        return "workspace", domain_id, chapter_id
```

and update the error message on the final raise to `"use fixture:name, domain:id/chapter, or workspace:id/chapter"`.

In `resolve_chapter`, after the `fixture` branch add:

```python
    if kind == "workspace":
        from apore.domains.store import get_data_root

        assert secondary is not None
        chapter_root = get_data_root() / primary / "knowledge" / "chapters" / secondary
        if not chapter_root.is_dir():
            raise FileNotFoundError(f"Chapter not found: {chapter_root}")
        return ChapterContext(
            knowledge_source=knowledge_source,
            chapter_root=chapter_root,
            display_name=f"{primary} / {secondary}",
        )
```

(The local import avoids a package-level import cycle and keeps the knowledge layer usable without the domains package in legacy paths.)

`product/backend/scripts/seed_domain.py`:

```python
"""Seed a workspace domain with compiled curriculum (testbed helper).

Usage (from product/backend):
    python scripts/seed_domain.py <domain-id> [source-domain-id]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from apore.domains import seed, store  # noqa: E402

PROGRAM_ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    domain_id = sys.argv[1]
    source = sys.argv[2] if len(sys.argv) > 2 else "discrete-math"
    record = store.load_domain(domain_id)
    copied = seed.seed_domain(record, program_root=PROGRAM_ROOT, source_domain_id=source)
    print(f"Seeded {record.domain_id} with chapters: {copied or 'none (already seeded)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/domains -q` then `python -m pytest tests -q`
Expected: all PASS (legacy suite untouched).

- [ ] **Step 5: Commit**

```bash
git add product/backend/apore/domains/seed.py product/backend/apore/knowledge/chapter.py product/backend/scripts/seed_domain.py product/backend/tests/domains/test_seed_and_resolve.py
git commit -m "feat(backend): workspace knowledge resolution and testbed seeding"
```

---

### Task 3: Session files (`apore/domains/sessionfile.py`)

**Files:**
- Create: `product/backend/apore/domains/sessionfile.py`
- Create: `product/backend/tests/domains/test_sessionfile.py`

**Interfaces:**
- Consumes: `DomainRecord`, `sessions_dir` (Task 1); dataclasses `GeneratedQuestion`, `AssessmentResult`, `GradingResult` from `apore.runtime.core`.
- Produces (used by Tasks 6, 7):
  - Layout: `<domain>/sessions/<session_id>/session.json` + `<domain>/sessions/<session_id>/learner-state.md`
  - `class SessionFileError(Exception)` — corrupt/unreadable session.json.
  - `session_dir(record, session_id) -> Path`, `session_json_path(record, session_id) -> Path`, `learner_state_path(record, session_id) -> Path`
  - `create_session_file(record, *, session_id, title, knowledge_source, chapter_id, focus_mode, max_questions, created_at) -> dict`
  - `load_session_file(record, session_id) -> dict` (raises `FileNotFoundError` / `SessionFileError`)
  - `append_events(record, session_id, events: list[dict]) -> None` — each event dict gets a `ts` added if missing.
  - `write_resume(record, session_id, *, question_count: int, resume: dict | None) -> None`
  - `list_sessions(record) -> list[dict]` — summaries sorted newest-first: `{session_id, title, chapter_id, created_at, updated_at, question_count, max_questions, status}` where status is `"complete"` when `question_count >= max_questions` and resume is empty, else `"active"`. Unreadable session folders yield `status: "invalid"` entries.
  - Serialization helpers: `question_to_dict/question_from_dict`, `assessment_to_dict/assessment_from_dict`, `grading_to_dict/grading_from_dict` (thin `dataclasses.asdict` / constructor wrappers).
  - Resume snapshot shape (a plain dict, `None` when the session is at rest between questions):

```json
{
  "question_count": 3,
  "active_concept_id": "sets",
  "tutor_mode": false,
  "awaiting_skip_reason": false,
  "active_transcript": [{"role": "assistant", "content": "..."}],
  "pending_question": { "...GeneratedQuestion fields..." },
  "pending_grading": {
    "question": {"...GeneratedQuestion..."},
    "learner_response": "…",
    "assessment": {"...AssessmentResult..."},
    "dialogue_transcript": []
  },
  "reflection": {
    "question": {"...GeneratedQuestion..."},
    "assessment": {"...AssessmentResult..."},
    "grading": {"...GradingResult..."},
    "transcript": []
  }
}
```

  - Transcript event types (each has `type` and ISO `ts`): `question {question_number, question_id, concept_id, concept_label, question_text}`, `learner_message {text}`, `tutor_message {text}`, `graded {correct}`, `rating {rating, reward, new_difficulty}`, `system {text}`.

- [ ] **Step 1: Write the failing tests**

`product/backend/tests/domains/test_sessionfile.py`:

```python
import json

import pytest

from apore.domains import sessionfile, store
from apore.runtime.core import AssessmentResult, GeneratedQuestion, GradingResult


@pytest.fixture(autouse=True)
def data_root(tmp_path, monkeypatch):
    monkeypatch.setenv("APORE_DATA_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture()
def domain():
    return store.create_domain(
        name="T", objective="o", teaching_style="socratic",
        teaching_prompt="p", model_preference="auto",
    )


def _create(domain, session_id="sid-1"):
    return sessionfile.create_session_file(
        domain,
        session_id=session_id,
        title="Set Theory — Adaptive Practice",
        knowledge_source=f"workspace:{domain.domain_id}/01-set-theory",
        chapter_id="01-set-theory",
        focus_mode="adaptive",
        max_questions=10,
        created_at="2026-07-06T00:00:00+00:00",
    )


def test_create_and_load_roundtrip(domain):
    _create(domain)
    data = sessionfile.load_session_file(domain, "sid-1")
    assert data["session_id"] == "sid-1"
    assert data["title"].startswith("Set Theory")
    assert data["transcript"] == []
    assert data["resume"] is None
    assert sessionfile.session_dir(domain, "sid-1").is_dir()


def test_append_events_adds_ts_and_persists(domain):
    _create(domain)
    sessionfile.append_events(
        domain, "sid-1",
        [{"type": "question", "question_number": 1, "question_id": "q1",
          "concept_id": "sets", "concept_label": "Sets", "question_text": "?"}],
    )
    sessionfile.append_events(domain, "sid-1", [{"type": "learner_message", "text": "hi"}])
    data = sessionfile.load_session_file(domain, "sid-1")
    assert [e["type"] for e in data["transcript"]] == ["question", "learner_message"]
    assert all(e["ts"] for e in data["transcript"])


def test_resume_snapshot_roundtrip(domain):
    _create(domain)
    question = GeneratedQuestion(
        question_number=1, question_id="q1", concept_id="sets",
        concept_label="Sets", question_type="recall",
        intended_difficulty=0.5, question_text="?", gen_response="raw",
    )
    assessment = AssessmentResult(correct="yes", hint_count=0, turn_count=1, hedging_count=0)
    grading = GradingResult(
        question_number=1, explicit_rating="ok", correct="yes", hint_count=0,
        turn_count=1, hedging_count=0, reward=0.4, new_difficulty=0.55,
    )
    resume = {
        "question_count": 1,
        "active_concept_id": "sets",
        "tutor_mode": False,
        "awaiting_skip_reason": False,
        "active_transcript": [],
        "pending_question": None,
        "pending_grading": None,
        "reflection": {
            "question": sessionfile.question_to_dict(question),
            "assessment": sessionfile.assessment_to_dict(assessment),
            "grading": sessionfile.grading_to_dict(grading),
            "transcript": [],
        },
    }
    sessionfile.write_resume(domain, "sid-1", question_count=1, resume=resume)
    data = sessionfile.load_session_file(domain, "sid-1")
    restored = data["resume"]["reflection"]
    assert sessionfile.question_from_dict(restored["question"]) == question
    assert sessionfile.assessment_from_dict(restored["assessment"]) == assessment
    assert sessionfile.grading_from_dict(restored["grading"]) == grading
    assert data["question_count"] == 1


def test_list_sessions_sorted_and_status(domain):
    _create(domain, "sid-1")
    _create(domain, "sid-2")
    sessionfile.write_resume(domain, "sid-2", question_count=10, resume=None)
    summaries = sessionfile.list_sessions(domain)
    assert [s["session_id"] for s in summaries] == ["sid-2", "sid-1"]
    by_id = {s["session_id"]: s for s in summaries}
    assert by_id["sid-2"]["status"] == "complete"
    assert by_id["sid-1"]["status"] == "active"


def test_corrupt_session_json_raises(domain):
    _create(domain)
    sessionfile.session_json_path(domain, "sid-1").write_text("{broken", encoding="utf-8")
    with pytest.raises(sessionfile.SessionFileError):
        sessionfile.load_session_file(domain, "sid-1")


def test_corrupt_session_listed_as_invalid(domain):
    _create(domain, "sid-1")
    sessionfile.session_json_path(domain, "sid-1").write_text("{broken", encoding="utf-8")
    summaries = sessionfile.list_sessions(domain)
    assert summaries[0]["status"] == "invalid"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/domains/test_sessionfile.py -q`
Expected: FAIL with `cannot import name 'sessionfile'`.

- [ ] **Step 3: Implement**

`product/backend/apore/domains/sessionfile.py`:

```python
"""Per-session persistence inside a domain folder.

Each session is a folder: session.json (metadata + transcript + resume
snapshot) beside the runtime's learner-state.md. session.json is written
after every turn phase, so a crash loses at most the in-flight turn.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from apore.domains.store import DomainRecord, sessions_dir
from apore.runtime.core import AssessmentResult, GeneratedQuestion, GradingResult

SCHEMA_VERSION = 1


class SessionFileError(Exception):
    """session.json exists but cannot be parsed."""


def session_dir(record: DomainRecord, session_id: str) -> Path:
    return sessions_dir(record) / session_id


def session_json_path(record: DomainRecord, session_id: str) -> Path:
    return session_dir(record, session_id) / "session.json"


def learner_state_path(record: DomainRecord, session_id: str) -> Path:
    return session_dir(record, session_id) / "learner-state.md"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(record: DomainRecord, session_id: str, data: dict) -> None:
    data["updated_at"] = _now()
    session_json_path(record, session_id).write_text(
        json.dumps(data, indent=2), encoding="utf-8"
    )


def create_session_file(
    record: DomainRecord,
    *,
    session_id: str,
    title: str,
    knowledge_source: str,
    chapter_id: str,
    focus_mode: str,
    max_questions: int,
    created_at: str,
) -> dict:
    session_dir(record, session_id).mkdir(parents=True, exist_ok=True)
    data = {
        "schema_version": SCHEMA_VERSION,
        "session_id": session_id,
        "title": title,
        "knowledge_source": knowledge_source,
        "chapter_id": chapter_id,
        "focus_mode": focus_mode,
        "max_questions": max_questions,
        "created_at": created_at,
        "updated_at": created_at,
        "question_count": 0,
        "transcript": [],
        "resume": None,
    }
    _write(record, session_id, data)
    return data


def load_session_file(record: DomainRecord, session_id: str) -> dict:
    path = session_json_path(record, session_id)
    if not path.is_file():
        raise FileNotFoundError(f"Session {session_id!r} not found in {record.domain_id!r}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise SessionFileError(f"session.json unreadable: {exc}") from exc
    if not isinstance(data, dict) or "session_id" not in data:
        raise SessionFileError("session.json is missing required fields")
    return data


def append_events(record: DomainRecord, session_id: str, events: list[dict]) -> None:
    data = load_session_file(record, session_id)
    for event in events:
        event.setdefault("ts", _now())
        data["transcript"].append(event)
    _write(record, session_id, data)


def write_resume(
    record: DomainRecord,
    session_id: str,
    *,
    question_count: int,
    resume: dict | None,
) -> None:
    data = load_session_file(record, session_id)
    data["question_count"] = question_count
    data["resume"] = resume
    _write(record, session_id, data)


def list_sessions(record: DomainRecord) -> list[dict]:
    root = sessions_dir(record)
    if not root.is_dir():
        return []
    summaries: list[dict] = []
    for entry in root.iterdir():
        if not entry.is_dir():
            continue
        try:
            data = load_session_file(record, entry.name)
        except (FileNotFoundError, SessionFileError):
            summaries.append(
                {
                    "session_id": entry.name,
                    "title": entry.name,
                    "chapter_id": "",
                    "created_at": "",
                    "updated_at": "",
                    "question_count": 0,
                    "max_questions": 0,
                    "status": "invalid",
                }
            )
            continue
        complete = (
            data["question_count"] >= data["max_questions"] and not data["resume"]
        )
        summaries.append(
            {
                "session_id": data["session_id"],
                "title": data["title"],
                "chapter_id": data.get("chapter_id", ""),
                "created_at": data["created_at"],
                "updated_at": data["updated_at"],
                "question_count": data["question_count"],
                "max_questions": data["max_questions"],
                "status": "complete" if complete else "active",
            }
        )
    summaries.sort(key=lambda s: s["created_at"], reverse=True)
    return summaries


# --- dataclass serialization -------------------------------------------------

def question_to_dict(q: GeneratedQuestion) -> dict:
    return asdict(q)


def question_from_dict(d: dict) -> GeneratedQuestion:
    return GeneratedQuestion(**d)


def assessment_to_dict(a: AssessmentResult) -> dict:
    return asdict(a)


def assessment_from_dict(d: dict) -> AssessmentResult:
    return AssessmentResult(**d)


def grading_to_dict(g: GradingResult) -> dict:
    return asdict(g)


def grading_from_dict(d: dict) -> GradingResult:
    return GradingResult(**d)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/domains -q` — all PASS.

- [ ] **Step 5: Commit**

```bash
git add product/backend/apore/domains/sessionfile.py product/backend/tests/domains/test_sessionfile.py
git commit -m "feat(backend): per-session transcript and resume persistence"
```

---

### Task 4: Extract session flow from app.py (pure refactor)

**Files:**
- Create: `product/backend/apore/api/session_flow.py`
- Modify: `product/backend/apore/api/app.py`

**Interfaces:**
- Consumes: everything the current `post_question`/`post_turn` bodies use.
- Produces (used by Task 7):
  - `session_flow.SessionState`, `session_flow.PendingGrading`, `session_flow.ReflectionState` — the dataclasses currently defined in `app.py:84-125`, moved verbatim.
  - `session_flow.run_question(sess: SessionState, body: QuestionRequest, *, session_id: str, provider, model: str, metadata: dict, program_root: Path) -> QuestionResponse` — the body of `post_question` (`app.py:457-530`) minus the `_get_session` lookup and provider resolution (those become parameters).
  - `session_flow.run_turn(sess: SessionState, body: TurnRequest, *, session_id: str, provider, model: str, program_root: Path) -> TurnResponse` — the body of `post_turn` (`app.py:535-739`) minus lookup and provider resolution.
  - `session_flow.session_state_response(sess: SessionState) -> SessionStateResponse` — the current `_session_state_response`.
  - Helper moves (verbatim): `_grade_pending_dialogue`, `_turn_response_from_grading`, `_enter_reflection` (all already parameterized on `provider`/`model` or pure).

**No behavior change. No new tests. The gate is the existing suite.**

- [ ] **Step 1: Create `session_flow.py`**

Move from `app.py`, verbatim except as noted:
- The dataclasses `PendingGrading`, `ReflectionState`, `SessionState` (lines 84–125).
- `_session_state_response` → rename to `session_state_response` (public).
- `_grade_pending_dialogue`, `_turn_response_from_grading`, `_enter_reflection` — unchanged, but `_grade_pending_dialogue` and the flow functions take `program_root: Path` as a parameter instead of reading the module-level `PROGRAM_ROOT` (mechanical substitution: every `PROGRAM_ROOT` in the moved code becomes `program_root`).
- `run_question(...)`: the `post_question` body from the `if sess.pending_question is not None:` guard (line 458) through the final `return QuestionResponse(...)` (line 530), with these substitutions: the provider-resolution block (lines 479–487) is deleted (provider/model are parameters), `metadata = _build_metadata(sess)` is deleted (metadata is a parameter), `question_number = sess.question_count + 1` stays.
- `run_turn(...)`: the `post_turn` body from line 537 (`learner_message = ...`) through line 739, with `provider, model = _require_provider()` deleted (parameters) and `PROGRAM_ROOT` → `program_root`.

Module header + imports for `session_flow.py`:

```python
"""Tutoring session flow shared by legacy and domain-scoped routes.

Extracted verbatim from app.py so domain routes can wrap the same loop with
transcript persistence. Behavior must not diverge from the legacy routes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from fastapi import HTTPException

from apore.api.schemas import (
    QuestionRequest,
    QuestionResponse,
    SessionStateResponse,
    TurnRequest,
    TurnResponse,
)
from apore.knowledge.chapter import ChapterContext
from apore.runtime import state
from apore.runtime.core import (
    AssessmentResult,
    GeneratedQuestion,
    GradingResult,
    assess_response,
    finalize_turn,
    generate_question,
    grade_answer_turn,
    seed_dialogue_transcript,
    skip_prompt_message,
    tutor_turn,
)
from apore.runtime.intent import is_help_request
from apore.runtime.question_bank import QuestionBankExhaustedError
```

- [ ] **Step 2: Rewire `app.py`**

Replace the moved definitions with imports, and make the two route handlers thin delegates. In `app.py`:

```python
from apore.api.session_flow import (  # noqa: F401 - re-exported for tests/compat
    PendingGrading,
    ReflectionState,
    SessionState,
    run_question,
    run_turn,
    session_state_response,
)
```

New handler bodies (`create_session`, `_get_session`, `_require_provider`, `_build_metadata`, and the `sessions` dict all stay in `app.py` unchanged):

```python
@app.post("/sessions/{session_id}/question", response_model=QuestionResponse)
def post_question(session_id: str, body: QuestionRequest) -> QuestionResponse:
    sess = _get_session(session_id)
    provider, model = _require_provider()
    return run_question(
        sess,
        body,
        session_id=session_id,
        provider=provider,
        model=model,
        metadata=_build_metadata(sess),
        program_root=PROGRAM_ROOT,
    )


@app.post("/sessions/{session_id}/turn", response_model=TurnResponse)
def post_turn(session_id: str, body: TurnRequest) -> TurnResponse:
    sess = _get_session(session_id)
    provider, model = _require_provider()
    return run_turn(
        sess,
        body,
        session_id=session_id,
        provider=provider,
        model=model,
        program_root=PROGRAM_ROOT,
    )


@app.get("/sessions/{session_id}/state", response_model=SessionStateResponse)
def get_session_state(session_id: str) -> SessionStateResponse:
    return session_state_response(_get_session(session_id))
```

Note: `run_question` still needs the provider check to occur only when a question can actually be generated — the current code resolves the provider before the guards. Keep the current order: `_require_provider()` in the handler runs before `run_question`, matching today's behavior for `POST /question` (503 before 409 guards is NOT current behavior — today the guards run first at lines 458–477, then provider resolution at 479. Preserve that: in `run_question`, keep the guards at the top; in the handler call `_require_provider()` lazily by passing a `provider_factory` instead). **Simplest faithful structure:** `run_question(sess, body, *, session_id, provider_factory, metadata_factory, program_root)` where `provider_factory() -> tuple[provider, model]` is `_require_provider` and `metadata_factory() -> dict` is `lambda: _build_metadata(sess)`; `run_question` calls them exactly where the old code did. `run_turn` resolves `provider, model = provider_factory()` at the same point the old code called `_require_provider()` (line 557, after request validation). Use this factory signature — it keeps every status-code ordering identical.

- [ ] **Step 3: Run the full suite**

Run: `python -m pytest tests -q`
Expected: ALL PASS — this is a behavior-preserving refactor; any failure means the extraction diverged. Fix before proceeding.

- [ ] **Step 4: Commit**

```bash
git add product/backend/apore/api/session_flow.py product/backend/apore/api/app.py
git commit -m "refactor(backend): extract session flow for reuse by domain routes"
```

---

### Task 5: Domain API — schemas, router, /health testbed flag

**Files:**
- Modify: `product/backend/apore/api/schemas.py` (append workspace models)
- Create: `product/backend/apore/api/domain_routes.py`
- Modify: `product/backend/apore/api/app.py` (include router; extend `/health`)
- Create: `product/backend/tests/domains/test_domains_api.py`

**Interfaces:**
- Consumes: `store` (Task 1).
- Produces (used by Tasks 6–9 and the frontend):

Append to `schemas.py`:

```python
class WorkspaceDomainCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    objective: str = ""
    teaching_style: str = "socratic"
    teaching_prompt: str = ""
    model_preference: str = "auto"


class WorkspaceChapterSummary(BaseModel):
    id: str
    has_concept_graph: bool
    wiki_count: int
    has_question_bank: bool


class WorkspaceDomainSummary(BaseModel):
    id: str
    name: str
    objective: str
    teaching_style: str
    teaching_prompt: str
    model_preference: str
    created_at: str
    status: Literal["ready", "empty", "invalid"]
    reason: str | None = None
    chapters: list[WorkspaceChapterSummary] = []
    session_count: int = 0
    source_files: list[str] = []


class WorkspaceDomainListResponse(BaseModel):
    domains: list[WorkspaceDomainSummary]
```

- Router `domain_router = APIRouter(prefix="/domains", tags=["domains"])` with `GET ""`, `POST ""` (201), `GET "/{domain_id}"`.
- Domain status rule: `"invalid"` (with reason) from the scan; `"ready"` if at least one chapter under `knowledge/chapters/` has `concept-graph.json`; else `"empty"`.
- `GET /health` response gains `"testbed": bool` — true when `os.environ.get("APORE_TESTBED") == "1"`.

- [ ] **Step 1: Write the failing tests**

`product/backend/tests/domains/test_domains_api.py`:

```python
import json

import pytest
from fastapi.testclient import TestClient

from apore.api.app import app
from apore.domains import store

client = TestClient(app)


@pytest.fixture(autouse=True)
def data_root(tmp_path, monkeypatch):
    monkeypatch.setenv("APORE_DATA_DIR", str(tmp_path))
    return tmp_path


CREATE_BODY = {
    "name": "Discrete Math",
    "objective": "Proof-based CS foundations",
    "teaching_style": "socratic",
    "teaching_prompt": "Ask before answering.",
    "model_preference": "auto",
}


def test_create_domain_and_list():
    resp = client.post("/domains", json=CREATE_BODY)
    assert resp.status_code == 201
    created = resp.json()
    assert created["name"] == "Discrete Math"
    assert created["status"] == "empty"
    assert created["chapters"] == []

    listing = client.get("/domains")
    assert listing.status_code == 200
    ids = [d["id"] for d in listing.json()["domains"]]
    assert created["id"] in ids


def test_create_domain_requires_name():
    resp = client.post("/domains", json={**CREATE_BODY, "name": ""})
    assert resp.status_code == 422


def test_get_domain_detail_and_404():
    created = client.post("/domains", json=CREATE_BODY).json()
    detail = client.get(f"/domains/{created['id']}")
    assert detail.status_code == 200
    assert detail.json()["teaching_prompt"] == "Ask before answering."
    assert client.get("/domains/nope-0000").status_code == 404


def test_ready_status_when_chapter_has_graph():
    created = client.post("/domains", json=CREATE_BODY).json()
    record = store.load_domain(created["id"])
    chapter = store.chapters_dir(record) / "01-intro"
    (chapter / "wiki").mkdir(parents=True)
    (chapter / "wiki" / "sets.md").write_text("# Sets", encoding="utf-8")
    (chapter / "concept-graph.json").write_text(
        json.dumps({"nodes": [{"id": "sets"}], "edges": []}), encoding="utf-8"
    )
    detail = client.get(f"/domains/{created['id']}").json()
    assert detail["status"] == "ready"
    assert detail["chapters"] == [
        {"id": "01-intro", "has_concept_graph": True, "wiki_count": 1,
         "has_question_bank": False}
    ]


def test_invalid_folder_listed_with_reason(data_root):
    bad = data_root / "pasted-junk"
    bad.mkdir()
    listing = client.get("/domains").json()["domains"]
    entry = next(d for d in listing if d["id"] == "pasted-junk")
    assert entry["status"] == "invalid"
    assert entry["reason"]


def test_health_reports_testbed(monkeypatch):
    monkeypatch.delenv("APORE_TESTBED", raising=False)
    assert client.get("/health").json()["testbed"] is False
    monkeypatch.setenv("APORE_TESTBED", "1")
    assert client.get("/health").json()["testbed"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/domains/test_domains_api.py -q`
Expected: FAIL (404 on /domains routes; KeyError on testbed).

- [ ] **Step 3: Implement**

`product/backend/apore/api/domain_routes.py`:

```python
"""Domain-workspace HTTP surface: /domains."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from apore.api.schemas import (
    WorkspaceChapterSummary,
    WorkspaceDomainCreate,
    WorkspaceDomainListResponse,
    WorkspaceDomainSummary,
)
from apore.domains import store
from apore.domains.store import DomainRecord

domain_router = APIRouter(prefix="/domains", tags=["domains"])


def _chapter_summaries(record: DomainRecord) -> list[WorkspaceChapterSummary]:
    chapters_root = store.chapters_dir(record)
    if not chapters_root.is_dir():
        return []
    out: list[WorkspaceChapterSummary] = []
    for chapter in sorted(p for p in chapters_root.iterdir() if p.is_dir()):
        wiki = chapter / "wiki"
        out.append(
            WorkspaceChapterSummary(
                id=chapter.name,
                has_concept_graph=(chapter / "concept-graph.json").is_file(),
                wiki_count=(
                    len([p for p in wiki.iterdir() if p.is_file()])
                    if wiki.is_dir()
                    else 0
                ),
                has_question_bank=(chapter / "question-bank.json").is_file(),
            )
        )
    return out


def _summary(record: DomainRecord) -> WorkspaceDomainSummary:
    chapters = _chapter_summaries(record)
    status = "ready" if any(c.has_concept_graph for c in chapters) else "empty"
    sessions_root = store.sessions_dir(record)
    session_count = (
        len([p for p in sessions_root.iterdir() if p.is_dir()])
        if sessions_root.is_dir()
        else 0
    )
    sources_root = store.sources_dir(record)
    source_files = (
        sorted(p.name for p in sources_root.iterdir() if p.is_file())
        if sources_root.is_dir()
        else []
    )
    return WorkspaceDomainSummary(
        id=record.domain_id,
        name=record.name,
        objective=record.objective,
        teaching_style=record.teaching_style,
        teaching_prompt=record.teaching_prompt,
        model_preference=record.model_preference,
        created_at=record.created_at,
        status=status,
        chapters=chapters,
        session_count=session_count,
        source_files=source_files,
    )


def _invalid_summary(item: store.InvalidDomain) -> WorkspaceDomainSummary:
    return WorkspaceDomainSummary(
        id=item.domain_id,
        name=item.domain_id,
        objective="",
        teaching_style="",
        teaching_prompt="",
        model_preference="",
        created_at="",
        status="invalid",
        reason=item.reason,
    )


@domain_router.get("", response_model=WorkspaceDomainListResponse)
def list_domains() -> WorkspaceDomainListResponse:
    records, invalid = store.list_domains()
    return WorkspaceDomainListResponse(
        domains=[_summary(r) for r in records] + [_invalid_summary(i) for i in invalid]
    )


@domain_router.post("", response_model=WorkspaceDomainSummary, status_code=201)
def create_domain(body: WorkspaceDomainCreate) -> WorkspaceDomainSummary:
    record = store.create_domain(
        name=body.name,
        objective=body.objective,
        teaching_style=body.teaching_style,
        teaching_prompt=body.teaching_prompt,
        model_preference=body.model_preference,
    )
    return _summary(record)


def _load_or_404(domain_id: str) -> DomainRecord:
    try:
        return store.load_domain(domain_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=f"Domain is invalid: {exc}") from exc


@domain_router.get("/{domain_id}", response_model=WorkspaceDomainSummary)
def get_domain(domain_id: str) -> WorkspaceDomainSummary:
    return _summary(_load_or_404(domain_id))
```

In `app.py`: add `import os` (if absent), `from apore.api.domain_routes import domain_router`, then after the CORS middleware block: `app.include_router(domain_router)`. Extend `health()`:

```python
@app.get("/health")
def health() -> dict:
    """Lightweight reachability check used by the desktop shell on startup."""
    return {
        "status": "ok",
        "service": "apore-backend",
        "version": "0.1.0",
        "testbed": os.environ.get("APORE_TESTBED") == "1",
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/domains/test_domains_api.py -q` then `python -m pytest tests -q` — all PASS.

- [ ] **Step 5: Commit**

```bash
git add product/backend/apore/api/schemas.py product/backend/apore/api/domain_routes.py product/backend/apore/api/app.py product/backend/tests/domains/test_domains_api.py
git commit -m "feat(backend): /domains API with scan-based listing and testbed flag"
```

---

### Task 6: Domain sessions — create, list, detail

**Files:**
- Modify: `product/backend/apore/api/schemas.py` (append session models)
- Modify: `product/backend/apore/api/domain_routes.py`
- Modify: `product/backend/apore/runtime/session_meta.py` (2-line prefix addition)
- Create: `product/backend/tests/domains/conftest.py`
- Create: `product/backend/tests/domains/test_domain_sessions_api.py`

**Interfaces:**
- Consumes: `sessionfile` (Task 3), `session_flow.SessionState` (Task 4), `resolve_chapter` with `workspace:` (Task 2), `state.initialize`, `generate_session_title`, and from `app.py`: the shared `sessions` dict (import `apore.api.app` lazily inside handlers to avoid the import cycle — `from apore.api import app as app_module` at call time).
- Produces:

Append to `schemas.py`:

```python
class WorkspaceSessionCreateRequest(BaseModel):
    chapter_id: str | None = None
    focus_mode: str = "adaptive"
    max_questions: int = Field(default=10, ge=1, le=50)


class WorkspaceSessionSummary(BaseModel):
    session_id: str
    title: str
    chapter_id: str
    created_at: str
    updated_at: str
    question_count: int
    max_questions: int
    status: Literal["active", "complete", "invalid"]


class WorkspaceSessionListResponse(BaseModel):
    sessions: list[WorkspaceSessionSummary]


class WorkspaceSessionDetailResponse(BaseModel):
    session_id: str
    title: str
    chapter_id: str
    knowledge_source: str
    created_at: str
    updated_at: str
    question_count: int
    max_questions: int
    scalar: float
    phase: Literal["idle", "awaiting_answer", "awaiting_rating", "reflection", "complete"]
    transcript: list[dict]
```

- Routes on `domain_router`:
  - `POST /{domain_id}/sessions` → `CreateSessionResponse` (reuses the existing schema). Chapter default: first chapter (sorted) with `concept-graph.json`; 409 `"Domain has no compiled curriculum"` when none.
  - `GET /{domain_id}/sessions` → `WorkspaceSessionListResponse`.
  - `GET /{domain_id}/sessions/{session_id}` → `WorkspaceSessionDetailResponse`; 404 unknown, 409 corrupt (`SessionFileError`).
- Phase derivation from the session file: resume has `pending_grading` → `awaiting_rating`; resume has `reflection` → `reflection`; resume has `pending_question` → `awaiting_answer`; `question_count >= max_questions` → `complete`; else `idle`. Publish as helper `derive_phase(data: dict) -> str` in `domain_routes.py` (Task 7 reuses it).
- `session_meta.py` `_parse_domain_chapter`: also accept the `workspace:` prefix — add as the first branch:

```python
    if knowledge_source.startswith("workspace:"):
        rest = knowledge_source.split(":", 1)[1]
        if "/" in rest:
            domain_id, chapter_id = rest.split("/", 1)
            return domain_id, chapter_id
```

- [ ] **Step 1: Create the shared conftest, then write the failing tests**

`pytest_plugins` declarations are only honored in the root conftest, so the domain API tests reuse the stub-provider wiring by importing the fixtures. Create `product/backend/tests/domains/conftest.py`:

```python
"""Shared fixtures for domain-workspace tests.

Re-exports the api conftest's autouse fixtures so all tests in this package
get the _pytest minimal chapter and the stub-provider wiring, plus a tmp
APORE_DATA_DIR for every test.
"""

import pytest

# Autouse fixtures activate by being importable from this conftest.
from tests.api.conftest import ensure_test_chapter, reset_app_state  # noqa: F401


@pytest.fixture(autouse=True)
def data_root(tmp_path, monkeypatch):
    monkeypatch.setenv("APORE_DATA_DIR", str(tmp_path))
    return tmp_path
```

With this conftest in place, remove the per-file `data_root` fixtures from `test_store.py`, `test_seed_and_resolve.py`, `test_sessionfile.py`, and `test_domains_api.py` when convenient (they are now redundant but harmless — the conftest supersedes them; do delete them in this task to keep one source of truth). Note: `tests/domains/test_domains_api.py::test_health_reports_testbed` and the store tests are unaffected by the stub-provider fixtures.

`product/backend/tests/domains/test_domain_sessions_api.py`:

```python
import shutil

import pytest
from fastapi.testclient import TestClient

import apore.api.app as app_module
from apore.api.app import app
from apore.domains import store

client = TestClient(app)


@pytest.fixture()
def seeded_domain():
    resp = client.post(
        "/domains",
        json={"name": "Testbed", "objective": "o", "teaching_style": "socratic",
              "teaching_prompt": "p", "model_preference": "auto"},
    )
    record = store.load_domain(resp.json()["id"])
    src = app_module.PROGRAM_ROOT / "domains" / "_pytest" / "chapters" / "01-intro"
    dest = store.chapters_dir(record) / "01-intro"
    shutil.copytree(src, dest)
    return record


def test_create_session_defaults_to_first_ready_chapter(seeded_domain):
    resp = client.post(f"/domains/{seeded_domain.domain_id}/sessions", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert data["knowledge_source"] == f"workspace:{seeded_domain.domain_id}/01-intro"
    assert data["title"]
    # Files landed inside the domain
    session_dir = store.sessions_dir(seeded_domain) / data["session_id"]
    assert (session_dir / "session.json").is_file()
    assert (session_dir / "learner-state.md").is_file()


def test_create_session_empty_domain_409():
    resp = client.post(
        "/domains",
        json={"name": "Empty", "objective": "", "teaching_style": "socratic",
              "teaching_prompt": "", "model_preference": "auto"},
    )
    domain_id = resp.json()["id"]
    resp = client.post(f"/domains/{domain_id}/sessions", json={})
    assert resp.status_code == 409


def test_list_and_detail(seeded_domain):
    created = client.post(
        f"/domains/{seeded_domain.domain_id}/sessions", json={"max_questions": 5}
    ).json()
    listing = client.get(f"/domains/{seeded_domain.domain_id}/sessions").json()
    assert [s["session_id"] for s in listing["sessions"]] == [created["session_id"]]
    assert listing["sessions"][0]["status"] == "active"

    detail = client.get(
        f"/domains/{seeded_domain.domain_id}/sessions/{created['session_id']}"
    ).json()
    assert detail["phase"] == "idle"
    assert detail["transcript"] == []
    assert detail["max_questions"] == 5
    assert detail["scalar"] == 0.5


def test_detail_unknown_404(seeded_domain):
    resp = client.get(f"/domains/{seeded_domain.domain_id}/sessions/nope")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/domains/test_domain_sessions_api.py -q`
Expected: FAIL with 404s on the new routes.

- [ ] **Step 3: Implement**

Add to `domain_routes.py` (imports: `uuid`, `datetime/timezone`, `sessionfile`, `resolve_chapter`, `state`, `generate_session_title`, the new schemas, `CreateSessionResponse`, `SessionState` from `session_flow`):

```python
def _ready_chapter_ids(record: DomainRecord) -> list[str]:
    chapters_root = store.chapters_dir(record)
    if not chapters_root.is_dir():
        return []
    return sorted(
        p.name
        for p in chapters_root.iterdir()
        if p.is_dir() and (p / "concept-graph.json").is_file()
    )


def derive_phase(data: dict) -> str:
    resume = data.get("resume") or {}
    if resume.get("pending_grading"):
        return "awaiting_rating"
    if resume.get("reflection"):
        return "reflection"
    if resume.get("pending_question"):
        return "awaiting_answer"
    if data["question_count"] >= data["max_questions"]:
        return "complete"
    return "idle"


@domain_router.post("/{domain_id}/sessions", response_model=CreateSessionResponse)
def create_domain_session(
    domain_id: str, body: WorkspaceSessionCreateRequest
) -> CreateSessionResponse:
    from apore.api import app as app_module

    record = _load_or_404(domain_id)
    ready = _ready_chapter_ids(record)
    if not ready:
        raise HTTPException(status_code=409, detail="Domain has no compiled curriculum")
    chapter_id = body.chapter_id or ready[0]
    if chapter_id not in ready:
        raise HTTPException(status_code=404, detail=f"Chapter {chapter_id!r} not found")
    focus_mode = (body.focus_mode or "adaptive").strip().lower()
    if focus_mode not in ("adaptive", "weak_points"):
        raise HTTPException(
            status_code=400, detail='focus_mode must be "adaptive" or "weak_points"'
        )

    knowledge_source = f"workspace:{domain_id}/{chapter_id}"
    chapter = resolve_chapter(knowledge_source, app_module.PROGRAM_ROOT)

    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    provider_name = get_active_provider()
    provider = get_provider(provider_name) if provider_name else None
    model = get_active_model() or "stub-model"
    title = generate_session_title(
        chapter=chapter,
        knowledge_source=knowledge_source,
        focus_mode=focus_mode,  # type: ignore[arg-type]
        max_questions=body.max_questions,
        provider=provider,
        model=model,
        program_root=app_module.PROGRAM_ROOT,
    )

    state_path = sessionfile.learner_state_path(record, session_id)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state.initialize(
        state_path,
        title=title,
        session_id=session_id,
        created_at=now,
        knowledge_source=knowledge_source,
        focus_mode=focus_mode,
        max_questions=body.max_questions,
    )
    sessionfile.create_session_file(
        record,
        session_id=session_id,
        title=title,
        knowledge_source=knowledge_source,
        chapter_id=chapter_id,
        focus_mode=focus_mode,
        max_questions=body.max_questions,
        created_at=now,
    )

    app_module.sessions[session_id] = SessionState(
        session_id=session_id,
        title=title,
        knowledge_source=knowledge_source,
        chapter=chapter,
        state_path=state_path,
        scalar=0.5,
        question_count=0,
        created_at=now,
        focus_mode=focus_mode,
        max_questions=body.max_questions,
    )
    return CreateSessionResponse(
        session_id=session_id,
        title=title,
        scalar=0.5,
        created_at=now,
        knowledge_source=knowledge_source,
        focus_mode=focus_mode,
        max_questions=body.max_questions,
    )


@domain_router.get("/{domain_id}/sessions", response_model=WorkspaceSessionListResponse)
def list_domain_sessions(domain_id: str) -> WorkspaceSessionListResponse:
    record = _load_or_404(domain_id)
    return WorkspaceSessionListResponse(
        sessions=[WorkspaceSessionSummary(**s) for s in sessionfile.list_sessions(record)]
    )


@domain_router.get(
    "/{domain_id}/sessions/{session_id}",
    response_model=WorkspaceSessionDetailResponse,
)
def get_domain_session(domain_id: str, session_id: str) -> WorkspaceSessionDetailResponse:
    record = _load_or_404(domain_id)
    try:
        data = sessionfile.load_session_file(record, session_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except sessionfile.SessionFileError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    scalar = state.read_scalar(sessionfile.learner_state_path(record, session_id))
    return WorkspaceSessionDetailResponse(
        session_id=data["session_id"],
        title=data["title"],
        chapter_id=data.get("chapter_id", ""),
        knowledge_source=data["knowledge_source"],
        created_at=data["created_at"],
        updated_at=data["updated_at"],
        question_count=data["question_count"],
        max_questions=data["max_questions"],
        scalar=scalar,
        phase=derive_phase(data),
        transcript=data["transcript"],
    )
```

Apply the `session_meta.py` prefix addition shown in Interfaces. Provider imports for `domain_routes.py` come from `apore.config.llm` and `apore.providers` (`get_active_provider`, `get_active_model`, `get_provider`) — note the tests' conftest patches `app_module.get_active_provider`, which does not affect these direct imports; title generation falls back deterministically when the provider errors, which `generate_session_title` already handles (it catches provider failures — verify by reading `session_meta.py:generate_session_title` during implementation; if it does not catch, wrap the call in `try/except Exception` and use `fallback_session_title`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/domains -q` then `python -m pytest tests -q` — all PASS.

- [ ] **Step 5: Commit**

```bash
git add product/backend/apore/api/schemas.py product/backend/apore/api/domain_routes.py product/backend/apore/runtime/session_meta.py product/backend/tests/domains/test_domain_sessions_api.py
git commit -m "feat(backend): domain-scoped session create/list/detail"
```

---

### Task 7: Domain question/turn with persistence and rehydration

**Files:**
- Modify: `product/backend/apore/api/domain_routes.py`
- Create: `product/backend/tests/domains/test_domain_turn_resume.py`

**Interfaces:**
- Consumes: `run_question`/`run_turn` factory signatures (Task 4), `sessionfile` (Task 3), `derive_phase` (Task 6).
- Produces:
  - `POST /domains/{domain_id}/sessions/{session_id}/question` → `QuestionResponse`
  - `POST /domains/{domain_id}/sessions/{session_id}/turn` → `TurnResponse`
  - Rehydration: unknown in-memory session id + valid session.json → SessionState rebuilt and the request proceeds. Corrupt file → 409.
  - After every question/turn: transcript events appended and resume snapshot written.

- [ ] **Step 1: Write the failing test**

`product/backend/tests/domains/test_domain_turn_resume.py`:

```python
"""Full domain-scoped loop with the stub provider, including restart-resume."""

import shutil

import pytest
from fastapi.testclient import TestClient

import apore.api.app as app_module
from apore.api.app import app
from apore.domains import store

client = TestClient(app)


@pytest.fixture()
def domain_session():
    resp = client.post(
        "/domains",
        json={"name": "Testbed", "objective": "o", "teaching_style": "socratic",
              "teaching_prompt": "p", "model_preference": "auto"},
    )
    record = store.load_domain(resp.json()["id"])
    src = app_module.PROGRAM_ROOT / "domains" / "_pytest" / "chapters" / "01-intro"
    shutil.copytree(src, store.chapters_dir(record) / "01-intro")
    created = client.post(f"/domains/{record.domain_id}/sessions", json={}).json()
    return record, created["session_id"]


def _base(record, session_id):
    return f"/domains/{record.domain_id}/sessions/{session_id}"


def test_full_loop_persists_transcript(domain_session):
    record, sid = domain_session
    q = client.post(f"{_base(record, sid)}/question", json={})
    assert q.status_code == 200

    turn = client.post(f"{_base(record, sid)}/turn", json={"learner_message": "my answer"})
    assert turn.status_code == 200
    assert turn.json()["phase"] == "graded"

    detail = client.get(_base(record, sid)).json()
    assert detail["phase"] == "awaiting_rating"
    types = [e["type"] for e in detail["transcript"]]
    assert "question" in types
    assert "learner_message" in types
    assert "graded" in types

    rate = client.post(f"{_base(record, sid)}/turn", json={"explicit_rating": "ok"})
    assert rate.json()["phase"] == "reflection"
    detail = client.get(_base(record, sid)).json()
    assert detail["phase"] == "reflection"
    assert any(e["type"] == "rating" for e in detail["transcript"])

    cont = client.post(f"{_base(record, sid)}/turn", json={"continue": True})
    assert cont.json()["phase"] == "completed"
    detail = client.get(_base(record, sid)).json()
    assert detail["phase"] == "idle"


def test_resume_after_restart_mid_turn(domain_session):
    record, sid = domain_session
    client.post(f"{_base(record, sid)}/question", json={})
    client.post(f"{_base(record, sid)}/turn", json={"learner_message": "answer one"})

    # Simulate a backend restart: in-memory session map wiped.
    app_module.sessions.clear()

    # Detail still knows we're awaiting a rating…
    detail = client.get(_base(record, sid)).json()
    assert detail["phase"] == "awaiting_rating"

    # …and the loop continues from the rating step after rehydration.
    rate = client.post(f"{_base(record, sid)}/turn", json={"explicit_rating": "hard"})
    assert rate.status_code == 200
    assert rate.json()["phase"] == "reflection"
    cont = client.post(f"{_base(record, sid)}/turn", json={"continue": True})
    assert cont.json()["phase"] == "completed"

    # Next question also works post-restart.
    q2 = client.post(f"{_base(record, sid)}/question", json={})
    assert q2.status_code == 200
    assert q2.json()["question_number"] == 2


def test_corrupt_session_file_409(domain_session):
    record, sid = domain_session
    app_module.sessions.clear()
    from apore.domains import sessionfile

    sessionfile.session_json_path(record, sid).write_text("{broken", encoding="utf-8")
    resp = client.post(f"{_base(record, sid)}/question", json={})
    assert resp.status_code == 409
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/domains/test_domain_turn_resume.py -q`
Expected: FAIL with 404 (routes missing).

- [ ] **Step 3: Implement**

Add to `domain_routes.py`:

```python
def _snapshot(sess: SessionState) -> dict | None:
    if not (
        sess.pending_question or sess.pending_grading or sess.reflection
        or sess.active_transcript or sess.tutor_mode or sess.awaiting_skip_reason
    ):
        return None
    snap: dict = {
        "question_count": sess.question_count,
        "active_concept_id": sess.active_concept_id,
        "tutor_mode": sess.tutor_mode,
        "awaiting_skip_reason": sess.awaiting_skip_reason,
        "active_transcript": list(sess.active_transcript),
        "pending_question": (
            sessionfile.question_to_dict(sess.pending_question)
            if sess.pending_question else None
        ),
        "pending_grading": None,
        "reflection": None,
    }
    if sess.pending_grading:
        snap["pending_grading"] = {
            "question": sessionfile.question_to_dict(sess.pending_grading.question),
            "learner_response": sess.pending_grading.learner_response,
            "assessment": sessionfile.assessment_to_dict(sess.pending_grading.assessment),
            "dialogue_transcript": list(sess.pending_grading.dialogue_transcript),
        }
    if sess.reflection:
        snap["reflection"] = {
            "question": sessionfile.question_to_dict(sess.reflection.question),
            "assessment": sessionfile.assessment_to_dict(sess.reflection.assessment),
            "grading": sessionfile.grading_to_dict(sess.reflection.grading),
            "transcript": list(sess.reflection.transcript),
        }
    return snap


def _rehydrate(record: DomainRecord, session_id: str) -> SessionState:
    from apore.api import app as app_module

    try:
        data = sessionfile.load_session_file(record, session_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except sessionfile.SessionFileError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    state_path = sessionfile.learner_state_path(record, session_id)
    if not state_path.is_file():
        raise HTTPException(status_code=409, detail="learner-state.md missing for session")

    chapter = resolve_chapter(data["knowledge_source"], app_module.PROGRAM_ROOT)
    resume = data.get("resume") or {}
    sess = SessionState(
        session_id=session_id,
        title=data["title"],
        knowledge_source=data["knowledge_source"],
        chapter=chapter,
        state_path=state_path,
        scalar=state.read_scalar(state_path),
        question_count=resume.get("question_count", data["question_count"]),
        created_at=data["created_at"],
        focus_mode=data.get("focus_mode", "adaptive"),
        max_questions=data["max_questions"],
        asked_question_ids=state.read_asked_ids(state_path),
        active_transcript=list(resume.get("active_transcript") or []),
        awaiting_skip_reason=bool(resume.get("awaiting_skip_reason")),
        tutor_mode=bool(resume.get("tutor_mode")),
        active_concept_id=resume.get("active_concept_id"),
    )
    if resume.get("pending_question"):
        sess.pending_question = sessionfile.question_from_dict(resume["pending_question"])
    if resume.get("pending_grading"):
        pg = resume["pending_grading"]
        sess.pending_grading = PendingGrading(
            question=sessionfile.question_from_dict(pg["question"]),
            learner_response=pg["learner_response"],
            assessment=sessionfile.assessment_from_dict(pg["assessment"]),
            dialogue_transcript=list(pg.get("dialogue_transcript") or []),
        )
    if resume.get("reflection"):
        rf = resume["reflection"]
        sess.reflection = ReflectionState(
            question=sessionfile.question_from_dict(rf["question"]),
            assessment=sessionfile.assessment_from_dict(rf["assessment"]),
            grading=sessionfile.grading_from_dict(rf["grading"]),
            transcript=list(rf.get("transcript") or []),
        )
    app_module.sessions[session_id] = sess
    return sess


def _get_or_rehydrate(record: DomainRecord, session_id: str) -> SessionState:
    from apore.api import app as app_module

    sess = app_module.sessions.get(session_id)
    if sess is not None:
        return sess
    return _rehydrate(record, session_id)


def _persist(record: DomainRecord, sess: SessionState, events: list[dict]) -> None:
    if events:
        sessionfile.append_events(record, sess.session_id, events)
    sessionfile.write_resume(
        record, sess.session_id,
        question_count=sess.question_count,
        resume=_snapshot(sess),
    )


@domain_router.post(
    "/{domain_id}/sessions/{session_id}/question", response_model=QuestionResponse
)
def post_domain_question(
    domain_id: str, session_id: str, body: QuestionRequest
) -> QuestionResponse:
    from apore.api import app as app_module

    record = _load_or_404(domain_id)
    sess = _get_or_rehydrate(record, session_id)
    response = run_question(
        sess,
        body,
        session_id=session_id,
        provider_factory=app_module._require_provider,
        metadata_factory=lambda: app_module._build_metadata(sess),
        program_root=app_module.PROGRAM_ROOT,
    )
    _persist(record, sess, [{
        "type": "question",
        "question_number": response.question_number,
        "question_id": response.question_id,
        "concept_id": response.concept_id,
        "concept_label": response.concept_label,
        "question_text": response.question_text,
    }])
    return response


@domain_router.post(
    "/{domain_id}/sessions/{session_id}/turn", response_model=TurnResponse
)
def post_domain_turn(domain_id: str, session_id: str, body: TurnRequest) -> TurnResponse:
    from apore.api import app as app_module

    record = _load_or_404(domain_id)
    sess = _get_or_rehydrate(record, session_id)
    response = run_turn(
        sess,
        body,
        session_id=session_id,
        provider_factory=app_module._require_provider,
        program_root=app_module.PROGRAM_ROOT,
    )

    events: list[dict] = []
    learner_message = (body.learner_message or body.learner_response or "").strip()
    if learner_message:
        events.append({"type": "learner_message", "text": learner_message})
    if body.skip:
        events.append({"type": "system", "text": "Learner requested to skip."})
    if body.skip_reason:
        events.append({"type": "learner_message", "text": body.skip_reason.strip()})
    if response.tutor_message:
        events.append({"type": "tutor_message", "text": response.tutor_message})
    if response.phase == "graded":
        events.append({"type": "graded", "correct": response.correct})
    if response.phase == "reflection" and body.explicit_rating:
        events.append({
            "type": "rating",
            "rating": response.explicit_rating,
            "reward": response.reward,
            "new_difficulty": response.new_difficulty,
        })
    _persist(record, sess, events)
    return response
```

Required imports at the top of `domain_routes.py` grow to include: `sessionfile`, `resolve_chapter`, `state`, `QuestionRequest/QuestionResponse/TurnRequest/TurnResponse`, and `PendingGrading, ReflectionState, SessionState, run_question, run_turn` from `apore.api.session_flow`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/domains -q` then `python -m pytest tests -q` — all PASS.

- [ ] **Step 5: Commit**

```bash
git add product/backend/apore/api/domain_routes.py product/backend/tests/domains/test_domain_turn_resume.py
git commit -m "feat(backend): domain-scoped tutoring loop with transcripts and restart resume"
```

---

### Task 8: Gated seed endpoint

**Files:**
- Modify: `product/backend/apore/api/schemas.py`, `product/backend/apore/api/domain_routes.py`
- Create: `product/backend/tests/domains/test_seed_api.py`

**Interfaces:**
- Consumes: `seed.seed_domain` (Task 2).
- Produces: `POST /domains/{domain_id}/seed` — body `SeedRequest {source_domain_id: str = "discrete-math"}`, response `SeedResponse {chapters: list[str]}`. **404 unless env `APORE_TESTBED=1`.**

Schemas:

```python
class SeedRequest(BaseModel):
    source_domain_id: str = "discrete-math"


class SeedResponse(BaseModel):
    chapters: list[str]
```

- [ ] **Step 1: Write the failing tests**

`product/backend/tests/domains/test_seed_api.py`:

```python
import pytest
from fastapi.testclient import TestClient

import apore.api.app as app_module
from apore.api.app import app

client = TestClient(app)


@pytest.fixture()
def domain_id():
    resp = client.post(
        "/domains",
        json={"name": "T", "objective": "", "teaching_style": "socratic",
              "teaching_prompt": "", "model_preference": "auto"},
    )
    return resp.json()["id"]


def test_seed_404_without_testbed_env(domain_id, monkeypatch):
    monkeypatch.delenv("APORE_TESTBED", raising=False)
    resp = client.post(f"/domains/{domain_id}/seed", json={})
    assert resp.status_code == 404


def test_seed_copies_curriculum_with_testbed_env(domain_id, monkeypatch):
    monkeypatch.setenv("APORE_TESTBED", "1")
    resp = client.post(
        f"/domains/{domain_id}/seed", json={"source_domain_id": "_pytest"}
    )
    assert resp.status_code == 200
    assert resp.json()["chapters"] == ["01-intro"]
    detail = client.get(f"/domains/{domain_id}").json()
    assert detail["status"] == "ready"


def test_seed_unknown_source_404(domain_id, monkeypatch):
    monkeypatch.setenv("APORE_TESTBED", "1")
    resp = client.post(
        f"/domains/{domain_id}/seed", json={"source_domain_id": "no-such"}
    )
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/domains/test_seed_api.py -q` — FAIL (405/404 mismatch and missing route).

- [ ] **Step 3: Implement**

Add to `domain_routes.py` (`import os`, `from apore.domains import seed`):

```python
@domain_router.post("/{domain_id}/seed", response_model=SeedResponse)
def seed_domain_endpoint(domain_id: str, body: SeedRequest) -> SeedResponse:
    from apore.api import app as app_module

    if os.environ.get("APORE_TESTBED") != "1":
        # Invisible outside the testbed — indistinguishable from a missing route.
        raise HTTPException(status_code=404, detail="Not Found")
    record = _load_or_404(domain_id)
    try:
        chapters = seed.seed_domain(
            record,
            program_root=app_module.PROGRAM_ROOT,
            source_domain_id=body.source_domain_id,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SeedResponse(chapters=chapters)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests -q` — all PASS. Backend is now feature-complete for this slice.

- [ ] **Step 5: Commit**

```bash
git add product/backend/apore/api/schemas.py product/backend/apore/api/domain_routes.py product/backend/tests/domains/test_seed_api.py
git commit -m "feat(backend): testbed-gated domain seeding endpoint"
```

---

### Task 9: Frontend API types + client

**Files:**
- Modify: `product/frontend/src/api/types.ts` (append)
- Modify: `product/frontend/src/api/client.ts` (append)

**Interfaces:**
- Consumes: backend routes from Tasks 5–8.
- Produces (used by all later frontend tasks):

Append to `api/types.ts`:

```typescript
// --- Domain workspaces (mirrors Workspace* models in apore/api/schemas.py) ---

export interface WorkspaceChapter {
  id: string;
  has_concept_graph: boolean;
  wiki_count: number;
  has_question_bank: boolean;
}

export type DomainStatus = 'ready' | 'empty' | 'invalid';

export interface WorkspaceDomain {
  id: string;
  name: string;
  objective: string;
  teaching_style: string;
  teaching_prompt: string;
  model_preference: string;
  created_at: string;
  status: DomainStatus;
  reason: string | null;
  chapters: WorkspaceChapter[];
  session_count: number;
  source_files: string[];
}

export interface CreateDomainPayload {
  name: string;
  objective: string;
  teaching_style: string;
  teaching_prompt: string;
  model_preference: string;
}

export type SessionStatus = 'active' | 'complete' | 'invalid';

export interface WorkspaceSessionSummary {
  session_id: string;
  title: string;
  chapter_id: string;
  created_at: string;
  updated_at: string;
  question_count: number;
  max_questions: number;
  status: SessionStatus;
}

export type SessionPhase =
  | 'idle'
  | 'awaiting_answer'
  | 'awaiting_rating'
  | 'reflection'
  | 'complete';

export interface TranscriptEvent {
  type: 'question' | 'learner_message' | 'tutor_message' | 'graded' | 'rating' | 'system';
  ts: string;
  question_number?: number;
  question_id?: string;
  concept_id?: string;
  concept_label?: string;
  question_text?: string;
  text?: string;
  correct?: string;
  rating?: string;
  reward?: number | null;
  new_difficulty?: number | null;
}

export interface WorkspaceSessionDetail {
  session_id: string;
  title: string;
  chapter_id: string;
  knowledge_source: string;
  created_at: string;
  updated_at: string;
  question_count: number;
  max_questions: number;
  scalar: number;
  phase: SessionPhase;
  transcript: TranscriptEvent[];
}

export interface QuestionResponse {
  question_number: number;
  question_id: string;
  concept_id: string;
  concept_label: string;
  question_type: string;
  intended_difficulty: number;
  question_text: string;
}

export type TurnPhase =
  | 'dialogue'
  | 'skip_prompt'
  | 'graded'
  | 'reflection'
  | 'completed'
  | 'session_complete';

export interface TurnResponse {
  phase: TurnPhase;
  question_number: number;
  tutor_message: string | null;
  question_closed: boolean;
  correct: string;
  explicit_rating: string | null;
  reward: number | null;
  new_difficulty: number | null;
  flag_reason: string | null;
}

export interface ProviderConfigUpdate {
  anthropic_api_key?: string;
  nim_api_key?: string;
  model?: string;
}
```

Also extend `HealthResponse` with `testbed: boolean;`.

Append to `api/client.ts`:

```typescript
export function listDomains(): Promise<{ domains: WorkspaceDomain[] }> {
  return apiFetch('/domains');
}

export function createDomain(payload: CreateDomainPayload): Promise<WorkspaceDomain> {
  return apiFetch('/domains', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export function getDomain(domainId: string): Promise<WorkspaceDomain> {
  return apiFetch(`/domains/${domainId}`);
}

export function seedDomain(domainId: string): Promise<{ chapters: string[] }> {
  return apiFetch(`/domains/${domainId}/seed`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
}

export function listDomainSessions(
  domainId: string,
): Promise<{ sessions: WorkspaceSessionSummary[] }> {
  return apiFetch(`/domains/${domainId}/sessions`);
}

export function createDomainSession(
  domainId: string,
  body: { chapter_id?: string; max_questions?: number },
): Promise<CreateSessionResponse> {
  return apiFetch(`/domains/${domainId}/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export function getDomainSession(
  domainId: string,
  sessionId: string,
): Promise<WorkspaceSessionDetail> {
  return apiFetch(`/domains/${domainId}/sessions/${sessionId}`);
}

export function postDomainQuestion(
  domainId: string,
  sessionId: string,
): Promise<QuestionResponse> {
  return apiFetch(`/domains/${domainId}/sessions/${sessionId}/question`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
}

export function postDomainTurn(
  domainId: string,
  sessionId: string,
  body: {
    learner_message?: string;
    explicit_rating?: string;
    skip?: boolean;
    skip_reason?: string;
    continue?: boolean;
  },
): Promise<TurnResponse> {
  return apiFetch(`/domains/${domainId}/sessions/${sessionId}/turn`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export function updateProviderConfig(update: ProviderConfigUpdate): Promise<ProviderConfig> {
  return apiFetch('/config/provider', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(update),
  });
}
```

(Update the type-import block at the top of `client.ts` accordingly.)

- [ ] **Step 1: Make the changes above**
- [ ] **Step 2: Gate**

Run (from `product/frontend`): `npm run build`
Expected: clean tsc + vite build.

- [ ] **Step 3: Commit**

```bash
git add product/frontend/src/api/types.ts product/frontend/src/api/client.ts
git commit -m "feat(frontend): workspace API types and client functions"
```

---

### Task 10: Navigation + shell restructure (App, Sidebar, Workspace, hooks)

**Files:**
- Modify: `product/frontend/src/types.ts` (replace contents)
- Create: `product/frontend/src/hooks/useDomains.ts`
- Create: `product/frontend/src/hooks/useDomainSessions.ts`
- Modify: `product/frontend/src/App.tsx`
- Rewrite: `product/frontend/src/components/Sidebar.tsx`
- Modify: `product/frontend/src/components/Workspace.tsx`

**Interfaces:**
- Consumes: `listDomains`, `listDomainSessions` (Task 9).
- Produces (used by Tasks 11, 13, 15):

`src/types.ts` (full replacement):

```typescript
export type DomainTab = 'chat' | 'sources' | 'graph' | 'scratchpad';

export type AppView =
  | { kind: 'create-domain' }
  | { kind: 'domain'; domainId: string; tab: DomainTab; sessionId: string | null };

export const TAB_LABELS: Record<DomainTab, string> = {
  chat: 'Tutor Chat',
  sources: 'Sources',
  graph: 'Curriculum Graph',
  scratchpad: 'Scratchpad',
};
```

`src/hooks/useDomains.ts`:

```typescript
import { useCallback, useEffect, useState } from 'react';
import { listDomains } from '../api/client';
import type { WorkspaceDomain } from '../api/types';

export interface DomainsState {
  domains: WorkspaceDomain[];
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

export function useDomains(backendOnline: boolean): DomainsState {
  const [domains, setDomains] = useState<WorkspaceDomain[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  const refresh = useCallback(() => setTick((v) => v + 1), []);

  useEffect(() => {
    if (!backendOnline) return;
    let cancelled = false;
    setLoading(true);
    listDomains()
      .then((result) => {
        if (cancelled) return;
        setDomains(result.domains);
        setError(null);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [backendOnline, tick]);

  return { domains, loading, error, refresh };
}
```

`src/hooks/useDomainSessions.ts` — same shape for `listDomainSessions(domainId)`:

```typescript
import { useCallback, useEffect, useState } from 'react';
import { listDomainSessions } from '../api/client';
import type { WorkspaceSessionSummary } from '../api/types';

export interface DomainSessionsState {
  sessions: WorkspaceSessionSummary[];
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

export function useDomainSessions(domainId: string | null): DomainSessionsState {
  const [sessions, setSessions] = useState<WorkspaceSessionSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  const refresh = useCallback(() => setTick((v) => v + 1), []);

  useEffect(() => {
    if (!domainId) {
      setSessions([]);
      return;
    }
    let cancelled = false;
    setLoading(true);
    listDomainSessions(domainId)
      .then((result) => {
        if (cancelled) return;
        setSessions(result.sessions);
        setError(null);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [domainId, tick]);

  return { sessions, loading, error, refresh };
}
```

`src/App.tsx` (full replacement):

```typescript
import { useEffect, useState } from 'react';
import { DesktopTitlebar } from './components/DesktopTitlebar';
import { Sidebar } from './components/Sidebar';
import { Workspace } from './components/Workspace';
import { AssistantPanel } from './components/AssistantPanel';
import { SettingsModal } from './components/SettingsModal';
import { useBackend } from './hooks/useBackend';
import { useDomains } from './hooks/useDomains';
import { useDomainSessions } from './hooks/useDomainSessions';
import type { AppView } from './types';

export function App() {
  const backend = useBackend();
  const domainsState = useDomains(backend.status === 'online');
  const [view, setView] = useState<AppView>({ kind: 'create-domain' });
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [initialized, setInitialized] = useState(false);

  const activeDomainId = view.kind === 'domain' ? view.domainId : null;
  const sessionsState = useDomainSessions(activeDomainId);

  // First load: land on the first usable domain, else the create screen.
  useEffect(() => {
    if (initialized || domainsState.loading || backend.status !== 'online') return;
    const first = domainsState.domains.find((d) => d.status !== 'invalid');
    if (first) {
      setView({ kind: 'domain', domainId: first.id, tab: 'chat', sessionId: null });
    }
    setInitialized(true);
  }, [initialized, domainsState.loading, domainsState.domains, backend.status]);

  const isChatView = view.kind === 'domain' && view.tab === 'chat';

  return (
    <div className="page">
      <DesktopTitlebar
        status={backend.status}
        onRefresh={() => {
          backend.refresh();
          domainsState.refresh();
        }}
        onOpenSettings={() => setSettingsOpen(true)}
      />

      <div className={`app-shell${isChatView ? ' is-chat-view' : ''}`}>
        <Sidebar
          domains={domainsState.domains}
          sessions={sessionsState.sessions}
          view={view}
          onNavigate={setView}
        />
        <Workspace
          view={view}
          backend={backend}
          domains={domainsState.domains}
          onNavigate={setView}
          onDomainsChanged={domainsState.refresh}
          onSessionsChanged={sessionsState.refresh}
        />
        {!isChatView && <AssistantPanel />}
      </div>

      {settingsOpen && (
        <SettingsModal
          provider={backend.provider}
          onClose={() => setSettingsOpen(false)}
          onSaved={backend.refresh}
        />
      )}
    </div>
  );
}
```

(`SettingsModal` arrives in Task 14 — until then, create a placeholder file exporting a component that returns `null`, so the shell compiles; Task 14 replaces it. `DesktopTitlebar` gains the `onOpenSettings` prop in Task 14; for this task add the prop to its interface and render nothing new yet — a prop pass-through keeps this task compiling without UI change. `AssistantPanel` prop change happens in Task 15; for now change its usage to no-props and adjust its signature to accept none.)

`src/components/Sidebar.tsx` (full replacement):

```typescript
import type { WorkspaceDomain, WorkspaceSessionSummary } from '../api/types';
import type { AppView } from '../types';

interface SidebarProps {
  domains: WorkspaceDomain[];
  sessions: WorkspaceSessionSummary[];
  view: AppView;
  onNavigate: (view: AppView) => void;
}

export function Sidebar({ domains, sessions, view, onNavigate }: SidebarProps) {
  const activeDomainId = view.kind === 'domain' ? view.domainId : null;

  return (
    <aside className="sidebar">
      <div className="domain-list">
        {domains.length === 0 && (
          <p className="domain-meta" style={{ padding: '8px 4px' }}>
            No domains yet. Create your first learning domain to get started.
          </p>
        )}

        {domains.map((domain) => (
          <DomainCard
            key={domain.id}
            domain={domain}
            active={domain.id === activeDomainId}
            sessions={domain.id === activeDomainId ? sessions : []}
            view={view}
            onNavigate={onNavigate}
          />
        ))}

        <button
          className="button-secondary"
          onClick={() => onNavigate({ kind: 'create-domain' })}
        >
          New domain
        </button>
      </div>
    </aside>
  );
}

function DomainCard({
  domain,
  active,
  sessions,
  view,
  onNavigate,
}: {
  domain: WorkspaceDomain;
  active: boolean;
  sessions: WorkspaceSessionSummary[];
  view: AppView;
  onNavigate: (view: AppView) => void;
}) {
  if (domain.status === 'invalid') {
    return (
      <section className="domain-card">
        <div className="domain-row">
          <div>
            <div className="domain-name">{domain.id}</div>
            <div className="domain-meta">Invalid folder: {domain.reason}</div>
          </div>
        </div>
      </section>
    );
  }

  const activeSessionId =
    view.kind === 'domain' && view.domainId === domain.id ? view.sessionId : null;
  const activeTab = view.kind === 'domain' && view.domainId === domain.id ? view.tab : null;

  const open = (tab: 'chat' | 'sources' | 'graph' | 'scratchpad', sessionId: string | null = null) =>
    onNavigate({ kind: 'domain', domainId: domain.id, tab, sessionId });

  return (
    <section className={`domain-card${active ? ' is-active' : ''}`}>
      <button className="domain-row" onClick={() => open('chat')}>
        <div>
          <div className="domain-name">{domain.name}</div>
          <div className="domain-meta">
            {domain.status === 'empty'
              ? 'No curriculum compiled yet'
              : `${domain.chapters.length} chapter${domain.chapters.length === 1 ? '' : 's'}`}
          </div>
        </div>
      </button>

      {active && (
        <div className="tree">
          <div className="tree-row is-heading">
            <span>Session History</span>
            <span className="tree-count">{sessions.length}</span>
          </div>
          <button
            className={`tree-row${activeTab === 'chat' && activeSessionId === null ? ' is-active' : ''}`}
            onClick={() => open('chat')}
          >
            <span className="tree-icon">+</span>
            <span>New session</span>
            <span />
          </button>
          {sessions.map((session) => (
            <button
              key={session.session_id}
              className={`tree-row${activeSessionId === session.session_id ? ' is-active' : ''}`}
              onClick={() => open('chat', session.session_id)}
              disabled={session.status === 'invalid'}
            >
              <span className="tree-icon">C</span>
              <span>{session.title}</span>
              <span className="tree-count">
                {session.status === 'complete' ? 'done' : `${session.question_count}/${session.max_questions}`}
              </span>
            </button>
          ))}

          <button
            className={`tree-row${activeTab === 'sources' ? ' is-active' : ''}`}
            onClick={() => open('sources')}
          >
            <span className="tree-icon">S</span>
            <span>Sources</span>
            <span className="tree-count">{domain.source_files.length}</span>
          </button>
          <button
            className={`tree-row${activeTab === 'graph' ? ' is-active' : ''}`}
            onClick={() => open('graph')}
          >
            <span className="tree-icon">G</span>
            <span>Curriculum Graph</span>
            <span />
          </button>
          <button
            className={`tree-row${activeTab === 'scratchpad' ? ' is-active' : ''}`}
            onClick={() => open('scratchpad')}
          >
            <span className="tree-icon">P</span>
            <span>Scratchpad</span>
            <span />
          </button>
        </div>
      )}
    </section>
  );
}
```

`src/components/Workspace.tsx` (full replacement — ChatView props land in Task 13; until then pass nothing and keep the current static `ChatView` import compiling by updating it in Task 13):

```typescript
import { TAB_LABELS, type AppView } from '../types';
import type { BackendState } from '../hooks/useBackend';
import type { WorkspaceDomain } from '../api/types';
import { CreateDomainView } from './views/CreateDomainView';
import { SourcesView } from './views/SourcesView';
import { ChatView } from './views/ChatView';
import { ScratchpadView } from './views/ScratchpadView';
import { GraphView } from './views/GraphView';

interface WorkspaceProps {
  view: AppView;
  backend: BackendState;
  domains: WorkspaceDomain[];
  onNavigate: (view: AppView) => void;
  onDomainsChanged: () => void;
  onSessionsChanged: () => void;
}

export function Workspace({
  view,
  backend,
  domains,
  onNavigate,
  onDomainsChanged,
  onSessionsChanged,
}: WorkspaceProps) {
  const domain =
    view.kind === 'domain' ? domains.find((d) => d.id === view.domainId) ?? null : null;
  const title =
    view.kind === 'create-domain'
      ? 'New Learning Domain'
      : `${domain?.name ?? view.domainId} — ${TAB_LABELS[view.tab]}`;

  return (
    <main className="workspace">
      <div className="tab-bar">
        <button className="tab is-active">{title}</button>
      </div>

      <section className="stage">
        {view.kind === 'create-domain' && (
          <CreateDomainView
            backend={backend}
            onCreated={(created) => {
              onDomainsChanged();
              onNavigate({ kind: 'domain', domainId: created.id, tab: 'chat', sessionId: null });
            }}
            onCancel={
              domains.length > 0
                ? () =>
                    onNavigate({
                      kind: 'domain',
                      domainId: domains[0].id,
                      tab: 'chat',
                      sessionId: null,
                    })
                : null
            }
          />
        )}
        {view.kind === 'domain' && domain && view.tab === 'chat' && (
          <ChatView
            domain={domain}
            sessionId={view.sessionId}
            backend={backend}
            onSessionCreated={(sessionId) => {
              onSessionsChanged();
              onNavigate({ ...view, sessionId });
            }}
          />
        )}
        {view.kind === 'domain' && domain && view.tab === 'sources' && (
          <SourcesView domain={domain} />
        )}
        {view.kind === 'domain' && domain && view.tab === 'scratchpad' && <ScratchpadView />}
        {view.kind === 'domain' && domain && view.tab === 'graph' && <GraphView domain={domain} />}
      </section>
    </main>
  );
}
```

**Sequencing note:** this task changes props consumed by `CreateDomainView` (Task 11), `ChatView` (Task 13), `SourcesView`/`GraphView` (Task 15). To keep every commit compiling, in THIS task update those four components' prop signatures minimally (accept the new props, keep rendering their current bodies, ignore unused props with a leading underscore or `void` reference). Their real rewrites land in their own tasks.

- [ ] **Step 1: Apply all file changes above (including minimal prop-signature updates + placeholder SettingsModal)**
- [ ] **Step 2: Gate**

Run: `npm run build` — clean. Then `npm run dev` with the backend running: sidebar shows real domains (empty list + create prompt on a fresh data root), New domain navigates to the create view.

- [ ] **Step 3: Commit**

```bash
git add product/frontend/src
git commit -m "feat(frontend): domain-aware navigation and real sidebar"
```

---

### Task 11: Wire CreateDomainView

**Files:**
- Modify: `product/frontend/src/components/views/CreateDomainView.tsx`
- Delete: `product/frontend/src/components/BackendOverview.tsx`

**Interfaces:**
- Consumes: `createDomain` (Task 9); props `onCreated: (d: WorkspaceDomain) => void`, `onCancel: (() => void) | null` (Task 10).
- Produces: a working create form. `BackendOverview` is deleted (its import in `CreateDomainView` goes away; nothing else imports it).

- [ ] **Step 1: Rewrite the component**

Keep `TEACHING_PROMPTS` and `STYLE_CARDS` exactly as they are. Replace the component body:

```typescript
export function CreateDomainView({
  backend,
  onCreated,
  onCancel,
}: {
  backend: BackendState;
  onCreated: (domain: WorkspaceDomain) => void;
  onCancel: (() => void) | null;
}) {
  const [style, setStyle] = useState<StyleId>('socratic');
  const [prompt, setPrompt] = useState(TEACHING_PROMPTS.socratic.text);
  const [name, setName] = useState('');
  const [objective, setObjective] = useState('');
  const [model, setModel] = useState('auto');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectStyle = (id: StyleId) => {
    setStyle(id);
    setPrompt(TEACHING_PROMPTS[id].text);
  };

  const modelOptions = ['auto'];
  if (backend.provider?.active_model) modelOptions.push(backend.provider.active_model);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!name.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      const created = await createDomain({
        name: name.trim(),
        objective: objective.trim(),
        teaching_style: style,
        teaching_prompt: prompt,
        model_preference: model,
      });
      onCreated(created);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setBusy(false);
    }
  }

  return (
    <section className="view">
      {backend.status === 'offline' && (
        <div className="alert is-error">
          Backend offline. Start it with{' '}
          <span className="inline-code">uvicorn apore.api.app:app --port 8000</span> from{' '}
          <span className="inline-code">product/backend</span>.
        </div>
      )}

      <article className="domain-create panel">
        <div className="screen-intro">
          <div>
            <p className="eyebrow">Domain scaffold</p>
            <h1>Create learning domain</h1>
            <p>
              Creates a self-contained folder under your Apore data directory. The name
              organizes the sidebar; the learning objective tells Apore what this domain
              should become teachable as.
            </p>
          </div>
        </div>

        <form className="domain-form" onSubmit={submit}>
          <label className="field">
            <span className="label">Domain name</span>
            <input
              className="input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Discrete Math"
            />
            <p className="help">Organizational label in the left sidebar.</p>
          </label>

          <label className="field">
            <span className="label">Model</span>
            <select className="select" value={model} onChange={(e) => setModel(e.target.value)}>
              {modelOptions.map((option) => (
                <option key={option} value={option}>{option}</option>
              ))}
            </select>
            <p className="help">
              {backend.provider?.active_provider
                ? `Active provider: ${backend.provider.active_provider}`
                : 'No provider configured yet — add a key in Settings.'}
            </p>
          </label>

          <label className="field is-wide">
            <span className="label">What are you trying to learn?</span>
            <input
              className="input"
              value={objective}
              onChange={(e) => setObjective(e.target.value)}
              placeholder="I want to learn discrete mathematics for proof-based computer science."
            />
          </label>

          <div className="choice-grid">
            {STYLE_CARDS.map((card) => (
              <button
                key={card.id}
                type="button"
                className={`choice-card${style === card.id ? ' is-selected' : ''}`}
                onClick={() => selectStyle(card.id)}
              >
                <strong>{card.title}</strong>
                <span>{card.blurb}</span>
              </button>
            ))}
          </div>

          <label className="prompt-preview">
            <span className="prompt-preview-header">
              <span className="prompt-preview-title">Teaching prompt</span>
              <span className="prompt-preview-meta">{TEACHING_PROMPTS[style].meta}</span>
            </span>
            <textarea
              className="prompt-editor"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
            />
          </label>

          {error && <div className="alert is-error">{error}</div>}

          <div className="form-footer">
            {onCancel && (
              <button type="button" className="button-secondary" onClick={onCancel}>
                Cancel
              </button>
            )}
            <button
              type="submit"
              className="button-primary"
              disabled={!name.trim() || busy || backend.status !== 'online'}
            >
              {busy ? 'Creating…' : 'Create domain'}
            </button>
          </div>
        </form>
      </article>
    </section>
  );
}
```

Imports: `useState, type FormEvent` from react; `createDomain` from `../../api/client`; `WorkspaceDomain` from `../../api/types`; `BackendState` from `../../hooks/useBackend`. Remove the `BackendOverview` import and delete `BackendOverview.tsx`. The fake "Preview manifest" button is removed (honest-UI rule).

- [ ] **Step 2: Gate**

`npm run build` clean. Manual: create a domain against the running backend → folder appears under the data root, sidebar shows it, app navigates into it.

- [ ] **Step 3: Commit**

```bash
git add -A product/frontend/src
git commit -m "feat(frontend): working create-domain form; retire BackendOverview"
```

---

### Task 12: Chat state machine (pure) + Vitest

**Files:**
- Modify: `product/frontend/package.json` (add vitest devDependency + test script)
- Create: `product/frontend/src/chat/machine.ts`
- Create: `product/frontend/src/chat/machine.test.ts`

**Interfaces:**
- Consumes: `TranscriptEvent`, `TurnResponse`, `SessionPhase`, `WorkspaceSessionDetail`, `QuestionResponse` (Task 9).
- Produces (used by Task 13):

```typescript
export type ChatStatus =
  | 'boot'            // loading detail or creating session
  | 'loading_question'
  | 'awaiting_answer'
  | 'working'         // turn request in flight
  | 'awaiting_rating'
  | 'reflection'
  | 'complete'
  | 'error';

export interface ChatState {
  status: ChatStatus;
  transcript: TranscriptEvent[];
  questionsAsked: number;
  maxQuestions: number;
  scalar: number;
  error: string | null;
  // status to return to after a failed request is retried/dismissed
  errorRecovery: ChatStatus;
}

export type ChatAction =
  | { type: 'detail_loaded'; detail: WorkspaceSessionDetail }
  | { type: 'question_requested' }
  | { type: 'question_received'; question: QuestionResponse }
  | { type: 'message_sent'; text: string }
  | { type: 'rating_sent'; rating: string }
  | { type: 'continue_sent' }
  | { type: 'turn_result'; result: TurnResponse; localEvents: TranscriptEvent[] }
  | { type: 'request_failed'; message: string }
  | { type: 'error_dismissed' };

export function initialChatState(): ChatState;
export function chatReducer(state: ChatState, action: ChatAction): ChatState;
```

Mapping rules the reducer implements:
- `detail_loaded`: transcript/scalar/counters from detail; status from `detail.phase`: `idle→loading_question` is NOT automatic — `idle` maps to `loading_question` only via the hook; reducer maps `idle→awaiting_answer`? **No — exact mapping:** `idle → 'loading_question'` (hook will fire the question request), `awaiting_answer → 'awaiting_answer'`, `awaiting_rating → 'awaiting_rating'`, `reflection → 'reflection'`, `complete → 'complete'`.
- `question_received`: appends a `question` transcript event built from the QuestionResponse, `questionsAsked = question.question_number`, status `awaiting_answer`.
- `message_sent` / `rating_sent` / `continue_sent`: append optimistic local events (`learner_message` for message; nothing for continue; `rating` events come from `turn_result`), status `working`, remembering the prior status in `errorRecovery`.
- `turn_result`: append `localEvents` (built by the hook from the response: `tutor_message`, `graded`, `rating`), then status by `result.phase`: `dialogue|skip_prompt → awaiting_answer`, `graded → awaiting_rating`, `reflection → reflection` (and update `scalar` from `result.new_difficulty` when non-null), `completed → loading_question`, `session_complete → complete`.
- `request_failed`: status `error`, keep `errorRecovery`.
- `error_dismissed`: status = `errorRecovery`.

- [ ] **Step 1: Add Vitest**

In `package.json` devDependencies add `"vitest": "^2"`; scripts add `"test": "vitest run"`. Run `npm install`.

- [ ] **Step 2: Write the failing tests**

`product/frontend/src/chat/machine.test.ts`:

```typescript
import { describe, expect, it } from 'vitest';
import { chatReducer, initialChatState, type ChatState } from './machine';
import type { QuestionResponse, TurnResponse, WorkspaceSessionDetail } from '../api/types';

const question: QuestionResponse = {
  question_number: 1,
  question_id: 'q1',
  concept_id: 'sets',
  concept_label: 'Sets',
  question_type: 'recall',
  intended_difficulty: 0.5,
  question_text: 'What is a set?',
};

function detail(phase: WorkspaceSessionDetail['phase']): WorkspaceSessionDetail {
  return {
    session_id: 's1', title: 'T', chapter_id: '01', knowledge_source: 'workspace:d/01',
    created_at: '', updated_at: '', question_count: 1, max_questions: 10,
    scalar: 0.5, phase, transcript: [],
  };
}

function turn(phase: TurnResponse['phase'], extra: Partial<TurnResponse> = {}): TurnResponse {
  return {
    phase, question_number: 1, tutor_message: 'msg', question_closed: false,
    correct: 'yes', explicit_rating: null, reward: null, new_difficulty: null,
    flag_reason: null, ...extra,
  };
}

describe('chatReducer', () => {
  it('maps loaded detail phases to statuses', () => {
    expect(chatReducer(initialChatState(), { type: 'detail_loaded', detail: detail('idle') }).status)
      .toBe('loading_question');
    expect(chatReducer(initialChatState(), { type: 'detail_loaded', detail: detail('awaiting_rating') }).status)
      .toBe('awaiting_rating');
    expect(chatReducer(initialChatState(), { type: 'detail_loaded', detail: detail('reflection') }).status)
      .toBe('reflection');
    expect(chatReducer(initialChatState(), { type: 'detail_loaded', detail: detail('complete') }).status)
      .toBe('complete');
  });

  it('runs the happy path: question -> answer -> graded -> rating -> reflection -> continue -> next question', () => {
    let state: ChatState = chatReducer(initialChatState(), {
      type: 'detail_loaded', detail: detail('idle'),
    });
    state = chatReducer(state, { type: 'question_received', question });
    expect(state.status).toBe('awaiting_answer');
    expect(state.transcript.at(-1)?.type).toBe('question');

    state = chatReducer(state, { type: 'message_sent', text: 'a set is a collection' });
    expect(state.status).toBe('working');
    expect(state.transcript.at(-1)?.type).toBe('learner_message');

    state = chatReducer(state, {
      type: 'turn_result',
      result: turn('graded'),
      localEvents: [
        { type: 'tutor_message', ts: '', text: 'feedback' },
        { type: 'graded', ts: '', correct: 'yes' },
      ],
    });
    expect(state.status).toBe('awaiting_rating');

    state = chatReducer(state, { type: 'rating_sent', rating: 'ok' });
    expect(state.status).toBe('working');
    state = chatReducer(state, {
      type: 'turn_result',
      result: turn('reflection', { new_difficulty: 0.55 }),
      localEvents: [{ type: 'rating', ts: '', rating: 'ok', reward: 0.4, new_difficulty: 0.55 }],
    });
    expect(state.status).toBe('reflection');
    expect(state.scalar).toBe(0.55);

    state = chatReducer(state, { type: 'continue_sent' });
    state = chatReducer(state, { type: 'turn_result', result: turn('completed'), localEvents: [] });
    expect(state.status).toBe('loading_question');
  });

  it('session_complete ends the session', () => {
    let state = chatReducer(initialChatState(), { type: 'detail_loaded', detail: detail('reflection') });
    state = chatReducer(state, { type: 'continue_sent' });
    state = chatReducer(state, { type: 'turn_result', result: turn('session_complete'), localEvents: [] });
    expect(state.status).toBe('complete');
  });

  it('request failure preserves recovery status', () => {
    let state = chatReducer(initialChatState(), { type: 'detail_loaded', detail: detail('idle') });
    state = chatReducer(state, { type: 'question_received', question });
    state = chatReducer(state, { type: 'message_sent', text: 'answer' });
    state = chatReducer(state, { type: 'request_failed', message: 'boom' });
    expect(state.status).toBe('error');
    expect(state.error).toBe('boom');
    state = chatReducer(state, { type: 'error_dismissed' });
    expect(state.status).toBe('awaiting_answer');
  });

  it('resume mid-turn: awaiting_rating detail leads straight to rating chips', () => {
    const state = chatReducer(initialChatState(), {
      type: 'detail_loaded', detail: detail('awaiting_rating'),
    });
    expect(state.status).toBe('awaiting_rating');
  });
});
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `npx vitest run src/chat/machine.test.ts`
Expected: FAIL — module `./machine` not found.

- [ ] **Step 4: Implement `src/chat/machine.ts`**

```typescript
import type {
  QuestionResponse,
  TranscriptEvent,
  TurnResponse,
  WorkspaceSessionDetail,
} from '../api/types';

export type ChatStatus =
  | 'boot'
  | 'loading_question'
  | 'awaiting_answer'
  | 'working'
  | 'awaiting_rating'
  | 'reflection'
  | 'complete'
  | 'error';

export interface ChatState {
  status: ChatStatus;
  transcript: TranscriptEvent[];
  questionsAsked: number;
  maxQuestions: number;
  scalar: number;
  error: string | null;
  errorRecovery: ChatStatus;
}

export type ChatAction =
  | { type: 'detail_loaded'; detail: WorkspaceSessionDetail }
  | { type: 'question_requested' }
  | { type: 'question_received'; question: QuestionResponse }
  | { type: 'message_sent'; text: string }
  | { type: 'rating_sent'; rating: string }
  | { type: 'continue_sent' }
  | { type: 'turn_result'; result: TurnResponse; localEvents: TranscriptEvent[] }
  | { type: 'request_failed'; message: string }
  | { type: 'error_dismissed' };

export function initialChatState(): ChatState {
  return {
    status: 'boot',
    transcript: [],
    questionsAsked: 0,
    maxQuestions: 10,
    scalar: 0.5,
    error: null,
    errorRecovery: 'boot',
  };
}

const PHASE_TO_STATUS: Record<WorkspaceSessionDetail['phase'], ChatStatus> = {
  idle: 'loading_question',
  awaiting_answer: 'awaiting_answer',
  awaiting_rating: 'awaiting_rating',
  reflection: 'reflection',
  complete: 'complete',
};

const TURN_PHASE_TO_STATUS: Record<TurnResponse['phase'], ChatStatus> = {
  dialogue: 'awaiting_answer',
  skip_prompt: 'awaiting_answer',
  graded: 'awaiting_rating',
  reflection: 'reflection',
  completed: 'loading_question',
  session_complete: 'complete',
};

export function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case 'detail_loaded':
      return {
        ...state,
        status: PHASE_TO_STATUS[action.detail.phase],
        transcript: action.detail.transcript,
        questionsAsked: action.detail.question_count,
        maxQuestions: action.detail.max_questions,
        scalar: action.detail.scalar,
        error: null,
      };
    case 'question_requested':
      return { ...state, status: 'loading_question', errorRecovery: state.status };
    case 'question_received':
      return {
        ...state,
        status: 'awaiting_answer',
        questionsAsked: action.question.question_number,
        transcript: [
          ...state.transcript,
          {
            type: 'question',
            ts: new Date().toISOString(),
            question_number: action.question.question_number,
            question_id: action.question.question_id,
            concept_id: action.question.concept_id,
            concept_label: action.question.concept_label,
            question_text: action.question.question_text,
          },
        ],
      };
    case 'message_sent':
      return {
        ...state,
        status: 'working',
        errorRecovery: state.status,
        transcript: [
          ...state.transcript,
          { type: 'learner_message', ts: new Date().toISOString(), text: action.text },
        ],
      };
    case 'rating_sent':
    case 'continue_sent':
      return { ...state, status: 'working', errorRecovery: state.status };
    case 'turn_result': {
      const next: ChatState = {
        ...state,
        status: TURN_PHASE_TO_STATUS[action.result.phase],
        transcript: [...state.transcript, ...action.localEvents],
      };
      if (action.result.new_difficulty !== null && action.result.new_difficulty !== undefined) {
        next.scalar = action.result.new_difficulty;
      }
      return next;
    }
    case 'request_failed':
      return { ...state, status: 'error', error: action.message };
    case 'error_dismissed':
      return { ...state, status: state.errorRecovery, error: null };
    default:
      return state;
  }
}
```

Note: `rating_sent`/`continue_sent` set `errorRecovery` from the CURRENT status (i.e. `awaiting_rating`/`reflection`) — but the test for `message_sent` failure expects recovery to `awaiting_answer`; the implementation above stores the pre-`working` status, which is correct for all three.

- [ ] **Step 5: Run tests to verify they pass**

Run: `npx vitest run` — all PASS. Also `npm run build` — clean.

- [ ] **Step 6: Commit**

```bash
git add product/frontend/package.json product/frontend/package-lock.json product/frontend/src/chat
git commit -m "feat(frontend): pure chat turn-loop state machine with vitest coverage"
```

---

### Task 13: useTutorSession + live ChatView

**Files:**
- Create: `product/frontend/src/hooks/useTutorSession.ts`
- Rewrite: `product/frontend/src/components/views/ChatView.tsx`
- Modify: `product/frontend/src/styles/theme.css` (append chip/notice styles)

**Interfaces:**
- Consumes: machine (Task 12), client functions (Task 9), props from Workspace (Task 10): `domain: WorkspaceDomain`, `sessionId: string | null`, `backend: BackendState`, `onSessionCreated: (sessionId: string) => void`.
- Produces: the live chat.

- [ ] **Step 1: Implement the hook**

`product/frontend/src/hooks/useTutorSession.ts`:

```typescript
import { useCallback, useEffect, useReducer, useRef } from 'react';
import {
  getDomainSession,
  postDomainQuestion,
  postDomainTurn,
} from '../api/client';
import type { TranscriptEvent, TurnResponse } from '../api/types';
import { chatReducer, initialChatState, type ChatState } from '../chat/machine';

export interface TutorSession {
  state: ChatState;
  sendMessage: (text: string) => void;
  rate: (rating: 'easy' | 'ok' | 'hard') => void;
  continueNext: () => void;
  skip: () => void;
  dismissError: () => void;
}

function eventsFromTurn(body: Record<string, unknown>, result: TurnResponse): TranscriptEvent[] {
  const ts = new Date().toISOString();
  const events: TranscriptEvent[] = [];
  if (result.tutor_message) {
    events.push({ type: 'tutor_message', ts, text: result.tutor_message });
  }
  if (result.phase === 'graded') {
    events.push({ type: 'graded', ts, correct: result.correct });
  }
  if (result.phase === 'reflection' && body.explicit_rating) {
    events.push({
      type: 'rating',
      ts,
      rating: result.explicit_rating ?? String(body.explicit_rating),
      reward: result.reward,
      new_difficulty: result.new_difficulty,
    });
  }
  return events;
}

export function useTutorSession(domainId: string, sessionId: string): TutorSession {
  const [state, dispatch] = useReducer(chatReducer, undefined, initialChatState);
  const busyRef = useRef(false);

  // Load (or resume) the session on open.
  useEffect(() => {
    let cancelled = false;
    getDomainSession(domainId, sessionId)
      .then((detail) => {
        if (!cancelled) dispatch({ type: 'detail_loaded', detail });
      })
      .catch((err) => {
        if (!cancelled) {
          dispatch({
            type: 'request_failed',
            message: err instanceof Error ? err.message : String(err),
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [domainId, sessionId]);

  // Whenever we land in loading_question, fetch the next question.
  useEffect(() => {
    if (state.status !== 'loading_question' || busyRef.current) return;
    busyRef.current = true;
    postDomainQuestion(domainId, sessionId)
      .then((question) => dispatch({ type: 'question_received', question }))
      .catch((err) =>
        dispatch({
          type: 'request_failed',
          message: err instanceof Error ? err.message : String(err),
        }),
      )
      .finally(() => {
        busyRef.current = false;
      });
  }, [state.status, domainId, sessionId]);

  const runTurn = useCallback(
    (body: Record<string, unknown>) => {
      postDomainTurn(domainId, sessionId, body)
        .then((result) =>
          dispatch({ type: 'turn_result', result, localEvents: eventsFromTurn(body, result) }),
        )
        .catch((err) =>
          dispatch({
            type: 'request_failed',
            message: err instanceof Error ? err.message : String(err),
          }),
        );
    },
    [domainId, sessionId],
  );

  return {
    state,
    sendMessage: (text: string) => {
      dispatch({ type: 'message_sent', text });
      runTurn({ learner_message: text });
    },
    rate: (rating) => {
      dispatch({ type: 'rating_sent', rating });
      runTurn({ explicit_rating: rating });
    },
    continueNext: () => {
      dispatch({ type: 'continue_sent' });
      runTurn({ continue: true });
    },
    skip: () => {
      dispatch({ type: 'message_sent', text: '(skip this question)' });
      runTurn({ skip: true });
    },
    dismissError: () => dispatch({ type: 'error_dismissed' }),
  };
}
```

- [ ] **Step 2: Rewrite ChatView**

`product/frontend/src/components/views/ChatView.tsx` — full replacement:

```typescript
import { useState, type FormEvent } from 'react';
import { createDomainSession, seedDomain } from '../../api/client';
import type { TranscriptEvent, WorkspaceDomain } from '../../api/types';
import type { BackendState } from '../../hooks/useBackend';
import { useTutorSession } from '../../hooks/useTutorSession';

interface ChatViewProps {
  domain: WorkspaceDomain;
  sessionId: string | null;
  backend: BackendState;
  onSessionCreated: (sessionId: string) => void;
}

export function ChatView(props: ChatViewProps) {
  if (props.sessionId === null) {
    return <NewSessionStarter {...props} />;
  }
  return <LiveSession {...props} sessionId={props.sessionId} />;
}

function NewSessionStarter({ domain, backend, onSessionCreated }: ChatViewProps) {
  const readyChapters = domain.chapters.filter((c) => c.has_concept_graph);
  const [chapterId, setChapterId] = useState(readyChapters[0]?.id ?? '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (readyChapters.length === 0) {
    return (
      <section className="view">
        <article className="panel empty-state">
          <p className="eyebrow">Tutor chat</p>
          <h1>No curriculum compiled yet</h1>
          <p>
            This domain has no teachable chapters. Source intake ships in a later
            milestone.
          </p>
          {backend.health?.testbed && <TestbedSeed domain={domain} />}
        </article>
      </section>
    );
  }

  async function start() {
    setBusy(true);
    setError(null);
    try {
      const created = await createDomainSession(domain.id, {
        chapter_id: chapterId || undefined,
      });
      onSessionCreated(created.session_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setBusy(false);
    }
  }

  return (
    <section className="view">
      <article className="panel empty-state">
        <p className="eyebrow">Tutor chat</p>
        <h1>Start a tutoring session</h1>
        {readyChapters.length > 1 && (
          <label className="field">
            <span className="label">Chapter</span>
            <select
              className="select"
              value={chapterId}
              onChange={(e) => setChapterId(e.target.value)}
            >
              {readyChapters.map((c) => (
                <option key={c.id} value={c.id}>{c.id}</option>
              ))}
            </select>
          </label>
        )}
        {error && <div className="alert is-error">{error}</div>}
        <button
          className="button-primary"
          onClick={start}
          disabled={busy || backend.status !== 'online'}
        >
          {busy ? 'Starting…' : 'Start session'}
        </button>
      </article>
    </section>
  );
}

function TestbedSeed({ domain }: { domain: WorkspaceDomain }) {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  return (
    <div className="testbed-hint">
      <p className="help">
        Testbed mode: seed this domain with the compiled discrete-math curriculum, or run{' '}
        <span className="inline-code">python scripts/seed_domain.py {domain.id}</span>.
      </p>
      <button
        className="button-secondary"
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          try {
            const seeded = await seedDomain(domain.id);
            setResult(`Seeded chapters: ${seeded.chapters.join(', ') || 'none'} — refresh to continue.`);
          } catch (err) {
            setResult(err instanceof Error ? err.message : String(err));
          } finally {
            setBusy(false);
          }
        }}
      >
        {busy ? 'Seeding…' : 'Seed testbed curriculum'}
      </button>
      {result && <p className="help">{result}</p>}
    </div>
  );
}

function LiveSession({
  domain,
  sessionId,
  backend,
}: ChatViewProps & { sessionId: string }) {
  const tutor = useTutorSession(domain.id, sessionId);
  const [draft, setDraft] = useState('');
  const { state } = tutor;

  const providerMissing = !backend.provider?.active_provider;
  const composerEnabled =
    !providerMissing &&
    (state.status === 'awaiting_answer' || state.status === 'reflection');

  function submit(e: FormEvent) {
    e.preventDefault();
    const text = draft.trim();
    if (!text || !composerEnabled) return;
    setDraft('');
    tutor.sendMessage(text);
  }

  return (
    <section className="view">
      <section className="chat-layout panel">
        <article className="chat-transcript">
          <div className="chat-path">
            {domain.name} / Session History / difficulty {state.scalar.toFixed(2)} ·{' '}
            {state.questionsAsked}/{state.maxQuestions} questions
          </div>

          {state.transcript.map((event, index) => (
            <TranscriptBlock key={index} event={event} />
          ))}

          {state.status === 'loading_question' && (
            <div className="run-card">
              <div className="run-card-body">
                <span className="run-spinner" />
                <span>Preparing the next question…</span>
              </div>
            </div>
          )}
          {state.status === 'working' && (
            <div className="run-card">
              <div className="run-card-body">
                <span className="run-spinner" />
                <span>Tutor is working…</span>
              </div>
            </div>
          )}

          {state.status === 'awaiting_rating' && (
            <div className="rating-row">
              <span>How did that question feel?</span>
              <button className="rating-chip" onClick={() => tutor.rate('easy')}>Easy</button>
              <button className="rating-chip" onClick={() => tutor.rate('ok')}>Okay</button>
              <button className="rating-chip" onClick={() => tutor.rate('hard')}>Hard</button>
            </div>
          )}

          {state.status === 'reflection' && (
            <div className="rating-row">
              <span>Ask a follow-up about this question, or move on.</span>
              <button className="button-secondary" onClick={tutor.continueNext}>
                Continue to next question
              </button>
            </div>
          )}

          {state.status === 'complete' && (
            <div className="assistant-block">
              <p><strong>Session complete.</strong></p>
              <p>
                {state.questionsAsked} questions · final difficulty{' '}
                <span className="inline-code">{state.scalar.toFixed(2)}</span>. Start a new
                session from the sidebar to keep going.
              </p>
            </div>
          )}

          {state.status === 'error' && (
            <div className="alert is-error">
              {state.error}
              <div style={{ marginTop: 8 }}>
                <button className="button-secondary" onClick={tutor.dismissError}>
                  Dismiss
                </button>
              </div>
            </div>
          )}
        </article>

        <div className="chat-composer-wrap">
          {providerMissing ? (
            <div className="alert is-error">
              No LLM provider configured. Add an API key in Settings to start tutoring.
            </div>
          ) : (
            <form className="chat-composer" onSubmit={submit}>
              <button
                type="button"
                className="composer-icon"
                title="Skip this question"
                onClick={tutor.skip}
                disabled={state.status !== 'awaiting_answer'}
              >
                »
              </button>
              <input
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                placeholder={
                  state.status === 'awaiting_answer'
                    ? 'Answer, or ask for help…'
                    : state.status === 'reflection'
                      ? 'Ask a follow-up about this question…'
                      : state.status === 'awaiting_rating'
                        ? 'Rate the question to continue'
                        : 'Waiting…'
                }
                disabled={!composerEnabled}
              />
              <button type="submit" className="composer-icon" disabled={!composerEnabled}>
                ↵
              </button>
            </form>
          )}
        </div>
      </section>
    </section>
  );
}

function TranscriptBlock({ event }: { event: TranscriptEvent }) {
  switch (event.type) {
    case 'question':
      return (
        <div className="assistant-block">
          <p>
            <strong>Q{event.question_number}</strong> ·{' '}
            <span className="inline-code">{event.concept_label}</span>
          </p>
          <p>{event.question_text}</p>
        </div>
      );
    case 'learner_message':
      return <div className="prompt-card">{event.text}</div>;
    case 'tutor_message':
      return (
        <div className="assistant-block">
          <p>{event.text}</p>
        </div>
      );
    case 'graded':
      return (
        <div className="system-line">
          assessment recorded · correct: {event.correct}
        </div>
      );
    case 'rating':
      return (
        <div className="system-line">
          rated {event.rating}
          {typeof event.new_difficulty === 'number'
            ? ` · difficulty → ${event.new_difficulty.toFixed(2)}`
            : ''}
        </div>
      );
    case 'system':
      return <div className="system-line">{event.text}</div>;
    default:
      return null;
  }
}
```

- [ ] **Step 3: Append styles to `src/styles/theme.css`**

```css
/* --- live chat additions --- */
.rating-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 0;
  font-size: 13px;
  color: var(--muted, #807d72);
}

.rating-chip {
  padding: 4px 14px;
  border-radius: 9999px;
  border: 1px solid var(--hairline-strong, #cfcdc4);
  background: transparent;
  color: inherit;
  cursor: pointer;
  font-size: 12px;
}

.rating-chip:hover {
  border-color: currentColor;
}

.system-line {
  font-size: 12px;
  color: var(--muted, #807d72);
  padding: 4px 0;
  font-family: 'JetBrains Mono', monospace;
}

.empty-state {
  padding: 32px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  align-items: flex-start;
}

.testbed-hint {
  border-top: 1px solid var(--hairline, #e6e5e0);
  padding-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
```

(Use the CSS custom properties already defined in `theme.css` — during implementation check the actual variable names at the top of the file and substitute; the fallbacks above keep it safe either way.)

- [ ] **Step 4: Gate**

`npx vitest run` PASS; `npm run build` clean. Manual with stub provider (set an `ANTHROPIC_API_KEY=test` style stub or configure via conftest-equivalent: simplest is running the backend with a real or dummy key and confirming 503 handling if none): create domain → seed (testbed env) → start session → answer → rating chips → reflection → continue → next question. Kill the backend process, restart it, reopen the session from the sidebar → transcript is intact and the loop continues.

- [ ] **Step 5: Commit**

```bash
git add product/frontend/src
git commit -m "feat(frontend): live tutoring chat with resume, ratings, and reflection"
```

---

### Task 14: Settings modal (BYOK)

**Files:**
- Replace placeholder: `product/frontend/src/components/SettingsModal.tsx`
- Modify: `product/frontend/src/components/DesktopTitlebar.tsx` (gear button)
- Modify: `product/frontend/src/styles/theme.css` (modal styles)

**Interfaces:**
- Consumes: `updateProviderConfig` (Task 9); `ProviderConfig` from `useBackend`.
- Produces: `SettingsModal({ provider, onClose, onSaved })`.

- [ ] **Step 1: Implement**

`SettingsModal.tsx`:

```typescript
import { useState, type FormEvent } from 'react';
import { updateProviderConfig } from '../api/client';
import type { ProviderConfig } from '../api/types';

interface SettingsModalProps {
  provider: ProviderConfig | null;
  onClose: () => void;
  onSaved: () => void;
}

export function SettingsModal({ provider, onClose, onSaved }: SettingsModalProps) {
  const [anthropicKey, setAnthropicKey] = useState('');
  const [nimKey, setNimKey] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await updateProviderConfig({
        ...(anthropicKey.trim() ? { anthropic_api_key: anthropicKey.trim() } : {}),
        ...(nimKey.trim() ? { nim_api_key: nimKey.trim() } : {}),
      });
      onSaved();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setBusy(false);
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <article className="panel settings-modal" onClick={(e) => e.stopPropagation()}>
        <div className="screen-intro">
          <div>
            <p className="eyebrow">Settings</p>
            <h2>LLM providers</h2>
            <p>
              Keys are stored locally by the Python runtime. Anthropic is preferred when
              both are set; NIM is the fallback.
            </p>
          </div>
          <button className="button-secondary" onClick={onClose}>Close</button>
        </div>

        {!provider?.active_provider && (
          <div className="alert is-error">No provider configured — tutoring is disabled.</div>
        )}

        <form className="domain-form" onSubmit={save}>
          <label className="field is-wide">
            <span className="label">Anthropic API key</span>
            <input
              className="input"
              type="password"
              value={anthropicKey}
              onChange={(e) => setAnthropicKey(e.target.value)}
              placeholder={
                provider?.anthropic_api_key_set
                  ? `configured (${provider.anthropic_api_key_hint ?? '…'})`
                  : 'sk-ant-…'
              }
            />
          </label>
          <label className="field is-wide">
            <span className="label">NVIDIA NIM API key</span>
            <input
              className="input"
              type="password"
              value={nimKey}
              onChange={(e) => setNimKey(e.target.value)}
              placeholder={
                provider?.nim_api_key_set
                  ? `configured (${provider.nim_api_key_hint ?? '…'})`
                  : 'nvapi-…'
              }
            />
          </label>

          {error && <div className="alert is-error">{error}</div>}

          <div className="form-footer">
            <span className="help">
              Active: {provider?.active_provider ?? 'none'}
              {provider?.active_model ? ` · ${provider.active_model}` : ''}
            </span>
            <button
              type="submit"
              className="button-primary"
              disabled={busy || (!anthropicKey.trim() && !nimKey.trim())}
            >
              {busy ? 'Saving…' : 'Save keys'}
            </button>
          </div>
        </form>
      </article>
    </div>
  );
}
```

`DesktopTitlebar.tsx`: add `onOpenSettings: () => void` to its props and render, inside `.titlebar-right` before the window controls:

```tsx
<button className="window-button" title="Settings" onClick={onOpenSettings}>
  ⚙
</button>
```

Append to `theme.css`:

```css
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.settings-modal {
  width: min(560px, 92vw);
  padding: 24px;
  max-height: 80vh;
  overflow-y: auto;
}
```

- [ ] **Step 2: Gate**

`npm run build` clean. Manual: open Settings, save a key, provider stat updates, chat composer's "no provider" notice clears after refresh.

- [ ] **Step 3: Commit**

```bash
git add product/frontend/src
git commit -m "feat(frontend): provider settings modal wired to /config/provider"
```

---

### Task 15: Honest stubs (Sources / Graph / Scratchpad / AssistantPanel)

**Files:**
- Rewrite: `product/frontend/src/components/views/SourcesView.tsx`
- Rewrite: `product/frontend/src/components/views/GraphView.tsx`
- Rewrite: `product/frontend/src/components/views/ScratchpadView.tsx`
- Modify: `product/frontend/src/components/AssistantPanel.tsx`

**Interfaces:**
- Consumes: `WorkspaceDomain` (Task 9), props from Workspace (Task 10).
- Produces: three stub views with zero fake data and zero dead controls.

- [ ] **Step 1: Rewrite the three views**

`SourcesView.tsx`:

```typescript
import type { WorkspaceDomain } from '../../api/types';

export function SourcesView({ domain }: { domain: WorkspaceDomain }) {
  return (
    <section className="view">
      <div className="screen-intro">
        <div>
          <p className="eyebrow">Sources</p>
          <h1>{domain.name} sources</h1>
          <p>
            Files in this domain's <span className="inline-code">sources/</span> folder.
            Source intake (files, websites, video transcription) ships in a later milestone.
          </p>
        </div>
      </div>

      <article className="panel empty-state">
        {domain.source_files.length === 0 ? (
          <p>No sources yet. This folder is empty on disk.</p>
        ) : (
          <ul>
            {domain.source_files.map((name) => (
              <li key={name}>
                <span className="inline-code">{name}</span>
              </li>
            ))}
          </ul>
        )}
      </article>
    </section>
  );
}
```

`GraphView.tsx`:

```typescript
import type { WorkspaceDomain } from '../../api/types';

export function GraphView({ domain }: { domain: WorkspaceDomain }) {
  const ready = domain.chapters.filter((c) => c.has_concept_graph);
  return (
    <section className="view">
      <div className="screen-intro">
        <div>
          <p className="eyebrow">Adaptive curriculum</p>
          <h1>Curriculum map</h1>
          <p>
            Interactive graph editing ships in a later milestone. Compiled chapters in this
            domain today:
          </p>
        </div>
      </div>

      <article className="panel empty-state">
        {ready.length === 0 ? (
          <p>No compiled curriculum yet.</p>
        ) : (
          <ul>
            {ready.map((chapter) => (
              <li key={chapter.id}>
                <span className="inline-code">{chapter.id}</span> — concept graph
                {chapter.has_question_bank ? ' · question bank' : ''} · {chapter.wiki_count}{' '}
                wiki files
              </li>
            ))}
          </ul>
        )}
      </article>
    </section>
  );
}
```

`ScratchpadView.tsx`:

```typescript
export function ScratchpadView() {
  return (
    <section className="view">
      <div className="screen-intro">
        <div>
          <p className="eyebrow">Scratchpad</p>
          <h1>Drawable workspace</h1>
          <p>
            The tldraw scratchpad — with selection capture, AI vision, and a hideable AI
            layer — ships in a later milestone.
          </p>
        </div>
      </div>
    </section>
  );
}
```

`AssistantPanel.tsx`: replace any hardcoded fake proposals/copy with a single honest panel (keep the existing outer class names so the layout holds):

```typescript
export function AssistantPanel() {
  return (
    <aside className="assistant-panel">
      <div className="assistant-header">
        <span>Assistant</span>
      </div>
      <div className="assistant-body">
        <p className="help">
          Contextual agents (curriculum builder, source compiler) ship in later milestones.
          Tutoring happens in the chat tab.
        </p>
      </div>
    </aside>
  );
}
```

(Check `AssistantPanel.tsx`'s current class names during implementation and keep the container ones; the inner content is replaced. If `assistant-header`/`assistant-body` don't exist in theme.css, reuse whatever container classes the current file has.)

- [ ] **Step 2: Gate**

`npm run build` clean; `npx vitest run` still green. Manual sweep of all tabs: nothing fake renders anywhere in the app.

- [ ] **Step 3: Commit**

```bash
git add product/frontend/src
git commit -m "feat(frontend): honest stub views for sources, graph, and scratchpad"
```

---

### Task 16: End-to-end verification + README

**Files:**
- Modify: `product/README.md` (current state + data-dir docs)

- [ ] **Step 1: Full automated gates**

```bash
cd product/backend && python -m pytest tests -q
cd ../frontend && npx vitest run && npm run build
```

Expected: everything green.

- [ ] **Step 2: Manual end-to-end script**

1. `cd product/backend` and run: `APORE_TESTBED=1 uvicorn apore.api.app:app --port 8000` (PowerShell: `$env:APORE_TESTBED='1'; uvicorn apore.api.app:app --port 8000`).
2. `cd product/frontend && npm run dev`, open http://localhost:5173.
3. Create a domain "Discrete Math". Verify the folder exists under `~/Apore/domains/discrete-math-*/` with `domain.json`, `sessions/`, `sources/`, `knowledge/`.
4. Open the chat tab → "No curriculum compiled yet" + testbed seed button. Seed. Refresh. Start a session.
5. Answer a question, ask for a hint mid-question ("I'm stuck, can you explain?"), finish, rate it, ask one reflection follow-up, continue.
6. Kill the backend (Ctrl+C). Restart it. Reopen the session from the sidebar → transcript intact, loop continues from where it stopped.
7. Portability check: stop backend, copy the domain folder to a new name (e.g. `discrete-math-copy`), start backend, refresh → both domains appear; the copy opens with full session history.
8. Settings: clear/change keys and confirm the chat composer notice appears/disappears accordingly.
9. Verify no seed affordance appears when the backend runs WITHOUT `APORE_TESTBED=1`.

- [ ] **Step 3: Update `product/README.md`**

Rewrite the "Current state and follow-ups" section: the shell now creates real portable domains under `~/Apore/domains/` (`APORE_DATA_DIR` override), runs live persisted+resumable tutoring sessions, and has in-app BYOK settings; remaining milestones: Python sidecar, source intake, graph editing, scratchpad, CSP/icons. Document `APORE_TESTBED=1` and `scripts/seed_domain.py` under a "Testbed" heading.

- [ ] **Step 4: Commit**

```bash
git add product/README.md
git commit -m "docs: functional app v1 usage, data dir, and testbed notes"
```
