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


def test_seed_non_post_method_404_without_testbed_env(domain_id, monkeypatch):
    monkeypatch.delenv("APORE_TESTBED", raising=False)
    resp = client.get(f"/domains/{domain_id}/seed")
    assert resp.status_code == 404


def test_seed_non_post_method_404_with_testbed_env(domain_id, monkeypatch):
    # Even when the testbed gate is on, non-POST verbs on the seed path
    # must remain indistinguishable from a missing route (no 405 leak).
    monkeypatch.setenv("APORE_TESTBED", "1")
    resp = client.get(f"/domains/{domain_id}/seed")
    assert resp.status_code == 404
