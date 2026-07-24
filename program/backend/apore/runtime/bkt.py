"""Bayesian Knowledge Tracing (BKT) for per-concept mastery.

Derive-on-read model: replay ordered correct/incorrect observations to obtain
P(L) per concept. No forgetting (P(F) = 0). See PROGRESSION.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal

MasteryBand = Literal["new", "struggling", "learning", "proficient"]


@dataclass(frozen=True)
class BKTParams:
    """Global BKT defaults (conventional ITS starting points)."""

    p_L0: float = 0.0
    p_T: float = 0.1
    p_G: float = 0.2
    p_S: float = 0.1
    p_F: float = 0.0  # no decay in v1


DEFAULT_PARAMS = BKTParams()

COVERED_THRESHOLD = 0.7


@dataclass(frozen=True)
class ConceptMastery:
    p_mastery: float | None
    band: MasteryBand
    n_observed: int
    display_pct: int | None


def band_for(p_mastery: float | None, n_observed: int) -> MasteryBand:
    """Map P(L) and observation count to a learner-facing band."""
    if n_observed <= 0 or p_mastery is None:
        return "new"
    if p_mastery >= COVERED_THRESHOLD:
        return "proficient"
    if p_mastery >= 0.3:
        return "learning"
    return "struggling"


def display_pct_for(p_mastery: float | None, n_observed: int) -> int | None:
    if n_observed <= 0 or p_mastery is None:
        return None
    return int(round(p_mastery * 100))


def update_step(
    p: float,
    obs: int,
    params: BKTParams = DEFAULT_PARAMS,
    *,
    p_S: float | None = None,
) -> float:
    """One BKT update: emission → posterior → learn transition (no forget).

    ``obs`` is 1 for correct, 0 for incorrect.
    Optional ``p_S`` overrides slip for evidence-quality modulation (v1.1).
    """
    if obs not in (0, 1):
        raise ValueError(f"obs must be 0 or 1, got {obs!r}")
    slip = params.p_S if p_S is None else p_S
    slip = max(0.0, min(1.0, slip))
    guess = max(0.0, min(1.0, params.p_G))
    p = max(0.0, min(1.0, p))

    p_correct = p * (1.0 - slip) + (1.0 - p) * guess
    # Numerical guard: avoid divide-by-zero on degenerate params.
    p_correct = min(max(p_correct, 1e-12), 1.0 - 1e-12)

    if obs == 1:
        posterior = p * (1.0 - slip) / p_correct
    else:
        posterior = p * slip / (1.0 - p_correct)

    posterior = max(0.0, min(1.0, posterior))
    # P(F)=0: no forget between opportunities; only learn transition.
    learned = posterior + (1.0 - posterior) * params.p_T
    return max(0.0, min(1.0, learned))


def replay(
    observations: Iterable[int],
    params: BKTParams = DEFAULT_PARAMS,
) -> ConceptMastery:
    """Replay an ordered sequence of binary observations → final mastery."""
    obs_list = list(observations)
    if not obs_list:
        return ConceptMastery(
            p_mastery=None,
            band="new",
            n_observed=0,
            display_pct=None,
        )

    p = params.p_L0
    for obs in obs_list:
        p = update_step(p, obs, params)

    n = len(obs_list)
    return ConceptMastery(
        p_mastery=p,
        band=band_for(p, n),
        n_observed=n,
        display_pct=display_pct_for(p, n),
    )


def empty_mastery() -> ConceptMastery:
    return ConceptMastery(
        p_mastery=None,
        band="new",
        n_observed=0,
        display_pct=None,
    )
