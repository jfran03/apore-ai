"""Fixture fetch for setup API."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from apore.knowledge.chapter import find_chapter_with_graph
from apore.setup.stub_compile import bootstrap_chapter_from_wiki, find_fixture_chapter_root


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


def fetch_fixture(program_root: Path, name: str) -> dict:
    manifest_path = program_root / "apore" / "fixtures" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    spec = manifest.get("fixtures", {}).get(name)
    if not spec:
        raise KeyError(f"Unknown fixture {name!r}")

    url: str = spec["url"]
    commit: str = spec["commit"]
    target: Path = program_root / spec["target"]

    fetch_status = "already_present"
    if target.exists() and _current_commit(target) == commit:
        pass
    else:
        if target.exists():
            shutil.rmtree(target)

        target.parent.mkdir(parents=True, exist_ok=True)
        _run(["git", "clone", "--depth", "1", url, str(target)], cwd=program_root)

        current = _current_commit(target)
        if current != commit:
            _run(["git", "fetch", "--depth", "1", "origin", commit], cwd=target)
            _run(["git", "checkout", commit], cwd=target)
        fetch_status = "fetched"

    chapter_root = find_fixture_chapter_root(target)
    bootstrap_status: str | None = None
    nodes = 0
    chapter_path: str | None = None
    chapter_ready = False

    if chapter_root is not None:
        chapter_path = str(chapter_root)
        if find_chapter_with_graph(target) is None:
            summary = bootstrap_chapter_from_wiki(chapter_root)
            bootstrap_status = summary["status"]
            nodes = summary["nodes"]
        else:
            graph = json.loads((chapter_root / "concept-graph.json").read_text(encoding="utf-8"))
            nodes = len(graph.get("nodes") or [])
            bootstrap_status = "already_present"
        chapter_ready = True

    return {
        "name": name,
        "commit": commit,
        "path": str(target),
        "status": fetch_status,
        "chapter_ready": chapter_ready,
        "chapter_path": chapter_path,
        "nodes": nodes,
        "bootstrap_status": bootstrap_status,
    }
