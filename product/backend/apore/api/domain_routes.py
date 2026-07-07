"""Domain-workspace HTTP surface: /domains."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from apore.api.schemas import (
    WorkspaceChapterSummary,
    WorkspaceDomainCreate,
    WorkspaceDomainListResponse,
    WorkspaceDomainSummary,
)
from apore.domains import store
from apore.domains.store import DomainRecord

domain_router = APIRouter(prefix="/domains", tags=["domains"])


def _chapter_summaries(record: DomainRecord) -> list[WorkspaceChapterSummary]:
    chapters_root = store.chapters_dir(record)
    if not chapters_root.is_dir():
        return []
    out: list[WorkspaceChapterSummary] = []
    for chapter in sorted(p for p in chapters_root.iterdir() if p.is_dir()):
        wiki = chapter / "wiki"
        out.append(
            WorkspaceChapterSummary(
                id=chapter.name,
                has_concept_graph=(chapter / "concept-graph.json").is_file(),
                wiki_count=(
                    len([p for p in wiki.iterdir() if p.is_file()])
                    if wiki.is_dir()
                    else 0
                ),
                has_question_bank=(chapter / "question-bank.json").is_file(),
            )
        )
    return out


def _summary(record: DomainRecord) -> WorkspaceDomainSummary:
    chapters = _chapter_summaries(record)
    status = "ready" if any(c.has_concept_graph for c in chapters) else "empty"
    sessions_root = store.sessions_dir(record)
    session_count = (
        len([p for p in sessions_root.iterdir() if p.is_dir()])
        if sessions_root.is_dir()
        else 0
    )
    sources_root = store.sources_dir(record)
    source_files = (
        sorted(p.name for p in sources_root.iterdir() if p.is_file())
        if sources_root.is_dir()
        else []
    )
    return WorkspaceDomainSummary(
        id=record.domain_id,
        name=record.name,
        objective=record.objective,
        teaching_style=record.teaching_style,
        teaching_prompt=record.teaching_prompt,
        model_preference=record.model_preference,
        created_at=record.created_at,
        status=status,
        chapters=chapters,
        session_count=session_count,
        source_files=source_files,
    )


def _invalid_summary(item: store.InvalidDomain) -> WorkspaceDomainSummary:
    return WorkspaceDomainSummary(
        id=item.domain_id,
        name=item.domain_id,
        objective="",
        teaching_style="",
        teaching_prompt="",
        model_preference="",
        created_at="",
        status="invalid",
        reason=item.reason,
    )


@domain_router.get("", response_model=WorkspaceDomainListResponse)
def list_domains() -> WorkspaceDomainListResponse:
    records, invalid = store.list_domains()
    return WorkspaceDomainListResponse(
        domains=[_summary(r) for r in records] + [_invalid_summary(i) for i in invalid]
    )


@domain_router.post("", response_model=WorkspaceDomainSummary, status_code=201)
def create_domain(body: WorkspaceDomainCreate) -> WorkspaceDomainSummary:
    record = store.create_domain(
        name=body.name,
        objective=body.objective,
        teaching_style=body.teaching_style,
        teaching_prompt=body.teaching_prompt,
        model_preference=body.model_preference,
    )
    return _summary(record)


def _load_or_404(domain_id: str) -> DomainRecord:
    try:
        return store.load_domain(domain_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=f"Domain is invalid: {exc}") from exc


@domain_router.get("/{domain_id}", response_model=WorkspaceDomainSummary)
def get_domain(domain_id: str) -> WorkspaceDomainSummary:
    return _summary(_load_or_404(domain_id))
