"""Consistency and efficiency of an Experiment run with repetitions.

Each Eval case runs several times, each run kept as its own Trajectory. A run *passes* when its
`tool_use` Score reaches `threshold` (1.0: every requirement met). The case then counts by its
kind, declared in the Eval case JSON as `"expected_state": {"kind": "lookup" | "search"}`
(assayer's loader accepts `expected_state` and has no tags field):

* `lookup` (a Publication or Precedent by its CNJ number or id): **all-pass**, every run passes;
* `search` (an open query): **at-least-one**, one passing run is enough.

A case that declares no kind is a `lookup`: the strict rule is the default, so a missing
declaration can never hide an inconsistent agent.

Efficiency per case is the mean over its runs of the tool calls, the tokens and the tool errors.
The same tool called twice with the same arguments, both failing, is a *repeated invalid
argument*: the model read the tool description, failed, and tried the same thing, which points
at a description that does not tell it how to call the tool. Tool errors whose text names
`source_unavailable` are a Source failing, not arguments, and are not counted as invalid.
"""

import json
from collections import Counter
from dataclasses import dataclass, field
from statistics import fmean
from typing import Any

from assayer.models import Case, Experiment, Trajectory

from evals.tool_use import TOOL_USE

KINDS = ("lookup", "search")
DEFAULT_KIND = "lookup"
RULES = {"lookup": "all-pass", "search": "at-least-one"}


def case_kind(case: Case) -> str:
    """Return the kind an Eval case declares in `expected_state["kind"]`, `lookup` by default.

    Raises:
        ValueError: When the declared kind is not `lookup` or `search`.
    """
    state = case.expected_state
    kind = state.get("kind") if isinstance(state, dict) else None
    if kind is None:
        return DEFAULT_KIND
    if kind not in KINDS:
        raise ValueError(f"Eval case {case.id!r}: kind must be one of {KINDS}, got {kind!r}")
    return kind


@dataclass(frozen=True)
class CaseConsistency:
    """How often the runs of one Eval case passed, and whether the case passes by its rule."""

    case_id: str
    kind: str
    runs: int
    passes: int

    @property
    def rule(self) -> str:
        """`all-pass` or `at-least-one`."""
        return RULES[self.kind]

    @property
    def passed(self) -> bool:
        """Whether the case passes: all runs for a lookup, at least one for a search."""
        if self.runs == 0:
            return False
        return self.passes == self.runs if self.kind == "lookup" else self.passes >= 1


def consistency(
    experiment: Experiment, *, metric: str = TOOL_USE, threshold: float = 1.0
) -> list[CaseConsistency]:
    """Count the passing runs of each Eval case that has a Score for `metric`.

    Args:
        experiment: An Experiment run with repetitions.
        metric: The trajectory-level metric that decides whether a run passes.
        threshold: The lowest Score that counts as a pass.

    Returns:
        One entry per Eval case with at least one Score, in the Experiment's case order.
    """
    scored: dict[str, list[float]] = {}
    for score in experiment.scores:
        if score.name == metric and score.target == "trajectory":
            scored.setdefault(score.target_id, []).append(score.value)
    result = []
    for case in experiment.cases:
        values = scored.get(case.id)
        if values:
            passes = sum(v >= threshold for v in values)
            result.append(CaseConsistency(case.id, case_kind(case), len(values), passes))
    return result


@dataclass(frozen=True)
class RepeatedInvalid:
    """A tool called with the same failing arguments more than once within an Eval case."""

    tool: str
    arguments: str
    count: int


@dataclass(frozen=True)
class CaseEfficiency:
    """Calls, tokens and tool errors of one Eval case: the mean per run and the repeats."""

    case_id: str
    runs: int
    calls: float
    tokens: float
    errors: float
    repeated_invalid: list[RepeatedInvalid] = field(default_factory=list)


def repeated_invalid(trajectories: list[Trajectory]) -> list[RepeatedInvalid]:
    """Find failing calls repeated with the same tool and arguments, across the given runs."""
    counts: Counter[tuple[str, str]] = Counter()
    for trajectory in trajectories:
        for step in trajectory.steps:
            if step.kind == "tool" and step.error and "source_unavailable" not in step.error:
                arguments = json.dumps(step.input, sort_keys=True, ensure_ascii=False, default=str)
                counts[(step.name or "?", arguments)] += 1
    return [RepeatedInvalid(t, a, n) for (t, a), n in sorted(counts.items()) if n > 1]


def _errors(trajectory: Trajectory) -> int:
    return sum(bool(s.error) for s in trajectory.steps if s.kind in {"tool", "model"})


def efficiency(experiment: Experiment) -> list[CaseEfficiency]:
    """Summarise calls, tokens and tool errors per Eval case, mean over its runs."""
    by_case: dict[Any, list[Trajectory]] = {}
    for trajectory in experiment.trajectories:
        by_case.setdefault(trajectory.case_id, []).append(trajectory)
    rows = []
    for case_id, runs in by_case.items():
        usages = [t.total_usage() for t in runs]
        rows.append(
            CaseEfficiency(
                case_id=case_id,
                runs=len(runs),
                calls=fmean(sum(s.kind == "tool" for s in t.steps) for t in runs),
                tokens=fmean(u.input_tokens + u.output_tokens for u in usages),
                errors=fmean(_errors(t) for t in runs),
                repeated_invalid=repeated_invalid(runs),
            )
        )
    return rows
