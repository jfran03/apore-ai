"""Setup API tests."""

import io
import uuid

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
