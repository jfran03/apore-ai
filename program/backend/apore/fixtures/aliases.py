"""Map legacy fixture: names to domain chapters (no .fixtures/ storage)."""

from __future__ import annotations

FIXTURE_DOMAIN_ALIASES: dict[str, tuple[str, str]] = {
    "apore-lite": ("discrete-math", "01-set-theory"),
}


def fixture_to_domain_chapter(fixture_name: str) -> tuple[str, str] | None:
    return FIXTURE_DOMAIN_ALIASES.get(fixture_name)
