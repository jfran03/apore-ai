"""Fetch fixtures defined in apore/fixtures/manifest.json.

Run from program/ working directory:
    python scripts/fetch_fixture.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from apore.setup.fixtures import fetch_fixture


def main() -> None:
    program_root = Path(__file__).parent.parent
    manifest_path = program_root / "apore" / "fixtures" / "manifest.json"

    if not manifest_path.exists():
        print(f"Error: manifest.json not found at {manifest_path}", file=sys.stderr)
        print("Run this script from the program/ directory.", file=sys.stderr)
        sys.exit(1)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    fixtures = manifest.get("fixtures", {})

    for name in fixtures:
        print(f"[{name}] fetching …")
        try:
            summary = fetch_fixture(program_root, name)
        except RuntimeError as exc:
            print(f"  ERROR: {exc}", file=sys.stderr)
            sys.exit(1)

        print(f"[{name}] {summary['status']} @ {summary['commit'][:12]}")
        print(f"[{name}] path: {summary['path']}")
        if summary.get("bootstrap_status"):
            print(
                f"[{name}] concept graph: {summary['bootstrap_status']} "
                f"({summary.get('nodes', 0)} nodes)"
            )
        if summary.get("chapter_ready"):
            print(f"[{name}] chapter ready: {summary.get('chapter_path')}")
        elif not summary.get("chapter_ready"):
            print(f"[{name}] warning: no chapter with wiki pages found", file=sys.stderr)


if __name__ == "__main__":
    main()
