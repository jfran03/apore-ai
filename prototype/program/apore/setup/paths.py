"""Safe path helpers for setup writes."""

from __future__ import annotations

import re
from pathlib import Path

_ID_RE = re.compile(r"^[a-z0-9_][a-z0-9_-]*$")


def validate_id(value: str, field: str) -> str:
    if not _ID_RE.match(value):
        raise ValueError(f"Invalid {field}: {value!r}")
    return value


def chapter_dir(program_root: Path, domain_id: str, chapter_id: str) -> Path:
    validate_id(domain_id, "domain_id")
    validate_id(chapter_id, "chapter_id")
    return program_root / "domains" / domain_id / "chapters" / chapter_id
