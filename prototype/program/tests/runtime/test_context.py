"""Tests for apore.runtime.context.assemble_prompt."""

from __future__ import annotations

import pytest
from pathlib import Path

from apore.runtime.context import assemble_prompt


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Return (program_root, wiki_html_path, learner_state_path)."""
    # Minimal program_root with AGENTS.md and protocol files
    root = tmp_path / "program"
    (root / "apore").mkdir(parents=True)
    (root / "shared" / "protocols").mkdir(parents=True)

    (root / "AGENTS.md").write_text("# Tutor Harness\nSystem content here.", encoding="utf-8")
    (root / "shared" / "protocols" / "generate-question.md").write_text(
        "# Protocol: generate-question\nProtocol instructions here.", encoding="utf-8"
    )
    (root / "shared" / "protocols" / "extract-signals.md").write_text(
        "# Protocol: extract-signals\nExtract instructions here.", encoding="utf-8"
    )

    # Fake wiki HTML file
    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir()
    wiki_file = wiki_dir / "concept-a.html"
    wiki_file.write_text(
        "<h1>Concept A</h1><p>This is the concept definition.</p>",
        encoding="utf-8",
    )

    # Fake learner-state.md
    state_file = tmp_path / "learner-state.md"
    state_file.write_text(
        "# Learner State\n\n## Scalar\n0.5\n\n## Mastery\n",
        encoding="utf-8",
    )

    return root, wiki_file, state_file


# ---------------------------------------------------------------------------
# Structure tests
# ---------------------------------------------------------------------------

def test_returns_dict_with_system_and_messages(tmp_path: Path):
    root, wiki, state = _make_fixture(tmp_path)
    result = assemble_prompt("generate-question", [wiki], state, program_root=root)
    assert isinstance(result, dict)
    assert "system" in result
    assert "messages" in result


def test_messages_is_single_user_message(tmp_path: Path):
    root, wiki, state = _make_fixture(tmp_path)
    result = assemble_prompt("generate-question", [wiki], state, program_root=root)
    msgs = result["messages"]
    assert len(msgs) == 1
    assert msgs[0]["role"] == "user"
    assert isinstance(msgs[0]["content"], str)


# ---------------------------------------------------------------------------
# Content tests
# ---------------------------------------------------------------------------

def test_system_contains_agents_md_content(tmp_path: Path):
    root, wiki, state = _make_fixture(tmp_path)
    result = assemble_prompt("generate-question", [wiki], state, program_root=root)
    assert "Tutor Harness" in result["system"]
    assert "System content here." in result["system"]


def test_user_message_contains_protocol_content(tmp_path: Path):
    root, wiki, state = _make_fixture(tmp_path)
    result = assemble_prompt("generate-question", [wiki], state, program_root=root)
    content = result["messages"][0]["content"]
    assert "Protocol: generate-question" in content
    assert "Protocol instructions here." in content


def test_user_message_contains_extract_signals_protocol(tmp_path: Path):
    root, wiki, state = _make_fixture(tmp_path)
    result = assemble_prompt("extract-signals", [wiki], state, program_root=root)
    content = result["messages"][0]["content"]
    assert "Protocol: extract-signals" in content
    assert "Extract instructions here." in content


def test_user_message_contains_grounding_content(tmp_path: Path):
    root, wiki, state = _make_fixture(tmp_path)
    result = assemble_prompt("generate-question", [wiki], state, program_root=root)
    content = result["messages"][0]["content"]
    # markitdown converts HTML headings and paragraphs to markdown text
    assert "Concept A" in content
    assert "concept definition" in content


def test_user_message_contains_learner_state(tmp_path: Path):
    root, wiki, state = _make_fixture(tmp_path)
    result = assemble_prompt("generate-question", [wiki], state, program_root=root)
    content = result["messages"][0]["content"]
    assert "Learner State" in content
    assert "0.5" in content


def test_user_message_has_section_headers(tmp_path: Path):
    root, wiki, state = _make_fixture(tmp_path)
    result = assemble_prompt("generate-question", [wiki], state, program_root=root)
    content = result["messages"][0]["content"]
    assert "## Protocol" in content
    assert "## Grounding Context" in content
    assert "## Learner State" in content


# ---------------------------------------------------------------------------
# Multiple grounding files
# ---------------------------------------------------------------------------

def test_multiple_grounding_paths_all_included(tmp_path: Path):
    root, wiki_a, state = _make_fixture(tmp_path)

    wiki_b = tmp_path / "wiki" / "concept-b.html"
    wiki_b.write_text("<h1>Concept B</h1><p>Neighbor content.</p>", encoding="utf-8")

    result = assemble_prompt("generate-question", [wiki_a, wiki_b], state, program_root=root)
    content = result["messages"][0]["content"]
    assert "Concept A" in content
    assert "Concept B" in content
    assert "Neighbor content" in content


def test_empty_grounding_paths(tmp_path: Path):
    root, _, state = _make_fixture(tmp_path)
    result = assemble_prompt("generate-question", [], state, program_root=root)
    content = result["messages"][0]["content"]
    assert "## Grounding Context" in content


# ---------------------------------------------------------------------------
# Invalid protocol
# ---------------------------------------------------------------------------

def test_invalid_protocol_raises_value_error(tmp_path: Path):
    root, wiki, state = _make_fixture(tmp_path)
    with pytest.raises(ValueError, match="Unknown protocol"):
        assemble_prompt("unknown-protocol", [wiki], state, program_root=root)
