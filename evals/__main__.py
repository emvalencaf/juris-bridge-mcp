"""Entry point: `uv run --group evals python -m evals run [--split NAME]`."""

import argparse
import sys
from collections.abc import Sequence

from evals.dataset import SPLITS, load_split
from evals.llm import EvalLLMSettings, LLMClient
from evals.run import format_experiment, gemini_agent_client, run_eval


def main(argv: Sequence[str], *, llm: LLMClient | None = None) -> int:
    """Run the Eval cases of a split through the agent and print the Experiment.

    A split with no Eval cases needs no model and prints an empty Experiment.

    Args:
        argv: Command-line arguments after the program name: `run [--split NAME]`, or none.
        llm: The model client; built from settings (Gemini) when None. Tests pass a scripted one.

    Returns:
        The process exit code.
    """
    parser = argparse.ArgumentParser(prog="python -m evals", description=__doc__)
    commands = parser.add_subparsers(dest="command")
    run = commands.add_parser("run", help="run a split of Eval cases through the agent")
    run.add_argument("--split", default="tuning", choices=SPLITS, help="default: tuning")
    args = parser.parse_args(list(argv))

    dataset = load_split(getattr(args, "split", "tuning"))
    model = None
    if dataset.cases and llm is None:
        settings = EvalLLMSettings()
        llm, model = gemini_agent_client(settings), settings.agent_model
    experiment = run_eval(dataset, llm, model=model)  # type: ignore[arg-type]
    print(format_experiment(experiment))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
