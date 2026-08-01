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
    assert sessions[0]["status"] == "active"
    assert sessions[0]["ended_at"] is None
    uuid.UUID(sessions[0]["session_id"])  # parseable id


def test_list_and_transcript_expose_ended_early(sessions_dir):
    session_id = _write_session(
        sessions_dir, title="Cut short", created_at="2026-07-01T00:00:00+00:00"
    )
    path = sessions_dir / f"{session_id}.md"
    state.write_session_status(
        path,
        status="ended_early",
        ended_at="2026-07-01T01:00:00+00:00",
    )

    listed = client.get("/sessions").json()["sessions"]
    assert listed[0]["session_id"] == session_id
    assert listed[0]["status"] == "ended_early"
    assert listed[0]["ended_at"] == "2026-07-01T01:00:00+00:00"

    transcript = client.get(f"/sessions/{session_id}/transcript").json()
    assert transcript["status"] == "ended_early"
    assert transcript["ended_at"] == "2026-07-01T01:00:00+00:00"


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
    assert data["status"] == "active"
    assert data["ended_at"] is None
    assert data["questions"] == []
    assert "## Session" in data["body"]
    assert "## Question Log" in data["body"]


def test_get_transcript_unknown_uuid_404(sessions_dir):
    resp = client.get(f"/sessions/{uuid.uuid4()}/transcript")
    assert resp.status_code == 404


def test_get_transcript_invalid_id_404_no_traversal(sessions_dir):
    # Not a UUID -> rejected before any filesystem access
    resp = client.get("/sessions/..%2F..%2Fpyproject/transcript")
    assert resp.status_code == 404


def test_get_transcript_non_uuid_id_404(sessions_dir):
    # Single-segment non-UUID id: reaches the handler and exercises its UUID guard
    resp = client.get("/sessions/not-a-uuid/transcript")
    assert resp.status_code == 404
