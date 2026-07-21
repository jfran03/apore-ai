"""Setup API tests."""

import io
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from apore.api.app import app

client = TestClient(app)


def test_list_knowledge():
    resp = client.get("/setup/knowledge")
    assert resp.status_code == 200
    data = resp.json()
    assert "fixtures" in data
    assert "domains" in data
    assert any(f["name"] == "apore-lite" for f in data["fixtures"])
    domain_ids = [d["id"] for d in data["domains"]]
    assert "_pytest" not in domain_ids
    for domain in data["domains"]:
        for chapter in domain["chapters"]:
            assert "has_question_bank" in chapter
            assert "question_bank_count" in chapter
            assert isinstance(chapter["has_question_bank"], bool)
            assert isinstance(chapter["question_bank_count"], int)
            if chapter["has_question_bank"]:
                assert chapter["question_bank_count"] > 0


def test_scaffold_domain_chapter_upload_compile():
    domain_id = f"testdomain_{uuid.uuid4().hex[:8]}"
    chapter_id = "ch01"

    assert client.post("/setup/domains", json={"domain_id": domain_id}).status_code == 200
    resp = client.post(
        f"/setup/domains/{domain_id}/chapters",
        json={"chapter_id": chapter_id},
    )
    assert resp.status_code == 200
    knowledge_source = resp.json()["knowledge_source"]

    upload = client.post(
        f"/setup/domains/{domain_id}/chapters/{chapter_id}/sources",
        files=[("files", ("notes.md", io.BytesIO(b"# Notes\n\nSets are collections."), "text/markdown"))],
    )
    assert upload.status_code == 200
    assert "notes.md" in upload.json()["uploaded"]

    compile_resp = client.post(
        f"/setup/domains/{domain_id}/chapters/{chapter_id}/compile-stub",
    )
    assert compile_resp.status_code == 200
    assert compile_resp.json()["nodes"] >= 1

    session = client.post("/sessions", json={"knowledge_source": knowledge_source})
    assert session.status_code == 200
    session_id = session.json()["session_id"]

    q = client.post(f"/sessions/{session_id}/question", json={})
    assert q.status_code == 200
    assert q.json()["concept_label"] == "Notes"
    assert q.json()["concept_id"] == "notes"


def test_rename_chapter_preserves_artifacts_and_rejects_duplicates():
    domain_id = f"testdomain_{uuid.uuid4().hex[:8]}"
    chapter_id = "ch01"
    other_id = "ch02"
    renamed_id = "ch01-renamed"

    assert client.post("/setup/domains", json={"domain_id": domain_id}).status_code == 200
    assert (
        client.post(
            f"/setup/domains/{domain_id}/chapters",
            json={"chapter_id": chapter_id},
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/setup/domains/{domain_id}/chapters",
            json={"chapter_id": other_id},
        ).status_code
        == 200
    )

    upload = client.post(
        f"/setup/domains/{domain_id}/chapters/{chapter_id}/sources",
        files=[("files", ("notes.md", io.BytesIO(b"# Notes\n\nSets are collections."), "text/markdown"))],
    )
    assert upload.status_code == 200
    assert (
        client.post(f"/setup/domains/{domain_id}/chapters/{chapter_id}/compile-stub").status_code
        == 200
    )

    conflict = client.patch(
        f"/setup/domains/{domain_id}/chapters/{chapter_id}",
        json={"chapter_id": other_id},
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"] == "A chapter with this name already exists."

    invalid = client.patch(
        f"/setup/domains/{domain_id}/chapters/{chapter_id}",
        json={"chapter_id": "Bad Name!"},
    )
    assert invalid.status_code == 400

    missing = client.patch(
        f"/setup/domains/{domain_id}/chapters/ghost",
        json={"chapter_id": "new-name"},
    )
    assert missing.status_code == 404

    renamed = client.patch(
        f"/setup/domains/{domain_id}/chapters/{chapter_id}",
        json={"chapter_id": renamed_id},
    )
    assert renamed.status_code == 200
    assert renamed.json()["chapter_id"] == renamed_id
    assert renamed.json()["knowledge_source"] == f"domain:{domain_id}/{renamed_id}"

    catalog = client.get("/setup/knowledge").json()
    domain = next(d for d in catalog["domains"] if d["id"] == domain_id)
    chapter_ids = [c["id"] for c in domain["chapters"]]
    assert renamed_id in chapter_ids
    assert chapter_id not in chapter_ids

    sources = client.get(f"/setup/domains/{domain_id}/chapters/{renamed_id}/sources")
    assert sources.status_code == 200
    assert len(sources.json()["sources"]) == 1

    artifact = client.get(f"/setup/domains/{domain_id}/chapters/{renamed_id}/artifact")
    assert artifact.status_code == 200
    assert artifact.json()["concept_count"] >= 1


def test_delete_chapter_removes_directory_and_catalog_entry():
    domain_id = f"testdomain_{uuid.uuid4().hex[:8]}"
    chapter_id = "ch01"

    assert client.post("/setup/domains", json={"domain_id": domain_id}).status_code == 200
    assert (
        client.post(
            f"/setup/domains/{domain_id}/chapters",
            json={"chapter_id": chapter_id},
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/setup/domains/{domain_id}/chapters/{chapter_id}/sources",
            files=[("files", ("notes.md", io.BytesIO(b"# Notes\n\nSets."), "text/markdown"))],
        ).status_code
        == 200
    )
    assert (
        client.post(f"/setup/domains/{domain_id}/chapters/{chapter_id}/compile-stub").status_code
        == 200
    )

    deleted = client.delete(f"/setup/domains/{domain_id}/chapters/{chapter_id}")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True

    assert client.get(f"/setup/domains/{domain_id}/chapters/{chapter_id}/sources").status_code == 404
    assert client.delete(f"/setup/domains/{domain_id}/chapters/{chapter_id}").status_code == 404

    catalog = client.get("/setup/knowledge").json()
    domain = next(d for d in catalog["domains"] if d["id"] == domain_id)
    assert chapter_id not in [c["id"] for c in domain["chapters"]]


def test_rename_domain_preserves_artifacts_and_migrates_sessions(tmp_path, monkeypatch):
    import apore.api.app as app_module
    from apore.api.app import SessionState, sessions
    from apore.knowledge.chapter import resolve_chapter
    from apore.runtime import state as state_mod

    monkeypatch.setattr(app_module, "SESSIONS_DIR", tmp_path)

    domain_id = f"testdomain_{uuid.uuid4().hex[:8]}"
    other_id = f"testdomain_{uuid.uuid4().hex[:8]}"
    renamed_id = f"{domain_id}_renamed"
    chapter_id = "ch01"

    assert client.post("/setup/domains", json={"domain_id": domain_id}).status_code == 200
    assert client.post("/setup/domains", json={"domain_id": other_id}).status_code == 200
    assert (
        client.post(
            f"/setup/domains/{domain_id}/chapters",
            json={"chapter_id": chapter_id},
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/setup/domains/{domain_id}/chapters/{chapter_id}/sources",
            files=[("files", ("notes.md", io.BytesIO(b"# Notes\n\nSets are collections."), "text/markdown"))],
        ).status_code
        == 200
    )
    assert (
        client.post(f"/setup/domains/{domain_id}/chapters/{chapter_id}/compile-stub").status_code
        == 200
    )

    knowledge_source = f"domain:{domain_id}/{chapter_id}"
    session_id = str(uuid.uuid4())
    state_path = tmp_path / f"{session_id}.md"
    state_mod.initialize(
        state_path,
        title="Live session",
        session_id=session_id,
        created_at="2026-07-01T00:00:00+00:00",
        knowledge_source=knowledge_source,
        focus_mode="adaptive",
        max_questions=10,
    )
    chapter = resolve_chapter(knowledge_source, app_module.PROGRAM_ROOT)
    sessions[session_id] = SessionState(
        session_id=session_id,
        title="Live session",
        knowledge_source=knowledge_source,
        chapter=chapter,
        state_path=state_path,
        scalar=0.5,
        question_count=0,
        created_at="2026-07-01T00:00:00+00:00",
    )

    other_session_id = str(uuid.uuid4())
    state_mod.initialize(
        tmp_path / f"{other_session_id}.md",
        title="Other domain session",
        session_id=other_session_id,
        created_at="2026-07-01T00:00:00+00:00",
        knowledge_source=f"domain:{other_id}/ch01",
        focus_mode="adaptive",
        max_questions=10,
    )

    conflict = client.patch(f"/setup/domains/{domain_id}", json={"domain_id": other_id})
    assert conflict.status_code == 409
    assert conflict.json()["detail"] == "A domain with this name already exists."

    invalid = client.patch(f"/setup/domains/{domain_id}", json={"domain_id": "Bad Name!"})
    assert invalid.status_code == 400

    missing = client.patch(
        f"/setup/domains/ghost_{uuid.uuid4().hex[:6]}",
        json={"domain_id": "new-name"},
    )
    assert missing.status_code == 404

    renamed = client.patch(f"/setup/domains/{domain_id}", json={"domain_id": renamed_id})
    assert renamed.status_code == 200
    assert renamed.json()["domain_id"] == renamed_id
    assert renamed.json()["sessions_updated"] >= 1

    catalog = client.get("/setup/knowledge").json()
    domain_ids = [d["id"] for d in catalog["domains"]]
    assert renamed_id in domain_ids
    assert domain_id not in domain_ids

    sources = client.get(f"/setup/domains/{renamed_id}/chapters/{chapter_id}/sources")
    assert sources.status_code == 200
    assert len(sources.json()["sources"]) == 1

    artifact = client.get(f"/setup/domains/{renamed_id}/chapters/{chapter_id}/artifact")
    assert artifact.status_code == 200
    assert artifact.json()["concept_count"] >= 1

    migrated = state_mod.read_session_meta(tmp_path / f"{session_id}.md")
    assert migrated["knowledge_source"] == f"domain:{renamed_id}/{chapter_id}"

    untouched = state_mod.read_session_meta(tmp_path / f"{other_session_id}.md")
    assert untouched["knowledge_source"] == f"domain:{other_id}/ch01"

    live = client.get(f"/sessions/{session_id}/state")
    assert live.status_code == 200
    assert live.json()["knowledge_source"] == f"domain:{renamed_id}/{chapter_id}"
    assert sessions[session_id].chapter.chapter_root == (
        app_module.PROGRAM_ROOT / "domains" / renamed_id / "chapters" / chapter_id
    )


def test_delete_domain_removes_tree_and_associated_sessions(tmp_path, monkeypatch):
    import apore.api.app as app_module
    from apore.api.app import SessionState, sessions
    from apore.knowledge.chapter import resolve_chapter
    from apore.runtime import state as state_mod

    monkeypatch.setattr(app_module, "SESSIONS_DIR", tmp_path)

    domain_id = f"testdomain_{uuid.uuid4().hex[:8]}"
    keep_id = f"testdomain_{uuid.uuid4().hex[:8]}"
    chapter_id = "ch01"

    assert client.post("/setup/domains", json={"domain_id": domain_id}).status_code == 200
    assert client.post("/setup/domains", json={"domain_id": keep_id}).status_code == 200
    assert (
        client.post(
            f"/setup/domains/{domain_id}/chapters",
            json={"chapter_id": chapter_id},
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/setup/domains/{domain_id}/chapters/{chapter_id}/sources",
            files=[("files", ("notes.md", io.BytesIO(b"# Notes\n\nSets."), "text/markdown"))],
        ).status_code
        == 200
    )
    assert (
        client.post(f"/setup/domains/{domain_id}/chapters/{chapter_id}/compile-stub").status_code
        == 200
    )

    knowledge_source = f"domain:{domain_id}/{chapter_id}"
    session_id = str(uuid.uuid4())
    state_path = tmp_path / f"{session_id}.md"
    state_mod.initialize(
        state_path,
        title="Delete me",
        session_id=session_id,
        created_at="2026-07-01T00:00:00+00:00",
        knowledge_source=knowledge_source,
        focus_mode="adaptive",
        max_questions=10,
    )
    chapter = resolve_chapter(knowledge_source, app_module.PROGRAM_ROOT)
    sessions[session_id] = SessionState(
        session_id=session_id,
        title="Delete me",
        knowledge_source=knowledge_source,
        chapter=chapter,
        state_path=state_path,
        scalar=0.5,
        question_count=0,
        created_at="2026-07-01T00:00:00+00:00",
    )

    keep_session_id = str(uuid.uuid4())
    state_mod.initialize(
        tmp_path / f"{keep_session_id}.md",
        title="Keep me",
        session_id=keep_session_id,
        created_at="2026-07-01T00:00:00+00:00",
        knowledge_source=f"domain:{keep_id}/ch01",
        focus_mode="adaptive",
        max_questions=10,
    )

    deleted = client.delete(f"/setup/domains/{domain_id}")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True
    assert deleted.json()["sessions_deleted"] >= 1

    assert client.get(f"/setup/domains/{domain_id}/chapters/{chapter_id}/sources").status_code == 404
    assert client.delete(f"/setup/domains/{domain_id}").status_code == 404
    assert client.get(f"/sessions/{session_id}/state").status_code == 404
    assert session_id not in sessions
    assert not (tmp_path / f"{session_id}.md").exists()
    assert (tmp_path / f"{keep_session_id}.md").exists()

    catalog = client.get("/setup/knowledge").json()
    domain_ids = [d["id"] for d in catalog["domains"]]
    assert domain_id not in domain_ids
    assert keep_id in domain_ids


def test_rewrite_knowledge_source_updates_only_matching_value(tmp_path):
    from apore.runtime import state as state_mod

    path = tmp_path / "session.md"
    state_mod.initialize(
        path,
        title="Rewrite me",
        session_id=str(uuid.uuid4()),
        created_at="2026-07-01T00:00:00+00:00",
        knowledge_source="domain:alpha/ch01",
        focus_mode="adaptive",
        max_questions=10,
    )
    text_before = path.read_text(encoding="utf-8")
    assert "domain:alpha/ch01" in text_before

    assert state_mod.rewrite_knowledge_source(path, "domain:alpha/ch01", "domain:beta/ch01") is True
    meta = state_mod.read_session_meta(path)
    assert meta["knowledge_source"] == "domain:beta/ch01"
    assert "## Question Log" in path.read_text(encoding="utf-8")

    assert state_mod.rewrite_knowledge_source(path, "domain:alpha/ch01", "domain:gamma/ch01") is False
    assert state_mod.read_session_meta(path)["knowledge_source"] == "domain:beta/ch01"


def test_create_domain_with_metadata_writes_domain_md():
    domain_id = f"testdomain_{uuid.uuid4().hex[:8]}"
    resp = client.post(
        "/setup/domains",
        json={
            "domain_id": domain_id,
            "name": "Cell Biology",
            "scope": "Cellular structure and function for undergrads.",
            "goal": "General mastery",
            "tutor_style": "Socratic",
        },
    )
    assert resp.status_code == 200
    path = resp.json()["path"]
    domain_md = (Path(path) / "DOMAIN.md").read_text(encoding="utf-8")
    assert "# Cell Biology" in domain_md
    assert "## Subject Scope" in domain_md
    assert "Cellular structure and function for undergrads." in domain_md
    assert "## Goal" in domain_md
    assert "General mastery" in domain_md
    assert "## Tutor Style" in domain_md
    assert "Socratic" in domain_md
    assert "01-intro" in domain_md


def test_create_domain_id_only_keeps_template_placeholder():
    domain_id = f"testdomain_{uuid.uuid4().hex[:8]}"
    resp = client.post("/setup/domains", json={"domain_id": domain_id})
    assert resp.status_code == 200
    path = resp.json()["path"]
    domain_md = (Path(path) / "DOMAIN.md").read_text(encoding="utf-8")
    assert "[DOMAIN NAME]" in domain_md
    assert "<!-- Replace [DOMAIN NAME]" in domain_md
