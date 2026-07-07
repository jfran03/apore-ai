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
    root = get_data_root()
    path = root / domain_id

    # Verify path stays within root (prevent path traversal)
    if path.resolve().parent != root.resolve():
        raise FileNotFoundError(f"Domain {domain_id!r} not found")

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
