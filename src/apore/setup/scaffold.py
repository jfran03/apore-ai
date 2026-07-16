"""Scaffold domains and chapters from shared templates."""

from __future__ import annotations

import shutil
from pathlib import Path

from apore.setup.paths import chapter_dir, validate_id


def scaffold_domain(program_root: Path, domain_id: str) -> Path:
    validate_id(domain_id, "domain_id")
    template = program_root / "shared" / "_templates" / "new-domain"
    if not template.is_dir():
        raise FileNotFoundError(f"Template not found: {template}")

    dest = program_root / "domains" / domain_id
    if dest.exists():
        raise FileExistsError(f"Domain already exists: {domain_id}")

    shutil.copytree(template, dest)
    return dest


def scaffold_chapter(program_root: Path, domain_id: str, chapter_id: str) -> Path:
    validate_id(domain_id, "domain_id")
    validate_id(chapter_id, "chapter_id")

    domain_path = program_root / "domains" / domain_id
    if not domain_path.is_dir():
        raise FileNotFoundError(f"Domain not found: {domain_id}")

    template_chapter = program_root / "shared" / "_templates" / "new-domain" / "chapters" / "01-intro"
    dest = chapter_dir(program_root, domain_id, chapter_id)
    if dest.exists():
        raise FileExistsError(f"Chapter already exists: {chapter_id}")

    shutil.copytree(template_chapter, dest)
    return dest
