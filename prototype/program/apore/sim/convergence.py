"""Trajectory analysis and artifact output for simulation runs."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from apore.sim.student import StudentProfile


def compute_session_error(trajectory: list[float], target_ability: float) -> float:
    """Mean absolute error between trajectory scalars and target_ability."""
    if not trajectory:
        return 0.0
    return sum(abs(d - target_ability) for d in trajectory) / len(trajectory)


def compute_trend(session_errors: list[float]) -> float:
    """Return the slope of a linear fit over session errors.

    Negative slope = errors trending downward = convergence.
    Uses ordinary least squares on indices 0, 1, ..., n-1.
    """
    n = len(session_errors)
    if n < 2:
        return 0.0

    xs = list(range(n))
    mean_x = sum(xs) / n
    mean_y = sum(session_errors) / n

    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, session_errors))
    denominator = sum((x - mean_x) ** 2 for x in xs)

    if denominator == 0.0:
        return 0.0
    return numerator / denominator


def write_artifacts(
    sessions: list[dict],
    profile: StudentProfile,
    output_dir: Path,
    fixture_commit: str,
    provider: str,
    model: str,
) -> None:
    """Write trajectories.csv, run_summary.json, and run_summary.md."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # --- trajectories.csv ---
    csv_path = output_dir / "trajectories.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["session_id", "question_number", "difficulty", "error_from_target"])
        for session in sessions:
            session_id = session["session_id"]
            for q_num, difficulty in enumerate(session["difficulties"], start=1):
                error = abs(difficulty - profile.ability)
                writer.writerow([session_id, q_num, difficulty, round(error, 6)])

    # --- per-session errors and trend ---
    session_errors = [
        compute_session_error(s["difficulties"], profile.ability) for s in sessions
    ]
    trend_slope = compute_trend(session_errors)

    # final error = mean of last-question errors across sessions
    final_errors = [abs(s["difficulties"][-1] - profile.ability) for s in sessions]
    mean_final_error = sum(final_errors) / len(final_errors) if final_errors else 0.0

    # --- run_summary.json ---
    summary = {
        "profile": {
            "ability": profile.ability,
            "misconceptions": profile.misconceptions,
            "seed": profile.seed,
        },
        "num_sessions": len(sessions),
        "questions_per_session": len(sessions[0]["difficulties"]) if sessions else 0,
        "mean_final_error": round(mean_final_error, 6),
        "trend_slope": round(trend_slope, 6),
        "fixture_commit": fixture_commit,
        "provider": provider,
        "model": model,
    }
    json_path = output_dir / "run_summary.json"
    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # --- run_summary.md ---
    converging = trend_slope < 0
    convergence_label = "YES (trend_slope < 0)" if converging else "NO (trend_slope >= 0)"
    md_lines = [
        "# Simulation Run Summary",
        "",
        "## Profile",
        f"- ability: {profile.ability}",
        f"- misconceptions: {profile.misconceptions}",
        f"- seed: {profile.seed}",
        "",
        "## Results",
        f"- num_sessions: {len(sessions)}",
        f"- questions_per_session: {summary['questions_per_session']}",
        f"- mean_final_error: {summary['mean_final_error']}",
        f"- trend_slope: {summary['trend_slope']}",
        "",
        "## Convergence",
        f"- Converging: {convergence_label}",
        "",
        "## Metadata",
        f"- fixture_commit: {fixture_commit}",
        f"- provider: {provider}",
        f"- model: {model}",
    ]
    md_path = output_dir / "run_summary.md"
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
