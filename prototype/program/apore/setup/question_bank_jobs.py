"""In-process background jobs for parallel question bank generation."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from apore.providers.base import Provider
from apore.setup.question_bank import generate_question_bank

JobStatus = str  # idle | running | completed | failed


@dataclass
class QuestionBankJob:
    status: JobStatus = "idle"
    concepts_total: int = 0
    concepts_done: int = 0
    questions: int | None = None
    concepts: int | None = None
    path: str | None = None
    error: str | None = None
    started_at: str | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def to_dict(self) -> dict:
        with self._lock:
            return {
                "status": self.status,
                "concepts_total": self.concepts_total,
                "concepts_done": self.concepts_done,
                "questions": self.questions,
                "concepts": self.concepts,
                "path": self.path,
                "error": self.error,
                "started_at": self.started_at,
            }

    def snapshot(self) -> dict:
        return self.to_dict()


_jobs: dict[str, QuestionBankJob] = {}
_registry_lock = threading.Lock()


def _job_key(chapter_root: Path) -> str:
    return str(chapter_root.resolve())


def reset_jobs_for_testing() -> None:
    """Clear in-memory generation jobs (tests only)."""
    with _registry_lock:
        _jobs.clear()


def get_job(chapter_root: Path) -> QuestionBankJob | None:
    key = _job_key(chapter_root)
    with _registry_lock:
        return _jobs.get(key)


def get_job_status(chapter_root: Path) -> dict:
    job = get_job(chapter_root)
    if job is None:
        return {
            "status": "idle",
            "concepts_total": 0,
            "concepts_done": 0,
            "questions": None,
            "concepts": None,
            "path": None,
            "error": None,
            "started_at": None,
        }
    return job.snapshot()


def _run_job(
    job: QuestionBankJob,
    *,
    chapter_root: Path,
    provider: Provider,
    model: str,
    program_root: Path,
    knowledge_source: str,
    provider_factory: Callable[[], Provider],
) -> None:
    def on_progress(done: int, total: int) -> None:
        with job._lock:
            job.concepts_done = done
            job.concepts_total = total

    try:
        summary = generate_question_bank(
            chapter_root,
            provider=provider,
            model=model,
            program_root=program_root,
            knowledge_source=knowledge_source,
            on_progress=on_progress,
            provider_factory=provider_factory,
        )
        with job._lock:
            job.status = "completed"
            job.questions = summary["questions"]
            job.concepts = summary["concepts"]
            job.path = summary["path"]
            job.concepts_done = job.concepts_total
    except Exception as exc:
        with job._lock:
            job.status = "failed"
            job.error = str(exc)


def start_job(
    chapter_root: Path,
    *,
    provider: Provider,
    model: str,
    program_root: Path,
    knowledge_source: str,
    concepts_total: int,
    provider_factory: Callable[[], Provider],
) -> QuestionBankJob:
    key = _job_key(chapter_root)
    with _registry_lock:
        existing = _jobs.get(key)
        if existing is not None and existing.status == "running":
            return existing

        job = QuestionBankJob(
            status="running",
            concepts_total=concepts_total,
            concepts_done=0,
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        _jobs[key] = job

    thread = threading.Thread(
        target=_run_job,
        kwargs={
            "job": job,
            "chapter_root": chapter_root,
            "provider": provider,
            "model": model,
            "program_root": program_root,
            "knowledge_source": knowledge_source,
            "provider_factory": provider_factory,
        },
        daemon=True,
    )
    thread.start()
    return job
