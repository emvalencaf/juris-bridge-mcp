"""The retrieval Scores: did the tools return the Publications and Precedents the case expects?

assayer's `context_precision_id` and `context_recall_id` read `retrieval` Steps, which the
agent loop does not write: it records `tool` Steps whose output is the text the model saw. This
module reads those tool results as one ranking, in call order, and hands it to assayer's own
metrics, so the Trajectory stored in a run is left as it is.

An item is a Publication, identified by its CNJ number, or a Precedent, identified by the
server's id (`stf-sv-11`). A Case's `reference_context_ids` hold those. A Publication that
comes back twice (two Publications of one Case, or two calls) counts once, at its first rank.
A failed tool call returns nothing.

Score semantics, from assayer: `context_precision` is the average precision of the ranking
(relevant items ranked first score higher), `context_recall` the share of the reference ids
that were retrieved. A Trajectory that retrieved nothing scores 0 on both. A Case that expects
nothing (a negative, or a `list_coverage` question) is not applicable (None: no Score and no
failure), as `tool_use` does for a Case that expects no tool call.

Only validated Eval cases count toward a result: `run_eval` registers these Metrics for the
`tuning` and `validation` splits, never for `drafts` or `seed`.
"""

import json
from collections.abc import Mapping
from typing import Any

from assayer.metrics import Metric, make_context_precision, make_context_recall
from assayer.models import Case, Step, Trajectory

CONTEXT_PRECISION = "context_precision"
CONTEXT_RECALL = "context_recall"

# The tools whose results are what the agent retrieved.
RETRIEVAL_TOOLS = frozenset({"search_publications", "get_publication", "search_precedents",
                             "get_precedent"})  # fmt: skip

_precision = make_context_precision("id", name=CONTEXT_PRECISION)
_recall = make_context_recall("id", name=CONTEXT_RECALL)


def _items(text: str) -> list[Mapping[str, Any]]:
    """The items of one tool result: its `items`, or the result itself when it is one item."""
    try:
        data = json.loads(text)
    except ValueError:
        return []
    if not isinstance(data, Mapping):
        return []
    if isinstance(data.get("items"), list):
        return [item for item in data["items"] if isinstance(item, Mapping)]
    return [data] if "id" in data else []


def retrieved_ids(trajectory: Trajectory) -> list[str]:
    """The ids of what the tools returned, in rank order, each once.

    Args:
        trajectory: The Trajectory whose tool Steps are read.

    Returns:
        The CNJ number of each Publication and the id of each Precedent; failed calls and
        tools outside `RETRIEVAL_TOOLS` give none.
    """
    ids: list[str] = []
    for step in trajectory.steps:
        if step.kind != "tool" or step.name not in RETRIEVAL_TOOLS or step.error:
            continue
        for item in _items(step.output or ""):
            ident = item.get("cnj_number") or item.get("id")
            if isinstance(ident, str) and ident not in ids:
                ids.append(ident)
    return ids


def _as_retrieval(trajectory: Trajectory) -> Trajectory:
    step = Step(kind="retrieval", output=[{"id": ident} for ident in retrieved_ids(trajectory)])
    return Trajectory(steps=[step], final_output=trajectory.final_output)


def _scorer(metric: Metric):
    def score(trajectory: Trajectory, case: Case) -> float | None:
        if not case.reference_context_ids:
            return None
        return metric.fn(_as_retrieval(trajectory), case)

    return score


def register_metrics(registry: Any) -> None:
    """Register the context precision and recall metrics into a Registry.

    Args:
        registry: The assayer Registry to fill.
    """
    for metric in (_precision, _recall):
        registry.register(
            Metric(
                name=metric.name,
                level="trajectory",
                requires=("reference_context_ids",),
                fn=_scorer(metric),
            )
        )
