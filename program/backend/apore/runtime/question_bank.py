"""Load, validate, and select questions from chapter question-bank.json."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from apore.knowledge.chapter import ChapterContext, ConceptGraph, select_next_concept

VALID_TYPES = frozenset({"recall", "apply", "synthesis"})
_TYPE_RELAX_ORDER = ("synthesis", "apply", "recall")


class QuestionBankExhaustedError(Exception):
    """No bank question matches selection criteria."""


@dataclass(frozen=True)
class BankQuestion:
    id: str
    concept_id: str
    type: str
    intended_difficulty: float
    text: str


@dataclass
class QuestionBank:
    version: int
    questions: list[BankQuestion]

    @classmethod
    def from_dict(cls, data: dict) -> QuestionBank:
        version = int(data.get("version", 1))
        questions: list[BankQuestion] = []
        for item in data.get("questions") or []:
            if not isinstance(item, dict):
                continue
            qid = item.get("id")
            concept_id = item.get("concept_id")
            qtype = item.get("type")
            text = item.get("text")
            if not qid or not concept_id or not qtype or not text:
                continue
            questions.append(
                BankQuestion(
                    id=str(qid),
                    concept_id=str(concept_id),
                    type=str(qtype).lower(),
                    intended_difficulty=float(item.get("intended_difficulty", 0.5)),
                    text=str(text).strip(),
                )
            )
        return cls(version=version, questions=questions)

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "questions": [
                {
                    "id": q.id,
                    "concept_id": q.concept_id,
                    "type": q.type,
                    "intended_difficulty": round(q.intended_difficulty, 2),
                    "text": q.text,
                }
                for q in self.questions
            ],
        }


def type_for_scalar(scalar: float) -> str:
    """Map learner difficulty scalar to question type (generate-question Step 2)."""
    if scalar <= 0.35:
        return "recall"
    if scalar <= 0.65:
        return "apply"
    return "synthesis"


def burst_type_for_index(burst_index: int) -> str:
    """Calibration burst type override (generate-question Step 3)."""
    if burst_index == 0:
        return "recall"
    if burst_index == 1:
        return "apply"
    return "recall"


def load_question_bank(chapter: ChapterContext) -> QuestionBank | None:
    path = chapter.question_bank_path
    if not path.is_file():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    return QuestionBank.from_dict(raw)


def save_question_bank(path: Path, bank: QuestionBank) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(bank.to_dict(), indent=2) + "\n", encoding="utf-8")


def validate_question_bank(bank: QuestionBank, graph: ConceptGraph) -> list[str]:
    """Return validation error messages; empty list means valid."""
    errors: list[str] = []
    seen_ids: set[str] = set()
    for q in bank.questions:
        if q.id in seen_ids:
            errors.append(f"duplicate question id: {q.id!r}")
        seen_ids.add(q.id)
        if q.concept_id not in graph.nodes:
            errors.append(f"unknown concept_id {q.concept_id!r} for question {q.id!r}")
        if q.type not in VALID_TYPES:
            errors.append(f"invalid type {q.type!r} for question {q.id!r}")
        if not (0.1 <= q.intended_difficulty <= 0.9):
            errors.append(
                f"intended_difficulty {q.intended_difficulty} out of range for {q.id!r}"
            )
        if not q.text.strip():
            errors.append(f"empty text for question {q.id!r}")
    return errors


def select_concept_for_burst(
    graph: ConceptGraph,
    *,
    question_number: int,
    mastery: dict[str, float] | None,
    bank: QuestionBank,
    allowed_concept_ids: set[str] | None = None,
) -> str:
    """Pick concept by depth tier for calibration burst (questions 1–3)."""
    burst_index = question_number - 1
    if burst_index < 0 or burst_index > 2:
        return select_next_concept(
            graph,
            mastery=mastery,
            allowed_concept_ids=allowed_concept_ids,
        )

    low_d, mid_d, high_d = _depth_tiers(graph, allowed_concept_ids=allowed_concept_ids)
    targets = [low_d, mid_d, high_d]
    target_depth = targets[burst_index]

    candidates = [
        n
        for n in graph.nodes.values()
        if n.depth == target_depth
        and _concept_allowed(n.id, allowed_concept_ids)
        and _concept_has_bank_questions(bank, n.id)
    ]
    if not candidates:
        candidates = [
            n
            for n in graph.nodes.values()
            if _concept_allowed(n.id, allowed_concept_ids)
            and _concept_has_bank_questions(bank, n.id)
        ]
    if not candidates:
        return select_next_concept(
            graph,
            mastery=mastery,
            allowed_concept_ids=allowed_concept_ids,
        )

    candidates.sort(key=lambda n: n.id)
    return candidates[0].id


def _concept_allowed(concept_id: str, allowed_concept_ids: set[str] | None) -> bool:
    if allowed_concept_ids is None:
        return True
    return concept_id in allowed_concept_ids


def _concept_has_bank_questions(bank: QuestionBank, concept_id: str) -> bool:
    return any(q.concept_id == concept_id for q in bank.questions)


def _depth_tiers(
    graph: ConceptGraph,
    *,
    allowed_concept_ids: set[str] | None = None,
) -> tuple[int, int, int]:
    """Return (low, mid, high) depth values from graph nodes."""
    depths = sorted(
        {
            n.depth
            for n in graph.nodes.values()
            if _concept_allowed(n.id, allowed_concept_ids)
        }
    )
    if not depths:
        return (0, 0, 0)
    if len(depths) == 1:
        d = depths[0]
        return (d, d, d)
    low = depths[0]
    high = depths[-1]
    mid = depths[len(depths) // 2]
    return (low, mid, high)


def _deprioritize_last_concept(
    concept_ids: list[str], last_concept_id: str | None
) -> list[str]:
    if not last_concept_id:
        return concept_ids
    without = [c for c in concept_ids if c != last_concept_id]
    with_last = [c for c in concept_ids if c == last_concept_id]
    return without + with_last


def _matching_candidates(
    bank: QuestionBank,
    *,
    concept_id: str,
    qtype: str,
    asked_ids: set[str],
    allow_reuse: bool,
) -> list[BankQuestion]:
    matches = [
        q for q in bank.questions if q.concept_id == concept_id and q.type == qtype
    ]
    if not allow_reuse:
        matches = [q for q in matches if q.id not in asked_ids]
    if not matches:
        return []
    matches.sort(key=lambda q: (q.id in asked_ids, q.id))
    return matches


def _relax_types(primary: str) -> list[str]:
    """Try primary type first, then relax downward."""
    order = list(_TYPE_RELAX_ORDER)
    if primary not in order:
        return [primary]
    idx = order.index(primary)
    return [primary] + [t for t in order[idx + 1 :] if t != primary]


def _relax_types_upward(primary: str) -> list[str]:
    """Types harder than primary when the bank lacks easier matches."""
    order = list(_TYPE_RELAX_ORDER)
    if primary not in order:
        return []
    idx = order.index(primary)
    return [t for t in order[:idx] if t != primary]


def _pick_from_concepts(
    bank: QuestionBank,
    concept_ids: list[str],
    *,
    type_order: list[str],
    asked_ids: set[str],
    allow_reuse: bool,
) -> BankQuestion | None:
    for cid in concept_ids:
        for try_type in type_order:
            candidates = _matching_candidates(
                bank,
                concept_id=cid,
                qtype=try_type,
                asked_ids=asked_ids,
                allow_reuse=allow_reuse,
            )
            if candidates:
                return candidates[0]
    return None


def _weak_concept_ids(
    graph: ConceptGraph,
    mastery: dict[str, float],
    *,
    allowed_concept_ids: set[str] | None = None,
) -> list[str]:
    """Concept ids with P(L) < 0.7 (observed weak first, then never-seen)."""
    allowed = [
        n
        for n in graph.nodes.values()
        if _concept_allowed(n.id, allowed_concept_ids) and mastery.get(n.id, 0.0) < 0.7
    ]
    observed_weak = sorted(
        (n.id for n in allowed if n.id in mastery),
        key=lambda cid: (mastery.get(cid, 0.0), cid),
    )
    if observed_weak:
        return observed_weak
    return sorted(n.id for n in allowed)


def select_question(
    *,
    bank: QuestionBank,
    graph: ConceptGraph,
    concept_id: str | None,
    scalar: float,
    asked_ids: set[str],
    question_number: int,
    mastery: dict[str, float] | None = None,
    requested_concept_id: str | None = None,
    focus_mode: str = "adaptive",
    last_concept_id: str | None = None,
    allowed_concept_ids: set[str] | None = None,
) -> BankQuestion:
    """Select a bank question; avoid back-to-back same concept, prefer unused IDs."""
    mastery = mastery or {}
    weak_only = focus_mode == "weak_points"
    allowed = allowed_concept_ids

    if allowed is not None and not allowed:
        raise QuestionBankExhaustedError("No concepts selected for this session")

    if weak_only:
        weak_ids = _weak_concept_ids(graph, mastery, allowed_concept_ids=allowed)
        if not weak_ids:
            raise QuestionBankExhaustedError(
                "No weak concepts remain for focused review in this session"
            )
        selected_id = select_next_concept(
            graph,
            requested_id=requested_concept_id or concept_id,
            mastery=mastery,
            scalar=scalar,
            weak_only=True,
            allowed_concept_ids=allowed,
        )
        qtype = type_for_scalar(scalar)
        concept_ids_to_try = [selected_id] + [c for c in weak_ids if c != selected_id]
    elif question_number <= 3:
        selected_id = select_concept_for_burst(
            graph,
            question_number=question_number,
            mastery=mastery,
            bank=bank,
            allowed_concept_ids=allowed,
        )
        qtype = burst_type_for_index(question_number - 1)
        concept_ids_to_try = [selected_id]
        if not requested_concept_id and not concept_id:
            pool = [
                n.id
                for n in sorted(graph.nodes.values(), key=lambda n: (n.depth, n.id))
                if n.id != selected_id and _concept_allowed(n.id, allowed)
            ]
            concept_ids_to_try.extend(pool)
    else:
        selected_id = select_next_concept(
            graph,
            requested_id=requested_concept_id or concept_id,
            mastery=mastery,
            scalar=scalar,
            allowed_concept_ids=allowed,
        )
        qtype = type_for_scalar(scalar)
        concept_ids_to_try = [selected_id]
        if not requested_concept_id and not concept_id:
            pool = [
                n.id
                for n in sorted(graph.nodes.values(), key=lambda n: (n.depth, n.id))
                if n.id != selected_id and _concept_allowed(n.id, allowed)
            ]
            concept_ids_to_try.extend(pool)

    # Drop any concepts outside the allowed set (e.g. pinned request mismatch).
    concept_ids_to_try = [
        cid for cid in concept_ids_to_try if _concept_allowed(cid, allowed)
    ]
    if not concept_ids_to_try:
        raise QuestionBankExhaustedError(
            "No questions available for the selected concepts in this session"
        )

    ordered_concepts = _deprioritize_last_concept(concept_ids_to_try, last_concept_id)
    downward_types = _relax_types(qtype)
    upward_types = _relax_types_upward(qtype)
    single_concept_session = len(concept_ids_to_try) == 1

    # Tier 1: difficulty-appropriate types, prefer unused questions.
    picked = _pick_from_concepts(
        bank,
        ordered_concepts,
        type_order=downward_types,
        asked_ids=asked_ids,
        allow_reuse=False,
    )
    if picked:
        return picked

    # Tier 2: same type rules, allow question reuse.
    picked = _pick_from_concepts(
        bank,
        ordered_concepts,
        type_order=downward_types,
        asked_ids=asked_ids,
        allow_reuse=True,
    )
    if picked:
        return picked

    # Tier 3: widen type upward when bank lacks easier matches.
    if upward_types:
        picked = _pick_from_concepts(
            bank,
            ordered_concepts,
            type_order=upward_types,
            asked_ids=asked_ids,
            allow_reuse=True,
        )
        if picked:
            return picked

    # Tier 4: single-concept or no-alternative edge case — allow last concept.
    if single_concept_session or (last_concept_id and last_concept_id in concept_ids_to_try):
        all_types = downward_types + [t for t in upward_types if t not in downward_types]
        picked = _pick_from_concepts(
            bank,
            concept_ids_to_try,
            type_order=all_types,
            asked_ids=asked_ids,
            allow_reuse=True,
        )
        if picked:
            return picked

    if weak_only:
        raise QuestionBankExhaustedError(
            "No unused questions remain for weak concepts in this session"
        )
    raise QuestionBankExhaustedError(
        "No questions available for a different concept than the previous one"
    )


def format_question_block(entry: BankQuestion, graph: ConceptGraph) -> str:
    """Build protocol-style QUESTION block for dialogue seeding."""
    node = graph.get(entry.concept_id)
    depth = node.depth if node else 0
    return (
        "QUESTION\n"
        f"concept: {entry.concept_id}\n"
        f"type: {entry.type}\n"
        f"depth: {depth}\n"
        f"intended_difficulty: {entry.intended_difficulty:.2f}\n"
        "---\n"
        f"{entry.text}"
    )


def depth_for_question(entry: BankQuestion, graph: ConceptGraph) -> int:
    node = graph.get(entry.concept_id)
    return node.depth if node else 0
