"""Upstream template fetch for setup API."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from apore.knowledge.chapter import find_chapter_with_graph
from apore.setup.stub_compile import bootstrap_chapter_from_wiki, find_fixture_chapter_root

_EMPTY_BANK = {"version": 1, "questions": []}


def _run(cmd: list[str], cwd: Path) -> None:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"Command failed: {cmd}")


def _current_commit(repo_dir: Path) -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _ensure_question_bank_shell(chapter_root: Path) -> None:
    bank_path = chapter_root / "question-bank.json"
    if not bank_path.is_file():
        bank_path.write_text(json.dumps(_EMPTY_BANK, indent=2) + "\n", encoding="utf-8")


def _clone_target_path(program_root: Path, name: str, spec: dict) -> Path:
    raw = spec.get("clone_target")
    if raw:
        return program_root / raw
    return program_root / ".fixtures" / name


def fetch_fixture(program_root: Path, name: str) -> dict:
    manifest_path = program_root / "apore" / "fixtures" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    spec = manifest.get("fixtures", {}).get(name)
    if not spec:
        raise KeyError(f"Unknown fixture {name!r}")

    url: str = spec["url"]
    commit: str = spec["commit"]
    upstream_subdir: str = spec.get("upstream_subdir", "discrete-math")
    domain_id: str = spec.get("domain_id", "discrete-math")
    chapter_id: str = spec.get("chapter_id", "01-set-theory")
    domain_target: Path = program_root / spec["target"]
    clone_target = _clone_target_path(program_root, name, spec)
    fixtures_dir = clone_target.parent
    knowledge_source = f"domain:{domain_id}/{chapter_id}"

    fetch_status = "fetched"
    try:
        if clone_target.exists():
            shutil.rmtree(clone_target)
        fixtures_dir.mkdir(parents=True, exist_ok=True)

        _run(["git", "clone", "--depth", "1", url, str(clone_target)], cwd=program_root)

        if _current_commit(clone_target) != commit:
            _run(["git", "fetch", "--depth", "1", "origin", commit], cwd=clone_target)
            _run(["git", "checkout", commit], cwd=clone_target)

        upstream_root = clone_target / upstream_subdir
        if not upstream_root.is_dir():
            raise RuntimeError(
                f"Expected {upstream_subdir!r} under cloned repo at {upstream_root}"
            )

        if domain_target.exists():
            shutil.rmtree(domain_target)
        domain_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(upstream_root, domain_target)

        chapter_root = find_fixture_chapter_root(domain_target)
        bootstrap_status: str | None = None
        nodes = 0
        chapter_path: str | None = None
        chapter_ready = False

        if chapter_root is not None:
            chapter_path = str(chapter_root)
            _ensure_question_bank_shell(chapter_root)
            if find_chapter_with_graph(domain_target) is None:
                summary = bootstrap_chapter_from_wiki(chapter_root)
                bootstrap_status = summary["status"]
                nodes = summary["nodes"]
            else:
                graph = json.loads(
                    (chapter_root / "concept-graph.json").read_text(encoding="utf-8")
                )
                nodes = len(graph.get("nodes") or [])
                bootstrap_status = "already_present"
            chapter_ready = True

        return {
            "name": name,
            "commit": commit,
            "path": str(domain_target),
            "knowledge_source": knowledge_source,
            "status": fetch_status,
            "chapter_ready": chapter_ready,
            "chapter_path": chapter_path,
            "nodes": nodes,
            "bootstrap_status": bootstrap_status,
        }
    finally:
        if fixtures_dir.exists() and fixtures_dir.name == ".fixtures":
            shutil.rmtree(fixtures_dir, ignore_errors=True)
