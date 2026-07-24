"""Derive per-concept BKT mastery from append-only session question logs."""

from __future__ import annotations

from pathlib import Path

from apore.runtime import state
from apore.runtime.bkt import (
    DEFAULT_PARAMS,
    BKTParams,
    ConceptMastery,
    empty_mastery,
    replay,
)

_SKIP_SESSION_NAMES = frozenset({"_bank_gen.md"})


def _session_files(sessions_dir: Path) -> list[Path]:
    if not sessions_dir.is_dir():
        return []
    files: list[Path] = []
    for path in sorted(sessions_dir.glob("*.md")):
        if path.name in _SKIP_SESSION_NAMES:
            continue
        files.append(path)
    return files


def collect_observations(
    sessions_dir: Path,
    knowledge_source: str,
) -> dict[str, list[tuple[str, int, int]]]:
    """Gather (date, Q#, obs) per concept for sessions matching knowledge_source.

    ``obs`` is 1 for correct=yes, 0 for correct=no. Other correctness values
    are dropped. Within each concept, callers should sort by (date, Q#).
    """
    by_concept: dict[str, list[tuple[str, int, int]]] = {}
    for path in _session_files(sessions_dir):
        try:
            meta = state.read_session_meta(path)
        except OSError:
            continue
        if meta.get("knowledge_source") != knowledge_source:
            continue
        try:
            rows = state.parse_question_log(path)
        except (OSError, ValueError):
            continue
        for row in rows:
            correct = (row.get("correct") or "").strip().lower()
            if correct not in ("yes", "no"):
                continue
            concept = (row.get("concept") or "").strip()
            if not concept:
                continue
            date = (row.get("date") or "").strip()
            try:
                qnum = int(str(row.get("Q#") or "0").strip() or "0")
            except ValueError:
                qnum = 0
            obs = 1 if correct == "yes" else 0
            by_concept.setdefault(concept, []).append((date, qnum, obs))
    return by_concept


def derive_mastery(
    sessions_dir: Path,
    knowledge_source: str,
    concept_ids: list[str],
    params: BKTParams | None = None,
) -> dict[str, ConceptMastery]:
    """Return BKT mastery for each concept_id (New when never observed)."""
    params = params or DEFAULT_PARAMS
    raw = collect_observations(sessions_dir, knowledge_source)
    result: dict[str, ConceptMastery] = {}
    for concept_id in concept_ids:
        events = raw.get(concept_id) or []
        if not events:
            result[concept_id] = empty_mastery()
            continue
        events.sort(key=lambda e: (e[0], e[1]))
        result[concept_id] = replay((obs for _, _, obs in events), params)
    return result


def derive_mastery_floats(
    sessions_dir: Path,
    knowledge_source: str,
    concept_ids: list[str] | None = None,
    params: BKTParams | None = None,
) -> dict[str, float]:
    """BKT P(L) map for selection / SessionStateResponse.

    Only includes concepts with at least one observation (omit unknowns).
    When ``concept_ids`` is None, includes every concept seen in matching logs.
    """
    params = params or DEFAULT_PARAMS
    raw = collect_observations(sessions_dir, knowledge_source)
    ids = list(concept_ids) if concept_ids is not None else sorted(raw.keys())
    out: dict[str, float] = {}
    for concept_id in ids:
        events = raw.get(concept_id) or []
        if not events:
            continue
        events.sort(key=lambda e: (e[0], e[1]))
        mastery = replay((obs for _, _, obs in events), params)
        if mastery.p_mastery is not None:
            out[concept_id] = mastery.p_mastery
    return out
