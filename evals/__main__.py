"""Entry point: `uv run --group evals python -m evals`."""

import sys

from assayer.runner import Runner

from evals.dataset import load_split


def _no_agent_yet(question: str) -> str:
    """Placeholder target; the agent loop replaces it. Never called on an empty Dataset."""
    raise NotImplementedError


def main(argv: list[str]) -> int:
    """Run the wiring check: load the tuning split and print its Experiment.

    Args:
        argv: Command-line arguments after the program name (none yet).

    Returns:
        The process exit code.
    """
    dataset = load_split("tuning")
    experiment = Runner(target=_no_agent_yet).run(dataset)
    print(f"Experiment {experiment.name!r}")
    print(f"  cases: {len(dataset.cases)}")
    print(f"  trajectories: {len(experiment.trajectories)}")
    print(f"  scores: {len(experiment.scores)}")
    print(f"  failures: {len(experiment.failures)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
