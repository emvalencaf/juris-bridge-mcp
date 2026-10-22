"""Loading Eval cases from the split folders under `evals/cases/`."""

import json
from pathlib import Path

from assayer.models import Dataset
from assayer.runner import load_cases

CASES_ROOT = Path(__file__).parent / "cases"
SPLITS = ("tuning", "validation", "drafts")


def load_split(split: str, root: Path = CASES_ROOT) -> Dataset:
    """Load every `*.json` file of one split folder into a single Dataset.

    Args:
        split: A folder name under `root`: `tuning`, `validation` or `drafts`.
        root: The folder holding the splits.

    Returns:
        A Dataset named after the split; empty when the folder is missing or has no files.
    """
    entries: list[dict] = []
    for path in sorted((root / split).glob("*.json")):
        entries.extend(json.loads(path.read_text(encoding="utf-8")))
    return Dataset(name=split, cases=load_cases(entries).cases)
