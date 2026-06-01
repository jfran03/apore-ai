"""Fetch fixtures defined in apore/fixtures/manifest.json.

Run from program/ working directory:
    python scripts/fetch_fixture.py
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


def _run(cmd: list[str], cwd: Path) -> None:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ERROR: {result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)


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


def main() -> None:
    program_root = Path(__file__).parent.parent
    manifest_path = program_root / "apore" / "fixtures" / "manifest.json"

    if not manifest_path.exists():
        print(f"Error: manifest.json not found at {manifest_path}", file=sys.stderr)
        print("Run this script from the program/ directory.", file=sys.stderr)
        sys.exit(1)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    fixtures = manifest.get("fixtures", {})

    for name, spec in fixtures.items():
        url: str = spec["url"]
        commit: str = spec["commit"]
        target: Path = program_root / spec["target"]

        print(f"[{name}] target: {target}")

        if target.exists() and _current_commit(target) == commit:
            print(f"[{name}] already at {commit[:12]} — skipping")
            continue

        if target.exists():
            print(f"[{name}] wrong commit — re-cloning")
            shutil.rmtree(target)

        target.parent.mkdir(parents=True, exist_ok=True)
        print(f"[{name}] cloning {url} ...")
        _run(["git", "clone", "--depth", "1", url, str(target)], cwd=program_root)

        current = _current_commit(target)
        if current != commit:
            print(f"[{name}] checking out {commit[:12]} ...")
            _run(["git", "fetch", "--depth", "1", "origin", commit], cwd=target)
            _run(["git", "checkout", commit], cwd=target)

        print(f"[{name}] ready at {commit[:12]}")


if __name__ == "__main__":
    main()
