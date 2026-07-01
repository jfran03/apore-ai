"""Question bank async generation API tests."""

from __future__ import annotations

import shutil
import time

import pytest
from fastapi.testclient import TestClient

import apore.api.app as app_module
import apore.setup.question_bank_jobs as jobs_module
from apore.api.app import app

client = TestClient(app)

DOMAIN = "_pytest"
CHAPTER = "01-intro"
GENERATE_URL = f"/setup/domains/{DOMAIN}/chapters/{CHAPTER}/question-bank/generate"
STATUS_URL = f"{GENERATE_URL}/status"
BANK_URL = f"/setup/domains/{DOMAIN}/chapters/{CHAPTER}/question-bank"
_BANK_PATH = (
    app_module.PROGRAM_ROOT / "domains" / DOMAIN / "chapters" / CHAPTER / "question-bank.json"
)
_BANK_FIXTURE = (
    app_module.PROGRAM_ROOT / "tests" / "fixtures" / "minimal_chapter" / "question-bank.json"
)


@pytest.fixture(autouse=True)
def clear_generation_jobs():
    jobs_module.reset_jobs_for_testing()
    yield
    jobs_module.reset_jobs_for_testing()


@pytest.fixture(autouse=True)
def restore_question_bank():
    yield
    if _BANK_FIXTURE.is_file():
        shutil.copy2(_BANK_FIXTURE, _BANK_PATH)


def _poll_until_terminal(timeout_s: float = 5.0) -> dict:
    deadline = time.time() + timeout_s
    last: dict = {}
    while time.time() < deadline:
        resp = client.get(STATUS_URL)
        assert resp.status_code == 200
        last = resp.json()
        if last["status"] in {"completed", "failed"}:
            return last
        time.sleep(0.05)
    raise AssertionError(f"generation did not finish: {last!r}")


def test_generate_returns_202_and_completes():
    resp = client.post(GENERATE_URL)
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "running"
    assert body["concepts_total"] >= 1
    assert body["concepts_done"] == 0

    final = _poll_until_terminal()
    assert final["status"] == "completed"
    assert final["questions"] is not None
    assert final["questions"] >= 6

    bank = client.get(BANK_URL)
    assert bank.status_code == 200
    assert len(bank.json()["questions"]) == final["questions"]


def test_second_post_while_running_returns_same_job(monkeypatch: pytest.MonkeyPatch):
    barrier = __import__("threading").Event()

    original_run = jobs_module._run_job

    def slow_run_job(*args, **kwargs):
        with jobs_module._registry_lock:
            job = kwargs["job"]
            job.concepts_total = 2
        barrier.wait(timeout=2)
        return original_run(*args, **kwargs)

    monkeypatch.setattr(jobs_module, "_run_job", slow_run_job)

    first = client.post(GENERATE_URL)
    assert first.status_code == 202
    first_body = first.json()
    assert first_body["status"] == "running"

    second = client.post(GENERATE_URL)
    assert second.status_code == 202
    second_body = second.json()
    assert second_body["status"] == "running"
    assert second_body["started_at"] == first_body["started_at"]

    barrier.set()
    final = _poll_until_terminal()
    assert final["status"] == "completed"


def test_get_status_idle_when_no_job():
    resp = client.get(STATUS_URL)
    assert resp.status_code == 200
    assert resp.json()["status"] == "idle"
