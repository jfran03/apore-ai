"""Stub-compile a chapter: sources/ → concept-graph.json + wiki/.

Usage (from program/):
    python scripts/stub_compile_chapter.py domains/my-domain/chapters/01-intro
"""

from __future__ import annotations

import sys
from pathlib import Path

from apore.setup.stub_compile import stub_compile_chapter


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python scripts/stub_compile_chapter.py <chapter-root>", file=sys.stderr)
        sys.exit(1)

    chapter_root = Path(sys.argv[1]).resolve()
    if not chapter_root.is_dir():
        print(f"Not a directory: {chapter_root}", file=sys.stderr)
        sys.exit(1)

    summary = stub_compile_chapter(chapter_root)
    print(f"Compiled {summary['nodes']} concepts → {summary['concept_graph']}")


if __name__ == "__main__":
    main()
