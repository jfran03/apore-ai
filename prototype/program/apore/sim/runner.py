"""Headless session runner for simulated student experiments."""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path

import json

from apore.providers.stub import StubProvider
from apore.providers import get_provider
from apore.providers.base import Provider
from apore.providers.anthropic_adapter import DEFAULT_MODEL as DEFAULT_ANTHROPIC_MODEL
from apore.knowledge.chapter import resolve_chapter
from apore.runtime import state as state_mod
from apore.runtime.core import run_question_cycle
from apore.sim.convergence import write_artifacts
from apore.sim.student import SimulatedStudent, StudentProfile


def _make_minimal_program_root(tmp_path: Path) -> Path:
    """Create a minimal program_root directory with AGENTS.md and protocol stubs."""
    root = tmp_path / "sim_program_root"
    (root / "shared" / "protocols").mkdir(parents=True, exist_ok=True)

    (root / "AGENTS.md").write_text("# Tutor Harness\nSystem content.", encoding="utf-8")
    (root / "shared" / "protocols" / "generate-question.md").write_text(
        "# Protocol: generate-question\nGenerate a question.", encoding="utf-8"
    )
    (root / "shared" / "protocols" / "extract-signals.md").write_text(
        "# Protocol: extract-signals\nExtract signals.", encoding="utf-8"
    )

    chapter = root / "domains" / "_sim" / "chapters" / "01-intro"
    chapter.mkdir(parents=True)
    graph = {
        "nodes": [
            {
                "id": "set_theory_intro",
                "label": "Introduction to Set Theory",
                "depth": 1,
            }
        ],
        "edges": [],
    }
    (chapter / "concept-graph.json").write_text(json.dumps(graph), encoding="utf-8")
    wiki = chapter / "wiki"
    wiki.mkdir()
    (wiki / "set_theory_intro.md").write_text("# Set theory intro\n\nContent.", encoding="utf-8")
    return root


def run_sessions(
    num_sessions: int,
    questions_per_session: int,
    profile: StudentProfile,
    provider_name: str = "anthropic",
    model: str = DEFAULT_ANTHROPIC_MODEL,
    fixture_name: str = "apore-lite",
    knowledge_source: str | None = None,
    output_dir: Path | None = None,
    program_root: Path | None = None,
    reset_between_sessions: bool = False,
) -> list[dict]:
    """Run num_sessions sessions of questions_per_session questions each.

    By default (reset_between_sessions=False) learner state carries over from
    one session to the next, so difficulty accumulates across sessions — this
    produces a downward error trend when target_ability > initial difficulty.

    When reset_between_sessions=True each session starts from difficulty=0.5
    (fresh learner-state.md), which is useful for ablation studies.

    Returns a list of session trajectory dicts, each with keys:
        session_id, session_number, difficulties (list of float per question).
    """
    provider: Provider
    if provider_name == "stub":
        provider = StubProvider()
    else:
        provider = get_provider(provider_name)

    student = SimulatedStudent(profile)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        if program_root is None:
            prog_root = _make_minimal_program_root(tmp)
            kb_source = knowledge_source or "domain:_sim/01-intro"
        else:
            prog_root = program_root
            kb_source = knowledge_source or f"fixture:{fixture_name}"

        chapter = resolve_chapter(kb_source, prog_root)

        # Shared state file — carried over across sessions unless reset requested.
        shared_state_path = tmp / "learner-state.md"
        state_mod.initialize(shared_state_path)

        trajectories: list[dict] = []

        for session_idx in range(1, num_sessions + 1):
            session_id = f"sim-{session_idx}-{uuid.uuid4().hex[:8]}"

            if reset_between_sessions:
                state_path = tmp / f"state_{session_idx}.md"
                state_mod.initialize(state_path)
            else:
                state_path = shared_state_path

            difficulties: list[float] = []

            for q_num in range(1, questions_per_session + 1):
                learner_response = student.respond(f"Question {q_num}")
                metadata = {
                    "fixture_commit": fixture_name,
                    "provider": provider_name,
                    "model": model,
                }
                result = run_question_cycle(
                    session_id=session_id,
                    question_number=q_num,
                    learner_response=learner_response,
                    chapter=chapter,
                    concept_id="set_theory_intro",
                    state_path=state_path,
                    provider=provider,
                    model=model,
                    config={},
                    metadata=metadata,
                    program_root=prog_root,
                )
                difficulties.append(result.new_difficulty)

            trajectories.append(
                {
                    "session_id": session_id,
                    "session_number": session_idx,
                    "difficulties": difficulties,
                }
            )

        if output_dir is not None:
            # Load fixture commit from manifest
            manifest_path = Path(__file__).parent.parent / "fixtures" / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            fixture_commit = manifest["fixtures"].get(fixture_name, {}).get("commit", fixture_name)

            write_artifacts(
                sessions=trajectories,
                profile=student.profile,
                output_dir=output_dir,
                fixture_commit=fixture_commit,
                provider=provider_name,
                model=model,
            )

    return trajectories
