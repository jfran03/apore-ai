"""Derive per-concept BKT mastery from append-only session question logs."""

from __future__ import annotations

from dataclasses import dataclass
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

# (session_created_at, Q#, obs, session_id, assisted)
Observation = tuple[str, int, int, str, bool]


@dataclass(frozen=True)
class ConceptMasteryDelta:
    """Session movement for one concept: mastery as if this session never
    happened (`before`) vs including it (`after`).

    Given chronological ordering by ``(session_created_at, Q#)``, ``before``
    equals the true prior state at the start of this session.
    """

    before: ConceptMastery
    after: ConceptMastery
    n_observed_session: int


def _session_files(sessions_dir: Path) -> list[Path]:
    if not sessions_dir.is_dir():
        return []
    files: list[Path] = []
    for path in sorted(sessions_dir.glob("*.md")):
        if path.name in _SKIP_SESSION_NAMES:
            continue
        files.append(path)
    return files


def _sort_key(event: Observation) -> tuple[str, int]:
    return (event[0], event[1])


def collect_observations(
    sessions_dir: Path,
    knowledge_source: str,
) -> dict[str, list[Observation]]:
    """Gather observations per concept for sessions matching knowledge_source.

    Each observation is ``(session_created_at, Q#, obs, session_id, assisted)``
    where ``obs`` is 1 for correct=yes, 0 for correct=no. Other correctness
    values are dropped. Missing ``assisted`` cells default to False so legacy
    session files are never retroactively rescored. Callers should sort by
    ``(session_created_at, Q#)``.
    """
    by_concept: dict[str, list[Observation]] = {}
    for path in _session_files(sessions_dir):
        try:
            meta = state.read_session_meta(path)
        except OSError:
            continue
        if meta.get("knowledge_source") != knowledge_source:
            continue
        created_at = (meta.get("created_at") or "").strip()
        session_id = (meta.get("id") or path.stem).strip()
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
            try:
                qnum = int(str(row.get("Q#") or "0").strip() or "0")
            except ValueError:
                qnum = 0
            obs = 1 if correct == "yes" else 0
            assisted = (row.get("assisted") or "").strip().lower() == "yes"
            by_concept.setdefault(concept, []).append(
                (created_at, qnum, obs, session_id, assisted)
            )
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
        events.sort(key=_sort_key)
        result[concept_id] = replay(
            [obs for _, _, obs, _, _ in events],
            params,
            assisted=[a for *_, a in events],
        )
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
        events.sort(key=_sort_key)
        mastery = replay(
            [obs for _, _, obs, _, _ in events],
            params,
            assisted=[a for *_, a in events],
        )
        if mastery.p_mastery is not None:
            out[concept_id] = mastery.p_mastery
    return out


def derive_mastery_delta(
    sessions_dir: Path,
    knowledge_source: str,
    session_id: str,
    concept_ids: list[str] | None = None,
    params: BKTParams | None = None,
) -> dict[str, ConceptMasteryDelta]:
    """Per-concept mastery movement attributable to ``session_id``.

    Only concepts with ≥1 observation in this session are returned.
    ``before`` replays all other sessions; ``after`` replays everything.
    """
    params = params or DEFAULT_PARAMS
    raw = collect_observations(sessions_dir, knowledge_source)
    if concept_ids is not None:
        ids = list(concept_ids)
    else:
        ids = sorted(
            cid
            for cid, events in raw.items()
            if any(e[3] == session_id for e in events)
        )

    result: dict[str, ConceptMasteryDelta] = {}
    for concept_id in ids:
        events = list(raw.get(concept_id) or [])
        events.sort(key=_sort_key)
        session_events = [e for e in events if e[3] == session_id]
        if not session_events:
            continue
        before_events = [e for e in events if e[3] != session_id]
        before = (
            replay(
                [obs for _, _, obs, _, _ in before_events],
                params,
                assisted=[a for *_, a in before_events],
            )
            if before_events
            else empty_mastery()
        )
        after = replay(
            [obs for _, _, obs, _, _ in events],
            params,
            assisted=[a for *_, a in events],
        )
        result[concept_id] = ConceptMasteryDelta(
            before=before,
            after=after,
            n_observed_session=len(session_events),
        )
    return result
