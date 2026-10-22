"""Entry point: `python -m evals run [--split NAME]` and `python -m evals compare A B`."""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from evals.compare import format_comparison
from evals.dataset import SPLITS, load_split
from evals.llm import EvalLLMSettings, LLMClient
from evals.progress import Progress
from evals.report import format_report
from evals.run import RunStopped, gemini_agent_client, gemini_judge_client, run_eval
from evals.store import RESULTS_DIR, StoreError, load_run, save_run

DEFAULT_REPETITIONS = 3


def main(
    argv: Sequence[str],
    *,
    llm: LLMClient | None = None,
    judge_llm: LLMClient | None = None,
    results_dir: Path = RESULTS_DIR,
) -> int:
    """Run a split of Eval cases through the agent, or compare two saved runs.

    A split with no Eval cases needs no model and prints an empty Experiment.

    Args:
        argv: Command-line arguments after the program name: `run [--split NAME]
            [--repetitions N] [--fresh] [--judge]`, `compare A B`, or none (a `run` of `tuning`).
        llm: The model client; built from settings (Gemini) when None. Tests pass a scripted one.
        judge_llm: The judge model's client, used only with `--judge`; built from settings
            (the judge model) when None.
        results_dir: Where runs and the progress file are kept (git-ignored by default).

    Returns:
        The process exit code: 0, or 1 when a run stopped early or a saved run is unreadable.
    """
    parser = argparse.ArgumentParser(prog="python -m evals", description=__doc__)
    commands = parser.add_subparsers(dest="command")
    run = commands.add_parser("run", help="run a split of Eval cases through the agent")
    run.add_argument("--split", default="tuning", choices=SPLITS, help="default: tuning")
    run.add_argument(
        "--repetitions",
        type=int,
        default=DEFAULT_REPETITIONS,
        help=f"runs of each Eval case (default: {DEFAULT_REPETITIONS})",
    )
    run.add_argument(
        "--judge",
        action="store_true",
        help="also score answers with the rubric judge (uncalibrated; spends judge calls)",
    )
    run.add_argument("--fresh", action="store_true", help="ignore saved progress, start over")
    compared = commands.add_parser("compare", help="compare two saved runs (B minus A)")
    compared.add_argument("a", help="saved run A: a path, or a file name under evals/results/")
    compared.add_argument("b", help="saved run B")
    args = parser.parse_args(list(argv))

    if args.command == "compare":
        return _compare(args.a, args.b, results_dir)

    split = getattr(args, "split", "tuning")
    repetitions = getattr(args, "repetitions", DEFAULT_REPETITIONS)
    if repetitions < 1:
        parser.error("--repetitions must be at least 1")
    dataset = load_split(split)
    settings = None
    model = None
    use_judge = getattr(args, "judge", False)
    if dataset.cases and (llm is None or (use_judge and judge_llm is None)):
        settings = EvalLLMSettings()
        if llm is None:
            llm, model = gemini_agent_client(settings), settings.agent_model
        if use_judge and judge_llm is None:
            judge_llm = gemini_judge_client(settings)
    progress = Progress(results_dir / f"progress-{split}.json") if dataset.cases else None
    if progress is not None and getattr(args, "fresh", False):
        progress.clear()
    try:
        experiment = run_eval(
            dataset,
            llm,  # type: ignore[arg-type]
            model=model,
            repetitions=repetitions,
            progress=progress,
            judge=judge_llm if use_judge else None,
        )
    except RunStopped as stopped:
        print(f"Run stopped: {stopped}")
        return 1
    meta = {
        "split": split,
        "repetitions": repetitions,
        "agent_model": model,
        "judge_model": settings.judge_model if settings else None,
    }
    print(format_report(experiment, meta))
    if dataset.cases:
        path = save_run(experiment, meta, root=results_dir)
        if progress is not None:
            progress.clear()
        print(f"\nSaved: {path}")
    return 0


def _compare(a: str, b: str, results_dir: Path) -> int:
    try:
        first, _ = load_run(a, root=results_dir)
        second, _ = load_run(b, root=results_dir)
    except StoreError as error:
        print(f"error: {error}")
        return 1
    print(format_comparison(first, second, Path(a).stem, Path(b).stem))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
