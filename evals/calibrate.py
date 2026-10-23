"""Calibrating the rubric judge against the maintainer's hand labels.

Two steps, both run from `python -m evals calibrate`:

* `export_labels` samples about twenty agent answers from a saved run into a labels template
  (question, expected outcome, tool results, answer, empty labels). The judge's verdict is
  never written there, so the maintainer labels blind.
* `score_labels` re-judges the labelled answers with the stronger calibration model, measures
  how often it agrees with the human labels (per axis, joint, Cohen's kappa) and builds the
  record that `evals.judge.load_calibration` reads. Only a record with `measured: true`
  clears the `[UNCALIBRATED]` mark.

Labels file (version 1): `{"version": 1, "run": ..., "items": [{"id", "case_id", "question",
"expected_outcome", "context", "answer", "correctness", "grounding"}]}`. The two label fields
are empty until labelled; a label is one of the rubric's or "unknown". Unlabeled items are
ignored.
"""

import json
from collections import Counter
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from assayer.judges import Judge
from assayer.models import Case, Experiment, Trajectory

from evals.judge import (
    CORRECTNESS,
    GROUNDING,
    RUBRIC_PROMPT,
    UNKNOWN,
    _context,
    make_rubric_judge,
)

LABELS_VERSION = 1
CALIBRATION_VERSION = 1
DEFAULT_SAMPLE = 20
AXES = {"correctness": CORRECTNESS, "grounding": GROUNDING}


class CalibrationError(Exception):
    """The labels file is unreadable or invalid, or nothing in it is labelled."""


def item_id(case_id: str, index: int) -> str:
    """The stable id of a run's `index`-th answer to a case (`case_id#index`, from zero)."""
    return f"{case_id}#{index}"


def _answers(experiment: Experiment) -> dict[str, Trajectory]:
    seen: Counter[str] = Counter()
    answers: dict[str, Trajectory] = {}
    for trajectory in experiment.trajectories:
        case_id = trajectory.case_id or ""
        key = item_id(case_id, seen[case_id])
        seen[case_id] += 1
        if trajectory.final_output:
            answers[key] = trajectory
    return answers


def sample_ids(experiment: Experiment, n: int = DEFAULT_SAMPLE) -> list[str]:
    """Pick up to `n` answer ids, deterministically, spread across cases (round robin)."""
    by_case: dict[str, list[str]] = {}
    for key in _answers(experiment):
        by_case.setdefault(key.rsplit("#", 1)[0], []).append(key)
    queues = [by_case[case] for case in sorted(by_case)]
    picked: list[str] = []
    depth = 0
    while len(picked) < n and any(depth < len(q) for q in queues):
        picked += [q[depth] for q in queues if depth < len(q)][: n - len(picked)]
        depth += 1
    return picked


def export_labels(experiment: Experiment, run: str, n: int = DEFAULT_SAMPLE) -> dict[str, Any]:
    """Build the labels template for `n` sampled answers; it carries no judge verdict."""
    cases = {c.id: c for c in experiment.cases}
    answers = _answers(experiment)
    items = []
    for key in sample_ids(experiment, n):
        trajectory = answers[key]
        case = cases.get(trajectory.case_id or "")
        expected = case.expected_outcome if case else None
        items.append(
            {
                "id": key,
                "case_id": trajectory.case_id,
                "question": str(case.input) if case else "",
                "expected_outcome": str(expected) if expected else "",
                "context": _context(trajectory),
                "answer": str(trajectory.final_output),
                "correctness": "",
                "grounding": "",
            }
        )
    return {
        "version": LABELS_VERSION,
        "run": run,
        "instructions": (
            "Fill correctness with one of correct|incorrect|refusal|unknown and grounding with "
            "one of grounded|misgrounded|ungrounded|unknown. Leave both empty to skip an item."
        ),
        "items": items,
    }


def load_labels(path: Path) -> dict[str, Any]:
    """Read a labels file.

    Raises:
        CalibrationError: When it is missing, not JSON, or has the wrong shape.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise CalibrationError(f"cannot read labels file {path}") from error
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        raise CalibrationError(f"{path} is not a labels file (no 'items' list)")
    return data


def _human(item: dict[str, Any], axis: str) -> str | None:
    value = item.get(axis)
    label = value.strip().casefold() if isinstance(value, str) else ""
    if not label:
        return None
    if label not in (*AXES[axis], UNKNOWN):
        raise CalibrationError(f"item {item.get('id')}: {label!r} is not a {axis} label")
    return label


def kappa(pairs: Sequence[tuple[str, str]]) -> float | None:
    """Cohen's kappa of (human, judge) label pairs; None when undefined."""
    if not pairs:
        return None
    total = len(pairs)
    observed = sum(h == j for h, j in pairs) / total
    humans, judges = Counter(h for h, _ in pairs), Counter(j for _, j in pairs)
    expected = sum(humans[label] * judges[label] for label in humans) / total**2
    if expected >= 1:
        return None
    return (observed - expected) / (1 - expected)


def _stats(pairs: list[tuple[str, str]]) -> dict[str, Any]:
    agreed = sum(h == j for h, j in pairs)
    return {
        "n": len(pairs),
        "agreement": agreed / len(pairs) if pairs else None,
        "kappa": kappa(pairs),
    }


def score_labels(
    experiment: Experiment,
    labels: dict[str, Any],
    judge: Judge,
    *,
    run: str,
    model: str,
    repetitions: int = 1,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Re-judge the labelled answers with `judge`; measure agreement with the human labels.

    Raises:
        CalibrationError: When a label is invalid, an item is not in the run, or none is labelled.
    """
    answers = _answers(experiment)
    cases = {c.id: c for c in experiment.cases}
    metric = make_rubric_judge(judge, repetitions, calibration=None)
    rows: list[dict[str, Any]] = []
    unlabeled = 0
    for item in labels["items"]:
        human = {axis: _human(item, axis) for axis in AXES}
        if all(v is None for v in human.values()):
            unlabeled += 1
            continue
        trajectory = answers.get(item.get("id"))
        if trajectory is None:
            raise CalibrationError(f"item {item.get('id')} is not an answer of run {run!r}")
        case: Case | None = cases.get(trajectory.case_id or "")
        meta = metric.evaluate(trajectory, case).scores[0].metadata
        rows.append({"id": item["id"], "human": human, "judge": {a: meta[a] for a in AXES}})
    if not rows:
        raise CalibrationError("no item is labelled; nothing to measure")
    per_axis = {
        axis: _stats([(r["human"][axis], r["judge"][axis]) for r in rows if r["human"][axis]])
        for axis in AXES
    }
    both = [r for r in rows if all(r["human"].values())]
    joint = {
        "n": len(both),
        "agreement": (
            sum(all(r["human"][a] == r["judge"][a] for a in AXES) for r in both) / len(both)
            if both
            else None
        ),
    }
    return {
        "version": CALIBRATION_VERSION,
        "measured": True,
        "run": run,
        "calibration_model": model,
        "judge_prompt": RUBRIC_PROMPT.ref,
        "scored_at": (now or datetime.now()).isoformat(timespec="seconds"),
        "labeled": len(rows),
        "unlabeled": unlabeled,
        **per_axis,
        "joint": joint,
        "items": rows,
    }


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}"


def format_calibration(record: dict[str, Any]) -> list[str]:
    """Report lines for a calibration record: counts and agreement per axis and joint."""
    lines = [
        f"Judge calibration (model {record.get('calibration_model')}, run {record.get('run')}): "
        f"{record.get('labeled', 0)} labelled, {record.get('unlabeled', 0)} unlabeled"
    ]
    for axis in AXES:
        stats = record.get(axis, {})
        lines.append(
            f"  {axis}: agreement {_pct(stats.get('agreement'))} over {stats.get('n', 0)} "
            f"| kappa {_pct(stats.get('kappa'))}"
        )
    joint = record.get("joint", {})
    lines.append(f"  joint: agreement {_pct(joint.get('agreement'))} over {joint.get('n', 0)}")
    return lines


def write_json(path: Path, data: dict[str, Any]) -> None:
    """Write `data` as indented UTF-8 JSON, creating the folder."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
