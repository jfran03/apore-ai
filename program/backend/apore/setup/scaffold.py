"""Scaffold domains and chapters from shared templates."""

from __future__ import annotations

import shutil
from pathlib import Path

from apore.setup.paths import chapter_dir, validate_id


def render_domain_md(
    name: str,
    scope: str | None = None,
    goal: str | None = None,
    tutor_style: str | None = None,
) -> str:
    """Render an apore-lite-style DOMAIN.md from creation metadata."""
    scope_text = (scope or "").strip() or "[SCOPE]"
    goal_text = (goal or "").strip() or "[GOAL]"
    style_text = (tutor_style or "").strip() or "[TUTOR STYLE]"
    return (
        f"# {name.strip() or '[DOMAIN NAME]'}\n"
        f"\n"
        f"## Subject Scope\n"
        f"{scope_text}\n"
        f"\n"
        f"## Goal\n"
        f"{goal_text}\n"
        f"\n"
        f"## Tutor Style\n"
        f"{style_text}\n"
        f"\n"
        f"## Chapter Index\n"
        f"\n"
        f"1. 01-intro — [Chapter description]\n"
    )


def scaffold_domain(
    program_root: Path,
    domain_id: str,
    *,
    name: str | None = None,
    scope: str | None = None,
    goal: str | None = None,
    tutor_style: str | None = None,
) -> Path:
    validate_id(domain_id, "domain_id")
    template = program_root / "shared" / "_templates" / "new-domain"
    if not template.is_dir():
        raise FileNotFoundError(f"Template not found: {template}")

    dest = program_root / "domains" / domain_id
    if dest.exists():
        raise FileExistsError(f"Domain already exists: {domain_id}")

    shutil.copytree(template, dest)
    if any([name, scope, goal, tutor_style]):
        (dest / "DOMAIN.md").write_text(
            render_domain_md(name or domain_id, scope, goal, tutor_style),
            encoding="utf-8",
        )
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


def rename_chapter(
    program_root: Path,
    domain_id: str,
    chapter_id: str,
    new_chapter_id: str,
) -> Path:
    validate_id(domain_id, "domain_id")
    validate_id(chapter_id, "chapter_id")
    validate_id(new_chapter_id, "chapter_id")

    domain_path = program_root / "domains" / domain_id
    if not domain_path.is_dir():
        raise FileNotFoundError(f"Domain not found: {domain_id}")

    src = chapter_dir(program_root, domain_id, chapter_id)
    if not src.is_dir():
        raise FileNotFoundError(f"Chapter not found: {chapter_id}")

    if new_chapter_id == chapter_id:
        return src

    dest = chapter_dir(program_root, domain_id, new_chapter_id)
    if dest.exists():
        raise FileExistsError("A chapter with this name already exists.")

    shutil.move(str(src), str(dest))
    return dest


def delete_chapter(program_root: Path, domain_id: str, chapter_id: str) -> None:
    validate_id(domain_id, "domain_id")
    validate_id(chapter_id, "chapter_id")

    domain_path = program_root / "domains" / domain_id
    if not domain_path.is_dir():
        raise FileNotFoundError(f"Domain not found: {domain_id}")

    path = chapter_dir(program_root, domain_id, chapter_id)
    if not path.is_dir():
        raise FileNotFoundError(f"Chapter not found: {chapter_id}")

    shutil.rmtree(path)


def rename_domain(program_root: Path, domain_id: str, new_domain_id: str) -> Path:
    validate_id(domain_id, "domain_id")
    validate_id(new_domain_id, "domain_id")

    src = program_root / "domains" / domain_id
    if not src.is_dir():
        raise FileNotFoundError(f"Domain not found: {domain_id}")

    if new_domain_id == domain_id:
        return src

    dest = program_root / "domains" / new_domain_id
    if dest.exists():
        raise FileExistsError("A domain with this name already exists.")

    shutil.move(str(src), str(dest))
    return dest


def delete_domain(program_root: Path, domain_id: str) -> None:
    validate_id(domain_id, "domain_id")

    path = program_root / "domains" / domain_id
    if not path.is_dir():
        raise FileNotFoundError(f"Domain not found: {domain_id}")

    shutil.rmtree(path)
