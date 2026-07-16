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
