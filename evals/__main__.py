"""Entry point: `uv run --group evals python -m evals run [--split NAME]`."""

import argparse
import sys
from collections.abc import Sequence

from evals.dataset import SPLITS, load_split
from evals.llm import EvalLLMSettings, LLMClient
from evals.run import format_experiment, gemini_agent_client, gemini_judge_client, run_eval


def main(
    argv: Sequence[str], *, llm: LLMClient | None = None, judge_llm: LLMClient | None = None
) -> int:
    """Run the Eval cases of a split through the agent and print the Experiment.

    A split with no Eval cases needs no model and prints an empty Experiment.

    Args:
        argv: Arguments after the program name: `run [--split NAME] [--judge]`, or none.
        llm: The model client; built from settings (Gemini) when None. Tests pass a scripted one.
        judge_llm: The judge model's client, used only with `--judge`; built from settings
            (the judge model) when None.

    Returns:
        The process exit code.
    """
    parser = argparse.ArgumentParser(prog="python -m evals", description=__doc__)
    commands = parser.add_subparsers(dest="command")
    run = commands.add_parser("run", help="run a split of Eval cases through the agent")
    run.add_argument("--split", default="tuning", choices=SPLITS, help="default: tuning")
    run.add_argument(
        "--judge",
        action="store_true",
        help="also score answers with the rubric judge (uncalibrated; spends judge calls)",
    )
    args = parser.parse_args(list(argv))

    dataset = load_split(getattr(args, "split", "tuning"))
    model = None
    use_judge = getattr(args, "judge", False)
    if dataset.cases and (llm is None or (use_judge and judge_llm is None)):
        settings = EvalLLMSettings()
        if llm is None:
            llm, model = gemini_agent_client(settings), settings.agent_model
        if use_judge and judge_llm is None:
            judge_llm = gemini_judge_client(settings)
    experiment = run_eval(
        dataset,
        llm,  # type: ignore[arg-type]
        model=model,
        judge=judge_llm if use_judge else None,
    )
    print(format_experiment(experiment))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
