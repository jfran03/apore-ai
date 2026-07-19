"""Bounded LLM chapter compiler: normalized sources -> staged wiki + graph.

The compiler reads a chapter's normalized source markdown, asks the configured
provider to synthesize concept-oriented wiki pages and a prerequisite graph
(``compile-chapter`` protocol), validates the structured output, and writes it to
the chapter's ``.compile/staging`` directory. Nothing is published to the tutor
until a human approves the staged version.
"""

from __future__ import annotations

import json
from pathlib import Path

from apore.providers.base import Provider
from apore.setup.artifacts import (
    ArtifactValidationError,
    CompiledArtifact,
    staging_dir,
    validate_compiled_artifact,
    write_artifact_files,
)
from apore.setup.sources import normalized_texts, valid_source_ids

_PROTOCOL = "compile-chapter"


class CompileError(RuntimeError):
    """Raised when compilation cannot produce a valid artifact."""


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


def parse_compile_response(raw: str) -> CompiledArtifact:
    """Parse an LLM compile response into a CompiledArtifact."""
    stripped = _strip_code_fence(raw)
    candidate = _find_json_object(stripped) or stripped
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise CompileError(f"Compiler output was not valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise CompileError("Compiler output must be a JSON object")
    return CompiledArtifact.from_dict(parsed)


def _build_sources_block(sources: list[dict]) -> str:
    blocks = []
    for src in sources:
        blocks.append(f"### Source: {src['id']}\n\n{src['text'].strip()}\n")
    return "\n".join(blocks)


def run_compile(
    chapter_root: Path,
    *,
    provider: Provider,
    model: str,
    program_root: Path,
) -> CompiledArtifact:
    """Invoke the provider and return the parsed (unvalidated) artifact."""
    sources = normalized_texts(chapter_root)
    if not sources:
        raise CompileError(
            "No normalized sources to compile. Add sources that convert successfully."
        )

    system = (program_root / "AGENTS.md").read_text(encoding="utf-8")
    protocol_text = (
        program_root / "shared" / "protocols" / f"{_PROTOCOL}.md"
    ).read_text(encoding="utf-8")
    sources_block = _build_sources_block(sources)

    user_content = (
        f"## Protocol\n\n{protocol_text}\n\n"
        f"## Chapter Sources\n\n{sources_block}"
    )
    closing = (
        "Compile the chapter now. Output only the JSON object with `pages` and "
        "`edges` as specified. Cite only the source ids listed above."
    )
    messages = [
        {"role": "user", "content": user_content},
        {"role": "user", "content": closing},
    ]
    raw = provider.invoke(system, messages, model, {"protocol": _PROTOCOL})
    return parse_compile_response(raw)


def compile_to_staging(
    chapter_root: Path,
    *,
    provider: Provider,
    model: str,
    program_root: Path,
    version: int,
    source_hash: str,
) -> dict:
    """Run compilation, validate, and write the artifact to staging.

    Returns a summary dict. Raises CompileError or ArtifactValidationError on
    failure without touching the published (approved) artifact.
    """
    artifact = run_compile(
        chapter_root, provider=provider, model=model, program_root=program_root
    )
    errors = validate_compiled_artifact(artifact, valid_source_ids(chapter_root))
    if errors:
        raise ArtifactValidationError(errors)

    target = staging_dir(chapter_root)
    if target.exists():
        import shutil

        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    write_artifact_files(
        target, artifact, source_hash=source_hash, version=version
    )
    return {
        "version": version,
        "concept_count": len(artifact.pages),
        "edge_count": len(artifact.edges),
    }
