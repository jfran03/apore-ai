"""Deterministic stub provider for testing."""

import json
import re

from apore.providers.base import Provider

_SOURCE_ID_RE = re.compile(r"^### Source:\s*(\S+)\s*$", re.MULTILINE)
_BANK_CONCEPT_RE = re.compile(r"concept ['\"]([a-z0-9_]+)['\"]")


def _bank_response(messages: list[dict]) -> str:
    """Emit six valid questions for the concept named in the closing message."""
    combined = " ".join(str(m.get("content", "")) for m in messages)
    match = _BANK_CONCEPT_RE.search(combined)
    concept_id = match.group(1) if match else "set_theory_intro"
    bands = {"recall": (0.25, 0.3), "apply": (0.5, 0.55), "synthesis": (0.75, 0.8)}
    questions = []
    for qtype, (d1, d2) in bands.items():
        for idx, diff in enumerate((d1, d2), start=1):
            questions.append(
                {
                    "id": f"{concept_id}-{qtype}-{idx:02d}",
                    "concept_id": concept_id,
                    "type": qtype,
                    "intended_difficulty": diff,
                    "text": f"[{qtype}] Question about {concept_id.replace('_', ' ')} ({idx}).",
                }
            )
    return json.dumps({"questions": questions})


def _compile_response(messages: list[dict]) -> str:
    """Build a valid compile-chapter artifact citing the provided source ids."""
    combined = " ".join(str(m.get("content", "")) for m in messages)
    source_ids = _SOURCE_ID_RE.findall(combined)
    citations = source_ids or ["unknown_source"]
    return json.dumps(
        {
            "pages": [
                {
                    "concept_id": "chapter_overview",
                    "label": "Chapter Overview",
                    "body": "A compiled overview synthesized from the chapter sources.",
                    "citations": citations,
                }
            ],
            "edges": [],
        }
    )

_QUESTION_BLOCK = """\
QUESTION
concept: set_theory_intro
type: recall
intended_difficulty: 0.5
---
What is the difference between a set and a multiset? [Source: set_theory_intro — Introduction]\
"""

_TUTOR_HINT = (
    "Think about which operation gives elements shared by both sets. "
    "[Source: sets_definition — Definition]"
)

_TUTOR_CLOSE = (
    "Yes, exactly — the sets are disjoint because they share no elements. "
    "[Source: sets_definition — Definition]\n"
    '{"question_closed": true}'
)

_GRADE_WRONG = (
    "Not quite. A set is not the same as a list — sets are collections of distinct "
    "elements without order or duplicates. [Source: sets_definition — Definition]\n"
    '{"question_closed": true, "correct": "no"}'
)

_GRADE_CORRECT = (
    "Correct. A set collects distinct elements with no implied order. "
    "[Source: sets_definition — Definition]\n"
    '{"question_closed": true, "correct": "yes"}'
)

_GRADE_HELP = (
    "Help request.\n"
    '{"help_request": true}'
)

_SIGNALS = {
    "explicit_rating": "ok",
    "correct": "yes",
    "hint_count": 1,
    "turn_count": 2,
    "hedging_count": 0,
}

def _content_as_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                parts.append(str(part.get("text") or ""))
            elif isinstance(part, dict) and part.get("type") in {"image_url", "image"}:
                parts.append("[Scratchpad selection]")
        return "\n".join(p for p in parts if p)
    return str(content or "")


def _dialogue_user_count(messages: list[dict]) -> int:
    user_msgs = [m for m in messages if m.get("role") == "user"]
    # First user message is the static protocol/grounding block from assemble_prompt.
    return max(0, len(user_msgs) - 1)


def _last_user_message(messages: list[dict]) -> str:
    user_msgs = [m for m in messages if m.get("role") == "user"]
    if len(user_msgs) <= 1:
        return ""
    return _content_as_text(user_msgs[-1].get("content", ""))


def _content_has_image(content: object) -> bool:
    if not isinstance(content, list):
        return False
    return any(
        isinstance(part, dict) and part.get("type") in {"image_url", "image"}
        for part in content
    )


class StubProvider(Provider):
    """Returns canned responses without making any network calls."""

    def invoke(
        self,
        system_prompt: str,
        messages: list[dict],
        model: str,
        config: dict,
    ) -> str:
        protocol = config.get("protocol")
        if protocol == "extract-signals":
            last_assistant = ""
            for msg in reversed(messages):
                if msg.get("role") == "assistant":
                    last_assistant = str(msg.get("content", ""))
                    break
            stripped = last_assistant.lstrip()
            if stripped.startswith("Not quite."):
                return json.dumps(
                    {**_SIGNALS, "correct": "no", "hint_count": 0, "turn_count": 1}
                )
            if stripped.startswith("Correct."):
                return json.dumps(
                    {**_SIGNALS, "correct": "yes", "hint_count": 0, "turn_count": 1}
                )
            hint_count = 1 if any(
                "Think about" in str(m.get("content", ""))
                for m in messages
                if m.get("role") == "assistant"
            ) else 0
            turn_count = max(1, _dialogue_user_count(messages))
            if messages and "extract-signals mode" in str(messages[-1].get("content", "")).lower():
                turn_count = max(1, turn_count - 1)
            return json.dumps(
                {**_SIGNALS, "hint_count": hint_count, "turn_count": turn_count}
            )
        if protocol == "compile-chapter":
            return _compile_response(messages)
        if protocol == "generate-question-bank":
            return _bank_response(messages)
        if protocol == "generate-session-title":
            return "Introduction to Sets — Adaptive Practice"
        if protocol == "generate-question":
            return _QUESTION_BLOCK
        if protocol in ("tutor-turn", "scratchpad-ask"):
            last_content = ""
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    last_content = msg.get("content")
                    break
            if protocol == "scratchpad-ask" and _content_has_image(last_content):
                if _dialogue_user_count(messages) >= 2:
                    return (
                        _TUTOR_CLOSE
                        + '\n{"question_closed": true, "feedback_regions": []}'
                    )
                return (
                    _TUTOR_HINT
                    + '\n{"feedback_regions": [{"x": 0.2, "y": 0.3, "w": 0.4, "h": 0.2, '
                    '"label": "Check this step", "explanation": "Revisit the marked work."}]}'
                )
            if _dialogue_user_count(messages) >= 2:
                return _TUTOR_CLOSE
            return _TUTOR_HINT
        if protocol in ("grade-answer", "scratchpad-grade"):
            last_user = _last_user_message(messages).lower()
            last_content = ""
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    last_content = msg.get("content")
                    break
            if any(
                phrase in last_user
                for phrase in (
                    "i don't know",
                    "i dont know",
                    "no idea",
                    "walk me through",
                    "explain this",
                    "clarification please",
                )
            ):
                return _GRADE_HELP
            if "list" in last_user or "wrong" in last_user:
                if protocol == "scratchpad-grade" and _content_has_image(last_content):
                    return (
                        "Not quite. A set is not the same as a list — sets are collections "
                        "of distinct elements without order or duplicates. "
                        "[Source: sets_definition — Definition]\n"
                        '{"question_closed": true, "correct": "no", '
                        '"feedback_regions": [{"x": 0.15, "y": 0.25, "w": 0.5, "h": 0.3, '
                        '"label": "Incorrect region", '
                        '"explanation": "This part of the work is incorrect."}]}'
                    )
                return _GRADE_WRONG
            if protocol == "scratchpad-grade" and _content_has_image(last_content):
                return (
                    "Correct. A set collects distinct elements with no implied order. "
                    "[Source: sets_definition — Definition]\n"
                    '{"question_closed": true, "correct": "yes", "feedback_regions": []}'
                )
            return _GRADE_CORRECT

        combined = system_prompt + " ".join(
            _content_as_text(m.get("content", "")) for m in messages
        )
        if "extract-signals" in combined:
            return json.dumps(_SIGNALS)
        return _QUESTION_BLOCK
