"""Question bank I/O, validation, and LLM-backed generation."""

from __future__ import annotations

import json
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

from apore.knowledge.chapter import (
    ChapterContext,
    get_wiki_paths,
    load_concept_graph,
    resolve_chapter,
)
from apore.providers.base import Provider
from apore.runtime.context import assemble_prompt
from apore.runtime.question_bank import (
    BankQuestion,
    QuestionBank,
    load_question_bank,
    save_question_bank,
    validate_question_bank,
)

_TYPE_DIFFICULTY = {
    "recall": (0.2, 0.3),
    "apply": (0.45, 0.55),
    "synthesis": (0.7, 0.8),
}


def _strip_code_fence(text: str) -> str:
    lines = text.strip().splitlines()
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _find_json_object(text: str) -> str | None:
    for start in (i for i, ch in enumerate(text) if ch == "{"):
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : i + 1]
                    try:
                        json.loads(candidate)
                    except json.JSONDecodeError:
                        break
                    return candidate
    return None


def parse_bank_generation_response(raw: str) -> list[BankQuestion]:
    """Parse LLM JSON output into bank entries."""
    stripped = _strip_code_fence(raw)
    candidate = stripped
    found = _find_json_object(stripped)
    if found:
        candidate = found
    parsed = json.loads(candidate)
    if isinstance(parsed, list):
        items = parsed
    elif isinstance(parsed, dict):
        items = parsed.get("questions") or []
    else:
        raise ValueError("Expected JSON object or array of questions")

    bank = QuestionBank.from_dict({"version": 1, "questions": items})
    return bank.questions


def chapter_root_for_domain(program_root: Path, domain_id: str, chapter_id: str) -> Path:
    from apore.setup.paths import chapter_dir

    return chapter_dir(program_root, domain_id, chapter_id)


def get_bank_for_chapter(chapter_root: Path) -> QuestionBank:
    bank = load_question_bank(
        ChapterContext(
            knowledge_source="",
            chapter_root=chapter_root,
            display_name="",
        )
    )
    if bank is None:
        return QuestionBank(version=1, questions=[])
    return bank


def write_bank(chapter_root: Path, bank: QuestionBank, graph) -> list[str]:
    errors = validate_question_bank(bank, graph)
    if errors:
        raise ValueError("; ".join(errors))
    save_question_bank(chapter_root / "question-bank.json", bank)
    return errors


def add_question(
    chapter_root: Path,
    entry: BankQuestion,
    *,
    graph,
) -> QuestionBank:
    bank = get_bank_for_chapter(chapter_root)
    if any(q.id == entry.id for q in bank.questions):
        raise ValueError(f"Question id already exists: {entry.id!r}")
    bank.questions.append(entry)
    write_bank(chapter_root, bank, graph)
    return bank


def update_question(
    chapter_root: Path,
    question_id: str,
    *,
    graph,
    **fields: str | float | bool,
) -> BankQuestion:
    bank = get_bank_for_chapter(chapter_root)
    for i, q in enumerate(bank.questions):
        if q.id != question_id:
            continue
        updated = BankQuestion(
            id=question_id,
            concept_id=str(fields.get("concept_id", q.concept_id)),
            type=str(fields.get("type", q.type)).lower(),
            intended_difficulty=float(
                fields.get("intended_difficulty", q.intended_difficulty)
            ),
            text=str(fields.get("text", q.text)).strip(),
            scratchpad_eligible=bool(
                fields.get("scratchpad_eligible", q.scratchpad_eligible)
            ),
        )
        bank.questions[i] = updated
        write_bank(chapter_root, bank, graph)
        return updated
    raise KeyError(f"Question not found: {question_id!r}")


def delete_question(chapter_root: Path, question_id: str, *, graph) -> QuestionBank:
    bank = get_bank_for_chapter(chapter_root)
    new_questions = [q for q in bank.questions if q.id != question_id]
    if len(new_questions) == len(bank.questions):
        raise KeyError(f"Question not found: {question_id!r}")
    bank.questions = new_questions
    write_bank(chapter_root, bank, graph)
    return bank


def _default_questions_for_concept(concept_id: str) -> list[BankQuestion]:
    """Deterministic fallback when LLM parse fails (stub / tests)."""
    out: list[BankQuestion] = []
    for qtype, (d1, d2) in _TYPE_DIFFICULTY.items():
        for idx, diff in enumerate((d1, d2), start=1):
            # Apply/synthesis defaults are scratchpad-eligible; recall is not.
            eligible = qtype in ("apply", "synthesis")
            out.append(
                BankQuestion(
                    id=f"{concept_id}-{qtype}-{idx:02d}",
                    concept_id=concept_id,
                    type=qtype,
                    intended_difficulty=diff,
                    text=f"[{qtype}] Question about {concept_id.replace('_', ' ')} ({idx}).",
                    scratchpad_eligible=eligible,
                )
            )
    return out


def generate_questions_for_concept(
    *,
    concept_id: str,
    chapter: ChapterContext,
    state_path: Path,
    provider: Provider,
    model: str,
    program_root: Path,
) -> list[BankQuestion]:
    graph = load_concept_graph(chapter)
    wiki_paths = get_wiki_paths(chapter, concept_id, graph)
    assembled = assemble_prompt(
        "generate-question-bank",
        state_path,
        concept_id=concept_id,
        chapter=chapter,
        graph=graph,
        wiki_paths=wiki_paths,
        program_root=program_root,
    )
    closing = (
        f"Generate the JSON question bank entries for concept {concept_id!r} only. "
        "Six questions total: two recall, two apply, two synthesis."
    )
    messages = list(assembled["messages"]) + [{"role": "user", "content": closing}]
    raw = provider.invoke(
        assembled["system"],
        messages,
        model,
        {"protocol": "generate-question-bank"},
    )
    try:
        return parse_bank_generation_response(raw)
    except (json.JSONDecodeError, ValueError, KeyError):
        return _default_questions_for_concept(concept_id)


def _merge_question_batches(batches: list[list[BankQuestion]]) -> list[BankQuestion]:
    all_questions: list[BankQuestion] = []
    seen_ids: set[str] = set()
    for batch in batches:
        for q in batch:
            if q.id in seen_ids:
                q = BankQuestion(
                    id=f"{q.concept_id}-{q.type}-{len(seen_ids):02d}",
                    concept_id=q.concept_id,
                    type=q.type,
                    intended_difficulty=q.intended_difficulty,
                    text=q.text,
                    scratchpad_eligible=q.scratchpad_eligible,
                )
            seen_ids.add(q.id)
            all_questions.append(q)
    return all_questions


def _prepare_bank_generation(
    chapter_root: Path,
    *,
    program_root: Path,
    knowledge_source: str,
    state_path: Path | None = None,
) -> tuple[ChapterContext, object, Path]:
    chapter = resolve_chapter(knowledge_source, program_root)
    if chapter.chapter_root.resolve() != chapter_root.resolve():
        chapter = ChapterContext(
            knowledge_source=knowledge_source,
            chapter_root=chapter_root,
            display_name=chapter.display_name,
        )

    graph = load_concept_graph(chapter)
    if not graph.nodes:
        raise ValueError("concept-graph.json has no nodes")

    sp = state_path or (program_root / "sessions" / "_bank_gen.md")
    if not sp.is_file():
        from apore.runtime import state as learner_state

        sp.parent.mkdir(parents=True, exist_ok=True)
        learner_state.initialize(sp)

    return chapter, graph, sp


def generate_question_bank(
    chapter_root: Path,
    *,
    provider: Provider,
    model: str,
    program_root: Path,
    knowledge_source: str,
    state_path: Path | None = None,
    on_progress: Callable[[int, int], None] | None = None,
    max_workers: int = 4,
    provider_factory: Callable[[], Provider] | None = None,
) -> dict:
    """Generate or refresh the full chapter question bank."""
    chapter, graph, sp = _prepare_bank_generation(
        chapter_root,
        program_root=program_root,
        knowledge_source=knowledge_source,
        state_path=state_path,
    )
    concept_ids = graph.ordered_ids()
    batches = _generate_concepts_parallel(
        concept_ids,
        chapter=chapter,
        state_path=sp,
        provider=provider,
        model=model,
        program_root=program_root,
        on_progress=on_progress,
        max_workers=max_workers,
        provider_factory=provider_factory,
    )
    all_questions = _merge_question_batches(batches)
    bank = QuestionBank(version=1, questions=all_questions)
    write_bank(chapter_root, bank, graph)
    return {
        "questions": len(all_questions),
        "concepts": len(graph.nodes),
        "path": str(chapter_root / "question-bank.json"),
    }


def _generate_concepts_parallel(
    concept_ids: list[str],
    *,
    chapter: ChapterContext,
    state_path: Path,
    provider: Provider,
    model: str,
    program_root: Path,
    on_progress: Callable[[int, int], None] | None,
    max_workers: int,
    provider_factory: Callable[[], Provider] | None,
) -> list[list[BankQuestion]]:
    total = len(concept_ids)
    if total == 0:
        return []

    workers = min(max_workers, total)
    progress_lock = Lock()
    concepts_done = 0
    results: dict[str, list[BankQuestion]] = {}

    def _run_concept(concept_id: str) -> tuple[str, list[BankQuestion]]:
        worker_provider = provider_factory() if provider_factory else provider
        batch = generate_questions_for_concept(
            concept_id=concept_id,
            chapter=chapter,
            state_path=state_path,
            provider=worker_provider,
            model=model,
            program_root=program_root,
        )
        return concept_id, batch

    def _note_progress() -> None:
        nonlocal concepts_done
        with progress_lock:
            concepts_done += 1
            done = concepts_done
        if on_progress:
            on_progress(done, total)

    if workers <= 1:
        for concept_id in concept_ids:
            cid, batch = _run_concept(concept_id)
            results[cid] = batch
            _note_progress()
    else:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(_run_concept, concept_id): concept_id
                for concept_id in concept_ids
            }
            for future in as_completed(futures):
                cid, batch = future.result()
                results[cid] = batch
                _note_progress()

    return [results[cid] for cid in concept_ids]


def bank_response_dict(chapter_root: Path, graph) -> dict:
    bank = get_bank_for_chapter(chapter_root)
    return {
        "version": bank.version,
        "questions": [entry_with_depth(q, graph) for q in bank.questions],
        "path": str(chapter_root / "question-bank.json"),
    }


def entry_with_depth(entry: BankQuestion, graph) -> dict:
    from apore.runtime.question_bank import depth_for_question

    return {
        "id": entry.id,
        "concept_id": entry.concept_id,
        "type": entry.type,
        "intended_difficulty": entry.intended_difficulty,
        "text": entry.text,
        "scratchpad_eligible": entry.scratchpad_eligible,
        "depth": depth_for_question(entry, graph),
    }
