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
    summaries.sort(key=lambda s: s["updated_at"], reverse=True)
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
