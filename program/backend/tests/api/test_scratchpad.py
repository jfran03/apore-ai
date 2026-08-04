"""Scratchpad mode API: study_mode, scene autosave, multimodal turns."""

from __future__ import annotations

import base64
import json

from fastapi.testclient import TestClient

from apore.api.app import app
from apore.providers.stub import StubProvider


def _png_uri() -> str:
    raw = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
    return f"data:image/png;base64,{base64.b64encode(raw).decode('ascii')}"


def test_create_session_study_mode_scratchpad(monkeypatch, tmp_path):
    monkeypatch.setenv("APORE_SESSIONS_DIR", str(tmp_path))
    # Re-import path binding is done at module load; use live app sessions dir via
    # create through client after patching PROGRAM sessions if needed.
    client = TestClient(app)
    monkeypatch.setattr(
        "apore.api.app.get_provider",
        lambda _name: StubProvider(),
    )
    monkeypatch.setattr("apore.api.app.get_active_provider", lambda: "stub")
    monkeypatch.setattr("apore.api.app.get_active_model", lambda: "stub-model")

    # Use existing fixture chapter if available; otherwise skip gracefully.
    res = client.post(
        "/sessions",
        json={
            "knowledge_source": "domain:discrete-math/01-set-theory",
            "study_mode": "scratchpad",
            "max_questions": 3,
        },
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["study_mode"] == "scratchpad"

    state = client.get(f"/sessions/{data['session_id']}/state")
    assert state.status_code == 200
    assert state.json()["study_mode"] == "scratchpad"


def test_scratchpad_submit_grades_with_feedback(monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr("apore.api.app.get_provider", lambda _name: StubProvider())
    monkeypatch.setattr("apore.api.app.get_active_provider", lambda: "stub")
    monkeypatch.setattr("apore.api.app.get_active_model", lambda: "stub-model")

    created = client.post(
        "/sessions",
        json={
            "knowledge_source": "domain:discrete-math/01-set-theory",
            "study_mode": "scratchpad",
            "max_questions": 3,
        },
    )
    assert created.status_code == 200, created.text
    session_id = created.json()["session_id"]
    q = client.post(f"/sessions/{session_id}/question", json={})
    assert q.status_code == 200, q.text

    turn = client.post(
        f"/sessions/{session_id}/turn",
        json={
            "scratchpad_action": "submit",
            "learner_image": _png_uri(),
            "learner_message": "wrong list answer",
        },
    )
    assert turn.status_code == 200, turn.text
    body = turn.json()
    assert body["phase"] == "graded"
    assert body["correct"] == "no"
    assert isinstance(body.get("feedback_regions"), list)
    assert len(body["feedback_regions"]) >= 1

    # Submitted crops are stored as sidecars; session markdown keeps a path reference.
    from apore.api.app import sessions

    sess = sessions[session_id]
    assets = sess.state_path.parent / sess.state_path.stem
    pngs = list(assets.glob("scratchpad-q*-submit-*.png"))
    assert pngs, "expected selection PNG sidecar"
    md = sess.state_path.read_text(encoding="utf-8")
    assert "scratchpad-q1-submit-1.png" in md
    assert "base64," not in md


def test_scratchpad_scene_roundtrip(monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr("apore.api.app.get_provider", lambda _name: StubProvider())
    monkeypatch.setattr("apore.api.app.get_active_provider", lambda: "stub")
    monkeypatch.setattr("apore.api.app.get_active_model", lambda: "stub-model")

    created = client.post(
        "/sessions",
        json={
            "knowledge_source": "domain:discrete-math/01-set-theory",
            "study_mode": "scratchpad",
            "max_questions": 3,
        },
    )
    assert created.status_code == 200, created.text
    session_id = created.json()["session_id"]
    q = client.post(f"/sessions/{session_id}/question", json={})
    assert q.status_code == 200
    qn = q.json()["question_number"]

    put = client.put(
        f"/sessions/{session_id}/scratchpad/scene",
        json={
            "question_number": qn,
            "schema_version": 1,
            "engine": "apore-konva",
            "nodes": [
                {
                    "id": "a",
                    "type": "rectangle",
                    "x": 0,
                    "y": 0,
                    "width": 10,
                    "height": 10,
                    "stroke": "#26251e",
                    "stroke_width": 2,
                }
            ],
            "camera": {"x": 1, "y": 2, "scale": 1.25},
            "last_export_bounds": {
                "x": -4,
                "y": -4,
                "width": 18,
                "height": 18,
                "padding": 4,
            },
            "feedback_regions": [
                {
                    "x": 0.25,
                    "y": 0.5,
                    "w": 0.5,
                    "h": 0.25,
                    "label": "Check",
                    "explanation": "Revisit this step",
                }
            ],
        },
    )
    assert put.status_code == 200, put.text

    malformed = client.put(
        f"/sessions/{session_id}/scratchpad/scene",
        json={
            "question_number": qn,
            "schema_version": 1,
            "engine": "apore-konva",
            "nodes": [{"id": "bad", "type": "image", "x": 0, "y": 0}],
            "camera": {"x": 0, "y": 0, "scale": 1},
            "last_export_bounds": None,
            "feedback_regions": [],
        },
    )
    assert malformed.status_code == 422

    got = client.get(
        f"/sessions/{session_id}/scratchpad/scene",
        params={"question_number": qn},
    )
    assert got.status_code == 200
    scene = got.json()["scene"]
    assert scene is not None
    assert scene["question_number"] == qn
    assert scene["schema_version"] == 1
    assert scene["engine"] == "apore-konva"
    assert len(scene["nodes"]) == 1
    assert scene["camera"] == {"x": 1.0, "y": 2.0, "scale": 1.25}
    assert scene["last_export_bounds"]["padding"] == 4.0
    assert scene["feedback_regions"][0]["label"] == "Check"
    assert scene.get("annotations") == []


def test_scratchpad_scene_annotations_round_trip(monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr("apore.api.app.get_provider", lambda _name: StubProvider())
    monkeypatch.setattr("apore.api.app.get_active_provider", lambda: "stub")
    monkeypatch.setattr("apore.api.app.get_active_model", lambda: "stub-model")

    created = client.post(
        "/sessions",
        json={
            "knowledge_source": "domain:discrete-math/01-set-theory",
            "study_mode": "scratchpad",
            "max_questions": 3,
        },
    )
    assert created.status_code == 200, created.text
    session_id = created.json()["session_id"]
    q = client.post(f"/sessions/{session_id}/question", json={})
    assert q.status_code == 200
    qn = q.json()["question_number"]

    put = client.put(
        f"/sessions/{session_id}/scratchpad/scene",
        json={
            "question_number": qn,
            "schema_version": 1,
            "engine": "apore-konva",
            "nodes": [
                {
                    "id": "a",
                    "type": "rectangle",
                    "x": 0,
                    "y": 0,
                    "width": 10,
                    "height": 10,
                    "stroke": "#26251e",
                    "stroke_width": 2,
                }
            ],
            "camera": {"x": 0, "y": 0, "scale": 1},
            "last_export_bounds": None,
            "feedback_regions": [],
            "annotations": [
                {
                    "id": "ann-1",
                    "node_ids": ["a"],
                    "prompt": "Is this a set?",
                    "response": "Check whether order matters.",
                    "feedback_regions": [
                        {
                            "x": 0.1,
                            "y": 0.2,
                            "w": 0.3,
                            "h": 0.25,
                            "label": "Here",
                            "explanation": "Revisit this mark",
                        }
                    ],
                }
            ],
        },
    )
    assert put.status_code == 200, put.text

    got = client.get(
        f"/sessions/{session_id}/scratchpad/scene",
        params={"question_number": qn},
    )
    assert got.status_code == 200
    scene = got.json()["scene"]
    assert scene is not None
    assert len(scene["annotations"]) == 1
    assert scene["annotations"][0]["id"] == "ann-1"
    assert scene["annotations"][0]["node_ids"] == ["a"]
    assert scene["annotations"][0]["response"] == "Check whether order matters."
    assert scene["annotations"][0]["feedback_regions"][0]["label"] == "Here"


def test_legacy_scene_without_annotations_still_loads(tmp_path):
    from apore.runtime import scratchpad_store

    state_path = tmp_path / "session.md"
    path = scratchpad_store.scene_path(state_path, 1)
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "question_number": 1,
                "schema_version": 1,
                "engine": "apore-konva",
                "nodes": [],
                "camera": {"x": 0, "y": 0, "scale": 1},
                "last_export_bounds": None,
                "feedback_regions": [],
            }
        ),
        encoding="utf-8",
    )
    scene = scratchpad_store.read_scene(state_path, 1)
    assert scene is not None
    assert scene["annotations"] == []


def test_legacy_excalidraw_scene_is_treated_as_absent(tmp_path):
    from apore.runtime import scratchpad_store

    state_path = tmp_path / "session.md"
    legacy_path = scratchpad_store.scene_path(state_path, 1)
    legacy_path.parent.mkdir(parents=True)
    legacy_path.write_text(
        '{"question_number":1,"elements":[{"id":"legacy"}],"app_state":{},"files":{}}',
        encoding="utf-8",
    )

    assert scratchpad_store.read_scene(state_path, 1) is None
