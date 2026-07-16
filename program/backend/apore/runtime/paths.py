"""Resolve PROGRAM_ROOT — the directory that contains the `apore/` package."""

from __future__ import annotations

from pathlib import Path


def get_program_root() -> Path:
    """Return the `program/` directory (the parent of the `apore/` package)."""
    # This file lives at program/apore/runtime/paths.py
    # __file__ -> .../program/apore/runtime/paths.py
    # .parent   -> .../program/apore/runtime/
    # .parent   -> .../program/apore/
    # .parent   -> .../program/
    return Path(__file__).resolve().parent.parent.parent
