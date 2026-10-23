"""Saving an Experiment to a local JSON file and loading it back.

assayer keeps an Experiment in memory only, so this module writes it, with a few facts about
the run (`meta`: split, repetitions, models), under `evals/results/` (kept out of version
control) in a timestamped file, and reads it again for `python -m evals compare`.
"""

import dataclasses
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from assayer.models import (
    Case,
    Experiment,
    PricingConfig,
    Score,
    Step,
    TokenUsage,
    Trajectory,
)
from assayer.models.evaluation_failure import EvaluationFailure

RESULTS_DIR = Path(__file__).parent / "results"
FORMAT_VERSION = 1


class StoreError(Exception):
    """A saved run cannot be found or read."""


def trajectory_to_dict(trajectory: Trajectory) -> dict[str, Any]:
    """Return a JSON-serializable dict of a Trajectory."""
    return dataclasses.asdict(trajectory)


def trajectory_from_dict(data: dict[str, Any]) -> Trajectory:
    """Rebuild a Trajectory from `trajectory_to_dict`."""
    steps = [
        Step(**{**raw, "usage": TokenUsage(**raw["usage"]) if raw.get("usage") else None})
        for raw in data.get("steps", [])
    ]
    return Trajectory(**{**data, "steps": steps})


def experiment_to_dict(experiment: Experiment) -> dict[str, Any]:
    """Return a JSON-serializable dict of an Experiment."""
    return dataclasses.asdict(experiment)


def experiment_from_dict(data: dict[str, Any]) -> Experiment:
    """Rebuild an Experiment from `experiment_to_dict`."""
    judge_usage = data.get("judge_usage")
    pricing = data.get("pricing")
    return Experiment(
        name=data["name"],
        trajectories=[trajectory_from_dict(t) for t in data.get("trajectories", [])],
        scores=[Score(**s) for s in data.get("scores", [])],
        failures=[EvaluationFailure(**f) for f in data.get("failures", [])],
        judge_usage=TokenUsage(**judge_usage) if judge_usage else None,
        judge_calls=data.get("judge_calls", 0),
        pricing=PricingConfig(**pricing) if pricing else None,
        cases=[Case(**c) for c in data.get("cases", [])],
    )


def save_run(
    experiment: Experiment,
    meta: dict[str, Any],
    *,
    root: Path = RESULTS_DIR,
    now: datetime | None = None,
) -> Path:
    """Write the Experiment and its meta to `<root>/<name>-<YYYYmmdd-HHMMSS>.json`.

    Args:
        experiment: The Experiment to keep.
        meta: Facts about the run (JSON-serializable): split, repetitions, models.
        root: The results folder; created if missing.
        now: The moment for the file name (the clock when None).

    Returns:
        The path written.
    """
    moment = now or datetime.now()
    root.mkdir(parents=True, exist_ok=True)
    stem = f"{experiment.name}-{moment:%Y%m%d-%H%M%S}"
    path = root / f"{stem}.json"
    extra = 1
    while path.exists():  # two runs in the same second never overwrite each other
        extra += 1
        path = root / f"{stem}-{extra}.json"
    payload = {
        "version": FORMAT_VERSION,
        "meta": {**meta, "saved_at": moment.isoformat(timespec="seconds")},
        "experiment": experiment_to_dict(experiment),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_run(reference: str | Path, *, root: Path = RESULTS_DIR) -> tuple[Experiment, dict]:
    """Read a saved run by path, or by file name (with or without `.json`) under `root`.

    Raises:
        StoreError: When the file is missing or is not a saved run.
    """
    path = Path(reference)
    if not path.exists():
        path = root / (path.name if path.suffix == ".json" else path.name + ".json")
    if not path.exists():
        raise StoreError(f"no saved run {str(reference)!r} (looked in {root})")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload["version"] != FORMAT_VERSION:
            raise ValueError("unexpected format")
        return experiment_from_dict(payload["experiment"]), payload.get("meta", {})
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise StoreError(f"cannot read saved run {path.name}") from error
