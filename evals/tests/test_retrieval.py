"""The retrieval Scores: precision and recall of what the tools returned against the golden ids."""

import json

from assayer.models import Case, Dataset, Step, Trajectory
from assayer.registries import Registry

from evals.dataset import load_split
from evals.llm import ChatResult, ScriptedLLMClient, ToolCall, Usage
from evals.retrieval import (
    CONTEXT_PRECISION,
    CONTEXT_RECALL,
    register_metrics,
    retrieved_ids,
)
from evals.run import format_experiment, run_eval

PUBLICATIONS = {
    "items": [{"id": "opaque-1", "cnj_number": "A"}, {"id": "opaque-2", "cnj_number": "B"}]
}
PRECEDENTS = {"items": [{"id": "stf-sv-11"}, {"id": "stf-sv-25"}]}


def tool(name: str, payload, error: str | None = None) -> Step:
    return Step(kind="tool", name=name, output=json.dumps(payload), error=error)


def score(steps: list[Step], references: list[str] | None) -> dict[str, float | None]:
    registry = Registry()
    register_metrics(registry)
    trajectory = Trajectory(steps=steps)
    case = Case(input="q", reference_context_ids=references)
    return {
        name: registry.get(name).fn(trajectory, case)
        for name in (CONTEXT_PRECISION, CONTEXT_RECALL)
    }


def test_a_perfect_retrieval_scores_one_on_both():
    result = score([tool("search_publications", PUBLICATIONS)], ["A", "B"])

    assert result == {CONTEXT_PRECISION: 1.0, CONTEXT_RECALL: 1.0}


def test_a_partial_retrieval_keeps_full_precision_and_loses_recall():
    result = score([tool("search_publications", PUBLICATIONS)], ["A", "C"])

    assert result[CONTEXT_RECALL] == 0.5
    assert result[CONTEXT_PRECISION] == 1.0


def test_a_relevant_item_ranked_second_costs_precision():
    result = score([tool("search_precedents", PRECEDENTS)], ["stf-sv-25"])

    assert result == {CONTEXT_PRECISION: 0.5, CONTEXT_RECALL: 1.0}


def test_an_empty_retrieval_scores_zero_on_both():
    result = score([tool("search_publications", {"items": []})], ["A"])

    assert result == {CONTEXT_PRECISION: 0.0, CONTEXT_RECALL: 0.0}


def test_no_tool_call_at_all_is_an_empty_retrieval():
    assert score([], ["A"]) == {CONTEXT_PRECISION: 0.0, CONTEXT_RECALL: 0.0}


def test_a_case_that_expects_nothing_is_not_applicable():
    assert score([tool("search_precedents", {"items": []})], []) == {
        CONTEXT_PRECISION: None,
        CONTEXT_RECALL: None,
    }


def test_a_failed_call_and_other_tools_retrieve_nothing():
    steps = [
        tool("search_publications", PUBLICATIONS, error="boom"),
        tool("list_coverage", PUBLICATIONS),
    ]

    assert retrieved_ids(Trajectory(steps=steps)) == []


def test_a_publication_returned_twice_counts_once_at_its_first_rank():
    steps = [
        tool("search_publications", PUBLICATIONS),
        tool("get_publication", {"cnj_number": "A", "id": "x"}),
    ]

    assert retrieved_ids(Trajectory(steps=steps)) == ["A", "B"]


def test_a_single_item_result_is_read_by_its_id():
    assert retrieved_ids(Trajectory(steps=[tool("get_precedent", {"id": "stf-sv-11"})])) == [
        "stf-sv-11"
    ]


def test_the_metrics_need_the_reference_ids():
    registry = Registry()
    register_metrics(registry)

    assert registry.get(CONTEXT_PRECISION).requires == ("reference_context_ids",)


def _llm() -> ScriptedLLMClient:
    search = {
        "cnj_number": "4839370-58.2009.8.13.0024",
        "date_from": "2026-10-19",
        "date_to": "2026-10-21",
    }
    return ScriptedLLMClient(
        [
            ChatResult(tool_calls=(ToolCall("search_publications", search),), usage=Usage(1, 1)),
            ChatResult(text="Há publicações.", usage=Usage(1, 1)),
        ]
    )


def _golden_case() -> Case:
    cases = load_split("validation").cases
    return next(c for c in cases if c.id == "draft-pub-lookup-03-tjmg")


def test_a_validated_split_is_scored_and_reported_with_the_cassette_dates():
    experiment = run_eval(Dataset("validation", [_golden_case()]), _llm())

    scores = {s.name: s.value for s in experiment.scores}
    assert scores[CONTEXT_PRECISION] == 1.0 and scores[CONTEXT_RECALL] == 1.0
    text = format_experiment(experiment)
    assert "precision 1.00 recall 1.00" in text
    assert "mean context_precision: 1.00 (1 case(s))" in text
    assert "golden set recorded: 2026-" in text


def test_a_draft_or_seed_split_is_never_scored_for_retrieval():
    for split in ("drafts", "seed"):
        experiment = run_eval(Dataset(split, [_golden_case()]), _llm())

        assert not [s for s in experiment.scores if s.name in (CONTEXT_PRECISION, CONTEXT_RECALL)]
        assert "precision" not in format_experiment(experiment)
