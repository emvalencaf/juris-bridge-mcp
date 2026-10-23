"""Comparing two saved runs: metrics, tokens and calls, the second minus the first."""

from statistics import fmean

from assayer.models import Experiment
from assayer.runner.compare import compare

from evals.consistency import consistency, efficiency


def _delta(a: float | None, b: float | None) -> float | None:
    return None if a is None or b is None else b - a


def _fmt(value: float | None, digits: int = 2) -> str:
    return "n/a" if value is None else f"{value:+.{digits}f}"


def _mean_calls(experiment: Experiment, shared: set) -> float | None:
    rows = [r for r in efficiency(experiment) if r.case_id in shared]
    return fmean(r.calls for r in rows) if rows else None


def _pass_rate(experiment: Experiment) -> float | None:
    rows = consistency(experiment)
    return fmean(r.passed for r in rows) if rows else None


def format_comparison(a: Experiment, b: Experiment, label_a: str = "A", label_b: str = "B") -> str:
    """Render how run B differs from run A (B minus A), with assayer's `compare`.

    Per metric the delta of the mean Score; the tokens and the tool calls per Eval case; the
    share of Eval cases that pass by their kind's rule. Eval cases only one run has are listed
    and left out of the token and call deltas.
    """
    comparison = compare(a, b)
    shared = {t.case_id for t in a.trajectories} & {t.case_id for t in b.trajectories}
    lines = [f"Comparison: {label_b} minus {label_a}", "  metrics (mean Score)"]
    for (name, field_), delta in comparison.metric_deltas.items():
        lines.append(f"    {name}{f'[{field_}]' if field_ else ''}: {_fmt(delta)}")
    if not comparison.metric_deltas:
        lines.append("    none")
    tokens = None
    if comparison.input_tokens_delta is not None and comparison.output_tokens_delta is not None:
        tokens = comparison.input_tokens_delta + comparison.output_tokens_delta
    calls = _delta(_mean_calls(a, shared), _mean_calls(b, shared))
    lines += [
        f"  tokens per Eval case: {_fmt(tokens, 0)}"
        f" (input {_fmt(comparison.input_tokens_delta, 0)},"
        f" output {_fmt(comparison.output_tokens_delta, 0)})",
        f"  tool calls per Eval case: {_fmt(calls)}",
        f"  cases passing by their rule: {_fmt(_delta(_pass_rate(a), _pass_rate(b)))}",
    ]
    if comparison.only_in_a:
        lines.append(f"  only in {label_a}: {', '.join(map(str, comparison.only_in_a))}")
    if comparison.only_in_b:
        lines.append(f"  only in {label_b}: {', '.join(map(str, comparison.only_in_b))}")
    return "\n".join(lines)
