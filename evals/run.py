"""Running Eval cases through the agent and scoring them, as one Experiment.

assayer's `Runner` calls the target with `Case.input` only, so `prepare` turns each Eval
case's question into `{"case_id", "question"}`: the id picks the Cassette named after it.
`run_case` is the per-case unit of work (one Cassette, one session, one Trajectory), kept
apart so a later wrapper (resuming, key rotation) can go around it.
"""

import asyncio
import dataclasses
import time
from collections.abc import Collection, Mapping
from pathlib import Path
from typing import Any

from assayer.models import Dataset, Experiment, Trajectory
from assayer.registries import Registry
from assayer.runner import Runner

from evals.agent import DEFAULT_MAX_STEPS, IN_SCOPE_TOOLS, run_agent
from evals.cassette import CASSETTES_DIR, Cassette, cassette_path, replay_session
from evals.citation_existence import CITATION_EXISTENCE
from evals.citation_existence import register_metrics as register_citation_metrics
from evals.judge import DEFAULT_REPETITIONS, JUDGE, format_judge_line, register_judge
from evals.llm import (
    AllKeysExhausted,
    EvalLLMSettings,
    GeminiClient,
    LLMClient,
    RateLimiter,
    RequestBudget,
    RequestCapReached,
    key_source_from,
)
from evals.progress import Progress, unit_key
from evals.retrieval import CONTEXT_PRECISION, CONTEXT_RECALL
from evals.retrieval import register_metrics as register_retrieval_metrics
from evals.store import trajectory_from_dict, trajectory_to_dict
from evals.tool_use import TOOL_USE, register_metrics

# Splits whose cases are validated: only these are scored for retrieval.
VALIDATED_SPLITS = frozenset({"tuning", "validation"})


def prepare(dataset: Dataset) -> Dataset:
    """Return the Dataset with each question wrapped as `{"case_id", "question"}`."""
    cases = [
        dataclasses.replace(case, input={"case_id": case.id, "question": case.input})
        for case in dataset.cases
    ]
    return Dataset(name=dataset.name, cases=cases)


async def run_case(
    case_id: str,
    question: str,
    llm: LLMClient,
    *,
    cassettes_root: Path = CASSETTES_DIR,
    tool_names: Collection[str] | None = IN_SCOPE_TOOLS,
    max_steps: int = DEFAULT_MAX_STEPS,
    model: str | None = None,
) -> Trajectory:
    """Put one Eval case to the agent over the Cassette named after its id.

    Raises:
        FileNotFoundError: When the case has no Cassette.
    """
    path = cassette_path(case_id, root=cassettes_root)
    if not path.exists():
        raise FileNotFoundError(f"no Cassette for Eval case {case_id!r}: {path}")
    async with replay_session(Cassette.load(path)) as session:
        return await run_agent(
            question, session, llm, max_steps=max_steps, tool_names=tool_names, model=model
        )


def run_eval(
    dataset: Dataset,
    llm: LLMClient,
    *,
    cassettes_root: Path = CASSETTES_DIR,
    tool_names: Collection[str] | None = IN_SCOPE_TOOLS,
    max_steps: int = DEFAULT_MAX_STEPS,
    model: str | None = None,
    repetitions: int = 1,
    progress: Progress | None = None,
    judge: LLMClient | None = None,
    judge_repetitions: int = DEFAULT_REPETITIONS,
) -> Experiment:
    """Run every Eval case of the Dataset `repetitions` times and score its tool use.

    Args:
        dataset: Eval cases as loaded by `evals.dataset.load_split`.
        llm: The model client (a scripted one in tests).
        cassettes_root: Where the Cassettes named after the case ids live.
        tool_names: The server tools offered to the agent.
        max_steps: The most model calls per case.
        model: The model name kept on the model Steps.
        judge: The judge model's client; when given (opt-in) the rubric judge also scores
            each answer, `judge_repetitions` times. None spends no judge call.
        judge_repetitions: Judgments per answer.
        repetitions: How many times each Eval case runs, each kept as its own Trajectory.
        progress: When given, each `case#repetition` unit is wrapped in it: a finished unit is
            reused, a new one is saved as soon as it ends.

    Returns:
        The Experiment: a Trajectory per repetition and a `tool_use` Score for each.

    Raises:
        RunStopped: When the keys are exhausted or the request cap is reached; the finished
            units are in `progress` (when given), so the same call resumes the run.
    """
    registry = Registry()
    register_metrics(registry)
    register_citation_metrics(registry)
    register_retrieval_metrics(registry)
    done: dict[str, int] = {}

    def work(case_input: dict[str, Any]) -> Trajectory:
        return asyncio.run(
            run_case(
                case_input["case_id"],
                case_input["question"],
                llm,
                cassettes_root=cassettes_root,
                tool_names=tool_names,
                max_steps=max_steps,
                model=model,
            )
        )

    def target(case_input: dict[str, Any]) -> Trajectory:
        case_id = case_input["case_id"]
        repetition = done.get(case_id, 0)
        done[case_id] = repetition + 1
        try:
            if progress is None:
                return work(case_input)
            stored = progress.run(
                unit_key(case_id, repetition), lambda: trajectory_to_dict(work(case_input))
            )
            return trajectory_from_dict(stored)
        except (AllKeysExhausted, RequestCapReached) as stop:
            raise _Stop(unit_key(case_id, repetition), stop) from stop

    metrics = [registry.get(TOOL_USE), registry.get(CITATION_EXISTENCE)]
    if dataset.name in VALIDATED_SPLITS:
        metrics += [registry.get(CONTEXT_PRECISION), registry.get(CONTEXT_RECALL)]
    if judge is not None:
        register_judge(registry, judge, judge_repetitions)
        metrics.append(registry.get(JUDGE))
    runner = Runner(target=target, metrics=metrics, repetitions=repetitions)
    try:
        return runner.run(prepare(dataset))
    except _Stop as stop:
        finished = len(progress) if progress is not None else 0
        raise RunStopped(
            f"stopped at {stop.unit} ({type(stop.reason).__name__}); {finished} unit(s) saved. "
            "Run the same command again to resume (after midnight Pacific time if the daily "
            "quota ran out)."
        ) from stop.reason


class RunStopped(Exception):  # noqa: N818
    """The run stopped on exhausted keys or the request cap; finished units stay in Progress."""


class _Stop(BaseException):
    """Carries a stop out of assayer's Runner, which turns any `Exception` into an error Step."""

    def __init__(self, unit: str, reason: Exception) -> None:
        super().__init__(unit)
        self.unit = unit
        self.reason = reason


def gemini_agent_client(settings: EvalLLMSettings) -> GeminiClient:
    """Build the agent's Gemini client from settings: real clock, keys per settings, run-capped.

    Raises:
        ValueError: When no `GEMINI_API_KEY` is set.
    """
    return _gemini_client(settings, settings.agent_model)


def gemini_judge_client(settings: EvalLLMSettings) -> GeminiClient:
    """Build the judge's Gemini client (the judge model) the same way as the agent's.

    Raises:
        ValueError: When no `GEMINI_API_KEY` is set.
    """
    return _gemini_client(settings, settings.judge_model)


def gemini_calibration_client(settings: EvalLLMSettings) -> GeminiClient:
    """Build the Gemini client of the calibration model (stronger than the judge's).

    Raises:
        ValueError: When no `GEMINI_API_KEY` is set.
    """
    return _gemini_client(settings, settings.calibration_model)


def _gemini_client(settings: EvalLLMSettings, model: str) -> GeminiClient:
    limiter = RateLimiter(
        settings.requests_per_minute, settings.tokens_per_minute, time.monotonic, time.sleep
    )
    return GeminiClient(
        model,
        key_source_from(settings),
        limiter,
        RequestBudget(settings.request_cap),
        settings,
        time.sleep,
    )


def format_experiment(experiment: Experiment, calibration: Mapping[str, Any] | None = None) -> str:
    """Render the Experiment: a summary, then one line per Eval case, then the caveats."""
    lines = [
        f"Experiment {experiment.name!r}",
        f"  cases: {len(experiment.cases)}",
        f"  trajectories: {len(experiment.trajectories)}",
        f"  scores: {len(experiment.scores)}",
        f"  failures: {len(experiment.failures)}",
    ]
    for trajectory in experiment.trajectories:
        lines.append("  " + _case_line(experiment, trajectory, calibration))
    citation = [s.value for s in experiment.scores if s.name == CITATION_EXISTENCE]
    if citation:
        lines.append(f"  mean citation_existence: {sum(citation) / len(citation):.2f}")
    lines += _retrieval_summary(experiment)
    tool_use = [s.value for s in experiment.scores if s.name == TOOL_USE]
    if tool_use:
        lines.append(f"  mean tool_use: {sum(tool_use) / len(tool_use):.2f}")
        lines.append(
            "  note: the agent is a small model; its scores do not transfer to a stronger one."
        )
        if experiment.name == "seed":
            lines.append(
                "  note: seed cases and Cassettes are hand-made and count toward no result."
            )
    return "\n".join(lines)


def _case_line(
    experiment: Experiment, trajectory: Trajectory, calibration: Mapping[str, Any] | None = None
) -> str:
    score = next(
        (s for s in experiment.scores if s.name == TOOL_USE and s.target_id == trajectory.case_id),
        None,
    )
    tools = [s for s in trajectory.steps if s.kind == "tool"]
    errors = sum(bool(s.error) for s in tools)
    errors += sum(s.kind == "model" and bool(s.error) for s in trajectory.steps)
    usage = trajectory.total_usage()
    misses = (trajectory.final_state or {}).get("cassette_misses", 0)
    shown = f"tool_use {score.value:.2f}" if score else "tool_use n/a"
    judged = next(
        (s for s in experiment.scores if s.name == JUDGE and s.target_id == trajectory.case_id),
        None,
    )
    line = (
        f"{trajectory.case_id}: {shown} | calls {len(tools)} | errors {errors} | "
        f"tokens {usage.input_tokens + usage.output_tokens} | cassette misses {misses}"
    )
    if score and score.comment:
        line += f" | {score.comment}"
    line += _citation_note(experiment, trajectory)
    line += _retrieval_note(experiment, trajectory)
    if judged:
        line += "\n    " + format_judge_line(judged, calibration)
    return line


def _citation_note(experiment: Experiment, trajectory: Trajectory) -> str:
    found = next(
        (
            s
            for s in experiment.scores
            if s.name == CITATION_EXISTENCE and s.target_id == trajectory.case_id
        ),
        None,
    )
    if not found:
        return ""
    return f" | citation_existence {found.value:.2f}" + (
        f" ({found.comment})" if found.comment else ""
    )


def _retrieval_note(experiment: Experiment, trajectory: Trajectory) -> str:
    values = {
        name: next(
            (
                s.value
                for s in experiment.scores
                if s.name == name and s.target_id == trajectory.case_id
            ),
            None,
        )
        for name in (CONTEXT_PRECISION, CONTEXT_RECALL)
    }
    if values[CONTEXT_PRECISION] is None:
        return ""
    return f" | precision {values[CONTEXT_PRECISION]:.2f} recall {values[CONTEXT_RECALL]:.2f}"


def _retrieval_summary(experiment: Experiment, root: Path = CASSETTES_DIR) -> list[str]:
    """The retrieval means of the run and the dates of the Cassettes behind them."""
    scored = {s.target_id for s in experiment.scores if s.name == CONTEXT_PRECISION}
    if not scored:
        return []
    lines = []
    for name in (CONTEXT_PRECISION, CONTEXT_RECALL):
        values = [s.value for s in experiment.scores if s.name == name]
        lines.append(f"  mean {name}: {sum(values) / len(values):.2f} ({len(scored)} case(s))")
    dates = sorted(
        Cassette.load(path).recorded_on
        for case_id in scored
        if (path := cassette_path(case_id, root=root)).exists()
    )
    if dates:
        lines.append(f"  golden set recorded: {dates[0]} to {dates[-1]} (Cassette dates)")
    return lines
