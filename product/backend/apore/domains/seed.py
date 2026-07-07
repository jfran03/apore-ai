"""Copy compiled curriculum into a workspace domain (testbed only).

Production has no UI path to this; it exists so the tutoring loop can be
exercised end-to-end before source intake ships.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from apore.domains.store import DomainRecord, chapters_dir


def seed_domain(
    record: DomainRecord,
    *,
    program_root: Path,
    source_domain_id: str = "discrete-math",
) -> list[str]:
    source_chapters = program_root / "domains" / source_domain_id / "chapters"
    if not source_chapters.is_dir():
        raise FileNotFoundError(
            f"No compiled curriculum at {source_chapters}"
        )
    dest_root = chapters_dir(record)
    dest_root.mkdir(parents=True, exist_ok=True)

    copied: list[str] = []
    for chapter in sorted(p for p in source_chapters.iterdir() if p.is_dir()):
        dest = dest_root / chapter.name
        if dest.exists():
            continue
        shutil.copytree(chapter, dest)
        copied.append(chapter.name)
    return copied
