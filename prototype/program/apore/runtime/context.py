"""Context assembly for LLM calls (PRD §5.3)."""

from __future__ import annotations

from pathlib import Path

from markitdown import MarkItDown

from apore.runtime.paths import get_program_root

_VALID_PROTOCOLS = {"generate-question", "extract-signals"}
_markitdown = MarkItDown()


def assemble_prompt(
    protocol: str,
    grounding_paths: list[Path],
    learner_state_path: Path,
    program_root: Path | None = None,
) -> dict:
    """Return {"system": str, "messages": [{"role": "user", "content": str}]}.

    System message: content of AGENTS.md
    User message: [protocol content] + [grounding slice] + [learner state]
    """
    if protocol not in _VALID_PROTOCOLS:
        raise ValueError(f"Unknown protocol {protocol!r}; expected one of {_VALID_PROTOCOLS}")

    root = program_root if program_root is not None else get_program_root()

    system = (root / "AGENTS.md").read_text(encoding="utf-8")

    protocol_text = (root / "shared" / "protocols" / f"{protocol}.md").read_text(encoding="utf-8")

    grounding_parts: list[str] = []
    for p in grounding_paths:
        try:
            grounding_parts.append(_markitdown.convert(str(p)).text_content)
        except Exception as exc:
            raise RuntimeError(f"Failed to convert grounding file {p}: {exc}") from exc
    grounding_text = "\n\n".join(grounding_parts)

    learner_state_text = learner_state_path.read_text(encoding="utf-8")

    user_content = (
        f"## Protocol\n\n{protocol_text}\n\n"
        f"## Grounding Context\n\n{grounding_text}\n\n"
        f"## Learner State\n\n{learner_state_text}"
    )

    return {
        "system": system,
        "messages": [{"role": "user", "content": user_content}],
    }
