"""The honest report of a run: consistency, efficiency and the limits of what it says.

`format_report` joins sections, each a function `(experiment, meta) -> list[str]` (lines).
Another metric adds its section by appending a function to `SECTIONS`; the limits section
stays last.
"""

from collections import Counter
from collections.abc import Callable
from typing import Any

from assayer.models import Experiment

from evals.calibrate import format_calibration
from evals.consistency import consistency, efficiency
from evals.judge import JUDGE, is_measured, load_calibration
from evals.run import format_experiment

Section = Callable[[Experiment, dict[str, Any]], list[str]]


def model_family(name: str) -> str:
    """Return the family prefix of a model name: `gemini-2.5-flash` gives `gemini`."""
    base = name.strip().casefold().rsplit("/", 1)[-1]
    return base.split("-", 1)[0]


def cassette_misses(experiment: Experiment) -> int:
    """Sum the cassette misses the Trajectories recorded."""
    return sum(
        t.final_state.get("cassette_misses", 0)
        for t in experiment.trajectories
        if isinstance(t.final_state, dict)
    )


def consistency_section(experiment: Experiment, meta: dict[str, Any]) -> list[str]:
    """Per Eval case: passing runs and the verdict by its kind (all-pass or at-least-one)."""
    rows = consistency(experiment)
    if not rows:
        return []
    lines = ["Consistency (a run passes when tool_use is 1.00)"]
    for row in rows:
        verdict = "PASS" if row.passed else "FAIL"
        lines.append(
            f"  {row.case_id}: {row.passes}/{row.runs} runs | {row.kind} ({row.rule}) | {verdict}"
        )
    passed = Counter(row.kind for row in rows if row.passed)
    total = Counter(row.kind for row in rows)
    for kind in sorted(total):
        lines.append(f"  {kind}: {passed[kind]}/{total[kind]} cases pass")
    return lines


def efficiency_section(experiment: Experiment, meta: dict[str, Any]) -> list[str]:
    """Per Eval case: mean calls, tokens and tool errors per run, and repeated invalid arguments."""
    rows = efficiency(experiment)
    if not rows:
        return []
    lines = ["Efficiency (mean per run)"]
    flags = []
    for row in rows:
        lines.append(
            f"  {row.case_id}: calls {row.calls:.1f} | tokens {row.tokens:.0f} | "
            f"tool errors {row.errors:.1f}"
        )
        flags += [(row.case_id, r) for r in row.repeated_invalid]
    for case_id, r in flags:
        lines.append(
            f"  FLAG {case_id}: {r.tool} failed {r.count}x with the same arguments {r.arguments}"
            " - the tool description may be unclear"
        )
    return lines


def calibration_lines(experiment: Experiment, record: dict[str, Any] | None) -> list[str]:
    """Agreement of the judge with the human labels, shown beside its scores (only if judged)."""
    scores = [s for s in experiment.scores if s.name == JUDGE]
    if not scores:
        return []
    mean = sum(s.value for s in scores) / len(scores)
    head = [f"Judge scores: mean {mean:.2f} over {len(scores)} answers"]
    if is_measured(record):
        return [*head, *format_calibration(record)]  # type: ignore[arg-type]
    return [
        *head,
        "  UNCALIBRATED: no measured agreement with human labels yet"
        " (python -m evals calibrate export/score).",
    ]


def limits_section(experiment: Experiment, meta: dict[str, Any]) -> list[str]:
    """What this report cannot tell you."""
    lines = [
        "Limits",
        "  - Name redaction is NER-based, best effort: names the model misses stay in Cassettes.",
        "  - The agent is a small model; its scores do not transfer to a stronger one.",
        f"  - Cassette misses in this run: {cassette_misses(experiment)}"
        " (requests with no recording, answered as source_unavailable).",
    ]
    agent, judge = meta.get("agent_model"), meta.get("judge_model")
    if agent and judge:
        if model_family(agent) == model_family(judge):
            lines.append(
                f"  - Agent ({agent}) and judge ({judge}) share the {model_family(agent)!r}"
                " family: the judge may favour the agent's answers."
            )
        else:
            lines.append(f"  - Agent ({agent}) and judge ({judge}) are of different families.")
    elif agent:
        lines.append(f"  - Agent model {agent}; no judge configured.")
    return lines


SECTIONS: list[Section] = [consistency_section, efficiency_section]


def format_report(
    experiment: Experiment,
    meta: dict[str, Any] | None = None,
    *,
    sections: list[Section] | None = None,
    calibration: dict[str, Any] | str | None = "load",
) -> str:
    """Render the Experiment, then every section, the judge calibration, then the limits.

    `calibration` is a calibration record, None, or "load" (default) to read the saved one.
    """
    meta = meta or {}
    record = load_calibration() if calibration == "load" else calibration
    blocks = [format_experiment(experiment, record)]  # type: ignore[arg-type]
    for section in SECTIONS if sections is None else sections:
        lines = section(experiment, meta)
        if lines:
            blocks.append("\n".join(lines))
    judged = calibration_lines(experiment, record)  # type: ignore[arg-type]
    if judged:
        blocks.append("\n".join(judged))
    blocks.append("\n".join(limits_section(experiment, meta)))
    return "\n\n".join(blocks)
