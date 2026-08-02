"""Question-scoped scratchpad scene + selection image sidecars."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from apore.providers.multimodal import MultimodalError, parse_data_uri


def _assets_dir(state_path: Path) -> Path:
    return state_path.parent / state_path.stem


def scene_path(state_path: Path, question_number: int) -> Path:
    return _assets_dir(state_path) / f"scratchpad-q{int(question_number)}.json"


def write_scene(
    state_path: Path,
    *,
    question_number: int,
    schema_version: int = 1,
    engine: str = "apore-konva",
    nodes: list[dict[str, Any]] | None = None,
    camera: dict[str, Any] | None = None,
    last_export_bounds: dict[str, Any] | None = None,
    feedback_regions: list[dict[str, Any]] | None = None,
) -> Path:
    """Persist a versioned Apore scratchpad document; returns its sidecar path."""
    path = scene_path(state_path, question_number)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "question_number": int(question_number),
        "schema_version": int(schema_version),
        "engine": engine,
        "nodes": list(nodes or []),
        "camera": dict(camera or {"x": 0.0, "y": 0.0, "scale": 1.0}),
        "last_export_bounds": (
            dict(last_export_bounds) if last_export_bounds is not None else None
        ),
        "feedback_regions": list(feedback_regions or []),
    }
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)
    return path


def read_scene(state_path: Path, question_number: int) -> dict[str, Any] | None:
    path = scene_path(state_path, question_number)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    if data.get("schema_version") != 1 or data.get("engine") != "apore-konva":
        return None
    return {
        "question_number": int(data.get("question_number") or question_number),
        "schema_version": 1,
        "engine": "apore-konva",
        "nodes": list(data.get("nodes") or [])
        if isinstance(data.get("nodes"), list)
        else [],
        "camera": (
            dict(data.get("camera"))
            if isinstance(data.get("camera"), dict)
            else {"x": 0.0, "y": 0.0, "scale": 1.0}
        ),
        "last_export_bounds": (
            dict(data.get("last_export_bounds"))
            if isinstance(data.get("last_export_bounds"), dict)
            else None
        ),
        "feedback_regions": (
            list(data.get("feedback_regions") or [])
            if isinstance(data.get("feedback_regions"), list)
            else []
        ),
    }


def clear_scene(state_path: Path, question_number: int) -> None:
    path = scene_path(state_path, question_number)
    if path.is_file():
        path.unlink()


def write_selection_image(
    state_path: Path,
    *,
    question_number: int,
    action: str,
    data_uri: str,
) -> Path:
    """Persist a submitted/asked crop as a binary sidecar next to the session."""
    media_type, raw = parse_data_uri(data_uri)
    ext = "png" if media_type == "image/png" else "jpg"
    safe_action = "ask" if action == "ask" else "submit"
    assets = _assets_dir(state_path)
    assets.mkdir(parents=True, exist_ok=True)
    prefix = f"scratchpad-q{int(question_number)}-{safe_action}-"
    existing = sorted(assets.glob(f"{prefix}*.{ext}"))
    next_idx = len(existing) + 1
    path = assets / f"{prefix}{next_idx}.{ext}"
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(raw)
    tmp.replace(path)
    return path


def selection_display_text(
    *,
    learner_message: str,
    relative_name: str,
) -> str:
    """Transcript text that references a sidecar instead of embedding base64."""
    prompt = (learner_message or "").strip()
    ref = f"[Scratchpad selection: {relative_name}]"
    if not prompt or prompt == "[Scratchpad selection]":
        return ref
    if "[Scratchpad selection" in prompt:
        return prompt
    return f"{prompt}\n{ref}"


def selection_ref_or_raise(path: Path, state_path: Path) -> str:
    """Return a path relative to the session assets dir for markdown references."""
    try:
        return path.relative_to(_assets_dir(state_path)).as_posix()
    except ValueError as exc:
        raise MultimodalError("Selection image path escaped session assets.") from exc
